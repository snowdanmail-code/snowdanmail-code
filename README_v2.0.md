# AI Remote Control GPT v2.0 — Build Pipeline Lab

## Status

This is a **source-code deliverable**, not an installable APK. This runtime lacks Android SDK 35 and Gradle 8.9, and network DNS is unavailable, so a full Android build or device installation cannot be verified locally. Do not report an APK as created.

## Scope of v2.0

1. Introduces GitHub Actions for `:app:assembleDebug` in a Linux Android SDK environment; builds are uploaded as private CI artifacts in the repository.
2. Pins build tool expectations: Java 17, Gradle 8.9, AGP 8.7.3, Kotlin 2.0.21, Android compile/target 35. GitHub Actions will download SDK and dependencies in its own runner, not in this offline environment.
3. Adds `tools/android_preflight.py` checks: manifests, permissions, build version, SDK level, repository CI, network-security configuration, and lab guards.
4. Fixes a probable Kotlin compile failure in `DemoAccessibilityService.kt`: `tapConfiguredWindowBlocking` was defined as an instance function but called on the class companion. It is now located inside the companion. The correction is **not yet verified by a full Android compile**.
5. Implements defense-in-depth: `BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED=false`; prevents initiation from the Android UI, CaptureService and AccessibilityService. External real-money actions are NOT part of this lab build. On-screen local demo button remains for consented safe gesture testing.
6. Replaces debug-wide unencrypted-HTTP permission with `networkSecurityConfig` permitting local emulator addresses `127.0.0.1` and `10.0.2.2` only. All other HTTP is denied. Production manifest is already configured with cleartext denied.
7. Updates app lab versionName to `2.0.0-lab`, versionCode to 20, and provides a no-wrapper local builder `tools/build_android_debug.sh` (requires external installed SDK+Gradle).

## CI use in a private GitHub repository

- Push the **contents** of this project directory into a private GitHub repository root (do not push personal screen recordings or secrets).
- Run `Actions → Android APK + offline checks → Run workflow`, or push a commit.
- GitHub Actions first runs Python offline tests, then builds a debug APK using SDK 35 and Gradle 8.9, and uploads it as `ai-remote-control-v2.0-debug-apk` if successful. GitHub Actions results are **not verified as of this source release**, since no repo is connected.
- Download/install only for local consented testing. It is a debug signed APK, **not** an official Play Store release.

## Local build on a configured Linux/macOS host

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
# Requires Java 17, Gradle 8.9 and the Android SDK 35 platform/build-tools.
./tools/build_android_debug.sh
```

If building fails, preserve the Gradle logs. Do not work around security checks or disable sandbox restrictions to get a green build.

## Offline QA in this environment

```bash
python tools/android_preflight.py --strict
PYTHONPATH=tools python -m unittest discover -s tools -p 'test_*.py' -q
(cd server && python -m unittest discover -s tests -q)
# Pure Kotlin/JVM tests can run with an existing kotlinc and JDK, no SDK.
```

## Known outstanding steps

- Verify Android Gradle assembly in actual SDK 35 environment.
- Install on test Android device and check MediaProjection, foreground notification, stop action and loopback HTTPS behavior.
- Measure capture → server → response p50/p95/p99 on both Wi-Fi and cellular. Synthetic latency metrics are not device measurements.
- Test live GPT API separately with no financial actions. No OpenAI API key or payment credentials are included.
- GitHub authentication alone did not grant access to any repository at last inspection. Nothing was pushed remotely.

This release retains the previous server math, visual recognition and reversible source snapshots but makes **no claim** to be a validated autonomous poker player or a financially safe system.
