#!/usr/bin/env python3
"""Static offline preflight; NOT equivalent to a Gradle build or APK installation."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = '{http://schemas.android.com/apk/res/android}'


def audit(root: Path = ROOT) -> dict:
    errors = []
    warnings = []
    config = root / 'android' / 'app' / 'build.gradle.kts'
    manifest = root / 'android' / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
    debug_manifest = root / 'android' / 'app' / 'src' / 'debug' / 'AndroidManifest.xml'
    security = root / 'android' / 'app' / 'src' / 'debug' / 'res' / 'xml' / 'debug_network_security.xml'
    workflow = root / '.github' / 'workflows' / 'ci.yml'
    build_ps = root / 'windows' / '01_BUILD_APK.ps1'
    connect_ps = root / 'windows' / '03_CONNECT_PHONE.ps1'
    for f in (config, manifest, debug_manifest, security, workflow, build_ps, connect_ps):
        if not f.is_file():
            errors.append('Required file missing: ' + str(f.relative_to(root)))
    if errors:
        return {'status': 'FAIL', 'errors': errors, 'warnings': warnings}

    gradle = config.read_text(encoding='utf-8')
    if not re.search(r'versionCode\s*=\s*32\b', gradle):
        errors.append('Incorrect versionCode; expected 32')
    if not re.search(r'minSdk\s*=\s*29\b', gradle):
        errors.append('Incorrect minSdk; expected 29')
    if not re.search(r'compileSdk\s*=\s*35\b', gradle):
        errors.append('compileSdk is not 35')
    if not re.search(r'targetSdk\s*=\s*35\b', gradle):
        errors.append('targetSdk is not 35')
    if not re.search(r'EXTERNAL_GAME_ACTIONS_ENABLED"\s*,\s*"false"', gradle):
        errors.append('Lab build does not hard-disable external game actions')
    if not re.search(r'versionName\s*=\s*"2\.12\.0-card-auto-fill"', gradle):
        errors.append('Incorrect app lab version')

    tree = ET.parse(manifest)
    top = tree.getroot()
    apps = top.findall('application')
    if len(apps) != 1:
        errors.append('Expected one application in main manifest')
    else:
        app = apps[0]
        if app.get(ANDROID_NS + 'usesCleartextTraffic') == 'true':
            errors.append('Main app permits all cleartext HTTP')
        if app.get(ANDROID_NS + 'allowBackup') != 'false':
            errors.append('Screen-capture app must disable backup')
        services = app.findall('service')
        fg = [s for s in services if s.get(ANDROID_NS + 'name') == '.CaptureService']
        if len(fg) != 1 or fg[0].get(ANDROID_NS + 'foregroundServiceType') != 'mediaProjection':
            errors.append('MediaProjection foreground service absent or misconfigured')
    permissions = {p.get(ANDROID_NS + 'name') for p in top.findall('uses-permission')}
    for permission in ('android.permission.INTERNET', 'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION'):
        if permission not in permissions:
            errors.append('Missing permission: ' + permission)

    ET.parse(debug_manifest)
    secroot = ET.parse(security).getroot()
    base = secroot.find('base-config')
    if base is None or base.get('cleartextTrafficPermitted') != 'false':
        errors.append('Debug security lacks deny-by-default cleartext')
    for domain_cfg in secroot.findall('domain-config'):
        if domain_cfg.get('cleartextTrafficPermitted') == 'true':
            for d in domain_cfg.findall('domain'):
                if d.text not in ('127.0.0.1', '10.0.2.2'):
                    errors.append('Non-local HTTP exception found: ' + str(d.text))

    kotlin_base = root / 'android' / 'app' / 'src' / 'main' / 'java' / 'com' / 'example' / 'airemote'
    activity = (kotlin_base / 'MainActivity.kt').read_text()
    service = (kotlin_base / 'CaptureService.kt').read_text()
    accessibility = (kotlin_base / 'DemoAccessibilityService.kt').read_text()
    if 'BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED' not in activity or 'BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED' not in service:
        errors.append('Lab safety switch absent from activity or service')
    if 'BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED' not in accessibility:
        errors.append('Accessibility gesture entry point lacks lab guard')
    if 'button("ЗАПУСТИТЬ СЕССИЮ' in activity:
        errors.append('UI exposes external game-action start button in lab build')
    if 'measureConnectionRtt()' not in activity or 'diagnostics/ping' not in activity:
        errors.append('Missing Android read-only RTT diagnostic')
    if not (kotlin_base / 'RttSummary.kt').is_file():
        errors.append('Missing pure Kotlin RTT summarizer')
    if 'emergencyStop()' not in activity or 'operatorControl.mayStart()' not in activity:
        errors.append('Missing sticky operator STOP and manual re-arm gate')
    if not (kotlin_base / 'OperatorControl.kt').is_file():
        errors.append('Operator stop latch implementation missing')
    durable = kotlin_base / 'OperatorStopStore.kt'
    if not durable.is_file():
        errors.append('Persistent operator STOP implementation missing')
    else:
        stop_source = durable.read_text(encoding='utf-8')
        if not all(term in stop_source for term in ('getSharedPreferences', 'getBoolean(STOPPED, true)', '.commit()')):
            errors.append('Durable STOP is not fail-closed or synchronously persisted')
    if not all(term in activity for term in ('OperatorStopStore.stop(this)', 'OperatorStopStore.armFromOperator(this@MainActivity)', 'OperatorStopStore.isStopped(this)')):
        errors.append('Activity is not wired to durable operator STOP')
    if not all(term in service for term in ('OperatorStopStore.stop(this)', 'OperatorStopStore.isStopped(this)')):
        errors.append('CaptureService is not wired to durable STOP')
    if 'OperatorStopStore.isStopped(service)' not in accessibility or 'OperatorStopStore.isStopped(this)' not in accessibility:
        errors.append('Gesture service is not wired to durable STOP')

    if 'Foreground' in service and 'ACTION_STOP' not in service:
        errors.append('Missing stop action')

    yml = workflow.read_text(encoding='utf-8')
    for expected in ('setup-android@v3', 'setup-gradle@v4', 'tools/build_android_debug.sh', 'upload-artifact@v4', 'python-offline:'):
        if expected not in yml:
            errors.append('Build CI missing: ' + expected)
    if (root / 'android' / 'gradle' / 'wrapper' / 'gradle-wrapper.jar').exists() is False:
        warnings.append('No gradle-wrapper.jar; CI uses setup-gradle 8.9; for local use install Gradle 8.9')
    expected_apk = 'AI-Remote-Control-v2.12-PLAYER-LAB.apk'
    for script in (build_ps, connect_ps):
        if expected_apk not in script.read_text(encoding='utf-8'):
            errors.append('Windows script APK version mismatch: ' + script.name)
    gradle_build_script = root / 'tools' / 'build_android_debug.sh'
    if not gradle_build_script.is_file() or ':app:testDebugUnitTest' not in gradle_build_script.read_text(encoding='utf-8'):
        errors.append('Gradle build script does not run Android JVM unit tests')
    if not (root / 'android/app/src/test/java/com/example/airemote/OperatorControlJvmTest.kt').is_file():
        errors.append('Missing Android Gradle STOP latch test')
    if ':app:testDebugUnitTest' not in build_ps.read_text(encoding='utf-8'):
        errors.append('Windows build skips mandatory Android unit tests')
    if 'OperatorStopStore.isStopped(this)' not in activity:
        errors.append('Android activity does not check persistent STOP on resume')

    if 'ai-remote-control-v2.12-debug-apk' not in yml:
        errors.append('CI artifact version mismatch')
    build_script = root / 'tools' / 'build_android_debug.sh'
    if not build_script.is_file() or 'apk_release_gate.py' not in build_script.read_text(encoding='utf-8'):
        errors.append('APK verification gate is not wired into build script')
    if not (root / 'tools' / 'apk_release_gate.py').is_file():
        errors.append('APK verification module missing')
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or ''
    sdk_ready = bool(sdk) and (Path(sdk) / 'platforms' / 'android-35' / 'android.jar').is_file()
    return {'status': 'PASS' if not errors else 'FAIL', 'errors': errors, 'warnings': warnings,
            'android_sdk_available_here': sdk_ready, 'is_apk_build': False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
