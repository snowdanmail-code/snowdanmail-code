# AI Remote Control GPT — v1.4 / Turn Cues (research mode)

## Actual deliverable

This release preserves v1.3 source and adds a **read-only** `server/arc_turn` module. It detects the three active button-colour regions from a screenshot, can identify a right-side gold confirmation region, and refuses to interpret menus, replay screens and disconnected scenes as active-game cues when a corresponding scene hint is supplied. A monotonic cue timeline asks for at least two matching observations separated by 150 ms before labeling a pattern stable.

A visually stable pattern is NOT confirmation that it is the account owner's turn. The server returns `turn_verified:false`, `action:null`, and `money_actions_enabled:false`. No click command or coordinates are returned by this subsystem. The screenshot scene hint and remaining-time value originate on the client and are not independently validated. The demo Android sender **currently uses a fixed 10,000 ms training time budget**, not actual screen OCR; timer accuracy is NOT implemented.

## What changed

- `server/arc_turn/cues.py` – normalized-coordinate HSV tri-colour cue reader; no OCR or money actions.
- `server/arc_turn/timeline.py` – bounded session timelines; stability, expiry and scene-conflict checks.
- `server/arc_fastloop/observe.py` – adds `turn_cues` and `turn_timeline` only when the observation is fresh.
- Android `CaptureService.kt` – displays new observation fields, never makes a tap on their basis.
- Android `MainActivity.kt` – clearer v1.4 test labeling.
- `server/tests/test_turn_v14.py` – synthetic-image unit and integration checks.
- `BENCHMARK_TURN_v1.4.json` – offline comparison with 19 **previously observed** screenshots, not a new independent holdout sample.

## Test commands

```bash
cd server
python -m unittest discover -s tests -q
# 266 tests in this environment.
```

For pure Kotlin frame-selection tests, with `kotlinc` available:

```bash
kotlinc android/app/src/main/java/com/example/airemote/FastCapturePolicy.kt android/tests_fast/FastCapturePolicyTest.kt -include-runtime -d fasttests.jar
java -jar fasttests.jar
```

The Android APK was not compiled because Android SDK/build environment is not available. An actual phone and live OpenAI API were not tested. The local screenshot benchmark excludes camera/capture, wireless transport, AI inference, response time and Android gestures.

## Android usage scope

The fast mode is an optional, manual, visible screen-observation test. It is NOT a poker automation release and must not be treated as evidence of profitable play or financial safety. Full end-to-end latency and independent recognition quality still require measurement on-device.

## Previous versions and rollback

The original v1.3 sources remain in this archive. Existing version registry/checkpoint code is carried forward; v1.4 is a source snapshot, not a verified remote hot-swap checkpoint. Keep v1.3 ZIP intact and test any rollback before deployment.
