# v2.0 — Build pipeline and lab guards

- CI: private-repository GitHub Actions to run offline tests and build a debug APK using JDK 17, Gradle 8.9 and Android SDK 35.
- Android: version 2.0.0-lab; external game gestures hard-disabled at build config, service and accessibility layers.
- Security: debug HTTP exceptions limited to localhost/Android emulator bridge; no general HTTP cleartext allowance.
- Fix: move `tapConfiguredWindowBlocking` into the correct Kotlin companion scope.
- QA: add Android preflight script, mutation tests and local build instructions.
- Limitations: no local SDK or Gradle; full APK not built or installed; CI pending repository access.
