# v2.10 — Operator control + Android test gate
- Sticky operator emergency STOP; explicit reset only; no automatic restart.
- Capture service stop and frame cleanup linked to operator STOP.
- Pure Kotlin stop-latch with 9 passing assertions.
- Added Gradle/JUnit unit tests for operator and play-chip guards.
- CI build script runs Android JVM tests before assembling and attesting the APK.
- All offline checks passed; no SDK/Gradle locally; no APK built or 1win tested.
