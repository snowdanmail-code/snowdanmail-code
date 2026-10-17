# AI Remote Control GPT — v2.7 (1win screen observation build candidate)

## Intended field test

The user plans to test directly against the **original Android 1win application** using **free, non-redeemable, non-withdrawable play chips**, not a recreated poker table. The simulator is only a regression environment for reproducing issues observed in the actual application.

**Present implementation does not yet autonomously play in 1win.** The v2.7 Android project has a user-consented MediaProjection capture mode, continuous read-only observation/diagnostics over local network, journal export (metadata, not screenshots), a local-test-only accessibility target and emergency capture stop. Its external-app gesture entry point is compile-time disabled (`EXTERNAL_GAME_ACTIONS_ENABLED=false`). No real 1win phone session has been observed or verified in this release. No ChatGPT Plus authorization has been completed. No Android APK is included because Android SDK/Gradle are unavailable in the current build environment.

## First real 1win test (read-only)

1. Build the Android debug APK with Windows `windows/01_BUILD_APK.ps1` **if** Java 17, Android SDK Platform 35 and Gradle 8.9 are installed, or build via the included GitHub Actions workflow if a repository is connected.
2. Install APK with `windows/03_CONNECT_PHONE.ps1 -InstallApk` using USB debugging; forward local port 8787 by ADB (`adb reverse tcp:8787 tcp:8787`).
3. Start the local server with `windows/02_START_SERVER.ps1`. Use a strong `ARC_DEVICE_TOKEN` and do not expose local HTTP endpoint to public network.
4. Open the Android app; approve MediaProjection; tap **НАЧАТЬ НАБЛЮДЕНИЕ ЭКРАНА 1WIN (без ставок)**, then open 1win yourself, only in the free-chip mode. Do not navigate to sensitive payment or account screens while capture is active.
5. Export the observation event journal and share diagnostics if recognition is wrong; do not provide passwords or access tokens. Use the explicit STOP control to end capture.

## Verified this run

- Python server tests: **337/337 OK** (`QA_SERVER_v2.7.log`).
- Lab auth adapter tests (synthetic OAuth tokens): **44/44 OK** (`QA_AUTH_v2.7.log`).
- Lab strategy tests (synthetic hands): **18/18 OK** (`QA_STRATEGY_v2.7.log`).
- Android static preflight tests: **4/4 OK** (`QA_PREFLIGHT_TESTS_v2.7.log`). Fixed a stale comparison in the wrong-APK-version test; now detects version v2.7 correctly.
- Android static preflight: **PASS**, with no local SDK and no wrapper JAR (`QA_PREFLIGHT_v2.7.log`).
- Python compile check: PASS.

None of these checks demonstrate an installed APK, access to ChatGPT subscription entitlements, actual successful model responses, or live poker input automation.

## Next engineering gate

Build/install a verified APK and collect a consented read-only capture trace from the real free-chip 1win UI. Then evaluate field recognition, timing and confidence. Any external-app automated gesture needs separate verification that 1win permits automation in this mode; never bypass the platform's controls. Also verify the official Sign in with ChatGPT availability in the user's account before promising Plus-funded execution. The provider boundary must support an eventual paid OpenAI API provider without replacing GPT with local hand-coded rules.
