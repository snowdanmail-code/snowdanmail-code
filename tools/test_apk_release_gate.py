"""Offline contract tests; synthetic ZIPs are NEVER described as real APKs."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apk_release_gate import ApkGateError, inspect, tool_path

BADGING = ("package: name='com.example.airemote' versionCode='31' versionName='2.11.0-persistent-stop'\n"
           "sdkVersion:'29'\ntargetSdkVersion:'35'\napplication-debuggable\n")
SIGNATURE = ("Verifies\nVerified using v1 scheme (JAR signing): false\n"
             "Verified using v2 scheme (APK Signature Scheme v2): true\n"
             "Signer #1 certificate SHA-256 digest: " + "a" * 64 + "\n")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.apk = Path(self.t.name) / 'fixture.apk'
        with zipfile.ZipFile(self.apk, 'w') as z:
            z.writestr('AndroidManifest.xml', b'fake manifest for tests only')
            z.writestr('classes.dex', b'fake dex for tests only')
            z.writestr('resources.arsc', b'fake resources for tests only')
            z.writestr('pad.bin', b'x' * 120)

    def runner(self, badging=BADGING, signature=SIGNATURE, returncode=0):
        def fake(command, **_kwargs):
            return SimpleNamespace(returncode=returncode,
                                   stdout=badging if 'dump' in command else signature, stderr='')
        return fake

    def test_valid_mocked_metadata_and_signature(self):
        report = inspect(self.apk, 'aapt', 'apksigner', runner=self.runner())
        self.assertEqual(report['status'], 'VERIFIED_DEBUG_APK')
        self.assertFalse(report['installed_or_tested_on_device'])
        self.assertEqual(len(report['sha256']), 64)

    def test_rejects_wrong_package(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(badging=BADGING.replace('com.example.airemote', 'com.other.app')))

    def test_rejects_wrong_version(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(badging=BADGING.replace("versionCode='31'", "versionCode='29'")))

    def test_rejects_non_debuggable(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(badging=BADGING.replace('application-debuggable', '')))

    def test_rejects_wrong_sdk(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(badging=BADGING.replace("targetSdkVersion:'35'", "targetSdkVersion:'34'")))

    def test_rejects_unsigned_apk(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(signature='Verified using v2 scheme (APK Signature Scheme v2): false\n'))

    def test_rejects_missing_certificate(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(signature=SIGNATURE.replace('Signer #1 certificate SHA-256 digest:', 'Other:')))

    def test_rejects_aapt_failure(self):
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner(returncode=2))

    def test_rejects_missing_dex(self):
        with zipfile.ZipFile(self.apk, 'w') as z:
            z.writestr('AndroidManifest.xml', 'dummy')
            z.writestr('resources.arsc', 'dummy')
            z.writestr('pad.bin', 'x' * 120)
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner())

    def test_rejects_corrupt_zip(self):
        self.apk.write_bytes(b'not-an-apk' * 100)
        with self.assertRaises(ApkGateError):
            inspect(self.apk, 'aapt', 'apksigner', runner=self.runner())

    def test_requires_sdk_for_tools(self):
        with self.assertRaises(ApkGateError):
            tool_path('aapt', sdk=str(Path(self.t.name) / 'missing-sdk'))


if __name__ == '__main__':
    unittest.main()
