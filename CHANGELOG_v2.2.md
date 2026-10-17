# v2.2 — Offline Capture Diagnostics (no OpenAI API)

**Base:** immutable v2.1 Android Test Kit archive (SHA-256 `8e6e64387064dbf356f1c9a3b66fcc9140023de8b4f7d44707505b51180ab87d`).

## One modular addition

- Added `server/arc_offline_inspect.py`: bounded, in-memory JPEG decoder and capture-quality diagnostics (dimensions, JPEG size, brightness, contrast, coarse quality flags). Uses Pillow locally; never sends frames to OpenAI or uses a ChatGPT account.
- Added authenticated `POST /offline/inspect` endpoint (`request=offline_inspect`, `image_base64=<JPEG>`). Only exact fields are accepted; corrupt, truncated, too-small or oversized frames are rejected. Response always includes `action:null` and `money_actions_enabled:false`.
- Added Android UI button **БЕСПЛАТНО: проверить качество кадра (без GPT)**. Reuses existing localhost/HTTPS + device-token transport, displays JSON diagnostics.
- Added 10 Python tests covering JPEG validation, token auth, payload restrictions, no-API behavior even if a key is present, and absence of disk writes.
- Updated Android lab version to `2.2.0-lab`, preflight version check, and CI artifact name. CI runs the offline HTTP smoke test.

## Verified locally

- 320 Python server tests: PASS (including 10 new tests).
- 4 standalone Kotlin/JVM test executables: PASS.
- Android static preflight: PASS (3 preflight unit tests PASS).
- Local HTTP smoke: PASS.
- APK compilation: **NOT RUN** (Android SDK/Gradle unavailable).
- GitHub CI: **NOT RUN** (no accessible repositories/installations).
- Physical Android and real 1win: **NOT TESTED**.

## Security and honesty boundaries

- This is **not GPT** and **not OCR**: the offline module does not identify cards, buttons, balances or actions.
- The user’s ChatGPT Plus subscription is not a general-purpose API credential; this release does not implement unsupported session/cookie extraction or browser automation.
- Screenshots are decoded in process and not persisted by the new module; the app still requires user permission to capture.
- No wagers, anti-bot evasion, or real-money actions were tested or added.
