import shutil
import tempfile
import unittest
from pathlib import Path
from android_preflight import ROOT, audit


REQUIRED_FOR_AUDIT = [
    'android/app/build.gradle.kts',
    'android/app/src/main/AndroidManifest.xml',
    'android/app/src/debug/AndroidManifest.xml',
    'android/app/src/debug/res/xml/debug_network_security.xml',
    'android/app/src/main/java/com/example/airemote/MainActivity.kt',
    'android/app/src/main/java/com/example/airemote/CaptureService.kt',
    'android/app/src/main/java/com/example/airemote/DemoAccessibilityService.kt',
    'android/app/src/main/java/com/example/airemote/RttSummary.kt',
    'android/app/src/main/java/com/example/airemote/OperatorControl.kt',
    'android/app/src/main/java/com/example/airemote/OperatorStopStore.kt',
    'android/app/src/test/java/com/example/airemote/OperatorControlJvmTest.kt',
    '.github/workflows/ci.yml',
    'windows/01_BUILD_APK.ps1', 'windows/03_CONNECT_PHONE.ps1',
    'tools/build_android_debug.sh', 'tools/apk_release_gate.py'
]


def make_fixture(dest: Path):
    for rel in REQUIRED_FOR_AUDIT:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest / rel)
    # Prove a test is checking its specific mutation, not failing from absent fixtures.
    report = audit(dest)
    if report['status'] != 'PASS':
        raise AssertionError('Invalid baseline fixture: ' + str(report['errors']))


class AndroidPreflightTests(unittest.TestCase):
    def test_baseline_has_no_preflight_errors(self):
        self.assertEqual(audit()['status'], 'PASS')

    def test_baseline_version_and_gate_are_pinned(self):
        build = (ROOT / 'android/app/build.gradle.kts').read_text()
        self.assertIn('versionCode = 31', build)
        self.assertIn('versionName = "2.11.0-persistent-stop"', build)
        self.assertIn('EXTERNAL_GAME_ACTIONS_ENABLED", "false"', build)
        self.assertIn('apk_release_gate.py', (ROOT / 'tools/build_android_debug.sh').read_text())

    def test_detects_external_game_action_switch(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            make_fixture(target)
            p = target / 'android/app/build.gradle.kts'
            p.write_text(p.read_text().replace('"EXTERNAL_GAME_ACTIONS_ENABLED", "false"',
                                                     '"EXTERNAL_GAME_ACTIONS_ENABLED", "true"'))
            report = audit(target)
            self.assertTrue(any('hard-disable external game actions' in e for e in report['errors']))

    def test_detects_global_cleartext_in_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            make_fixture(target)
            p = target / 'android/app/src/main/AndroidManifest.xml'
            p.write_text(p.read_text().replace('android:usesCleartextTraffic="false"',
                                                    'android:usesCleartextTraffic="true"'))
            report = audit(target)
            self.assertTrue(any('permits all cleartext HTTP' in e for e in report['errors']))

    def test_detects_wrong_windows_apk_version(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            make_fixture(target)
            p = target / 'windows/03_CONNECT_PHONE.ps1'
            p.write_text(p.read_text().replace('AI-Remote-Control-v2.11-PLAYER-LAB.apk',
                                                    'AI-Remote-Control-v2.6-READONLY.apk'))
            result = audit(target)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any('APK version mismatch' in e for e in result['errors']))

    def test_detects_removed_persistent_stop(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            make_fixture(target)
            p = target / 'android/app/src/main/java/com/example/airemote/OperatorStopStore.kt'
            p.write_text(p.read_text().replace('getBoolean(STOPPED, true)',
                                               'getBoolean(STOPPED, false)'))
            report = audit(target)
            self.assertTrue(any('fail-closed' in e for e in report['errors']))


if __name__ == '__main__':
    unittest.main()
