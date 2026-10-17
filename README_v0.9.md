# AI Remote Control GPT v0.9 — Video fixture pack

## Purpose
An **incremental module** built over v0.8, not a new poker agent and not a tested APK.
Added `server/arc_vision/` and a privacy-sensitive, manually reviewed video-frame dataset.

## Videos inspected
- `Screen_Recording_20261017_025551.mp4` — approximately 24.63 s.
- `Screen_Recording_20261017_024504.mp4` — approximately 469.37 s.
- `Screen_Recording_20261017_023653.mp4` — approximately 252.02 s.
Combined: ~12 min 26 seconds; 1080x2340 each; videos NOT bundled.

## Newly observed states
1. `OVERLAY_SESSION_STATS`: session stats overlay opens while game stays in background.
2. `OVERLAY_WAITLIST`: waitlist sidebar can obscure game state.
3. `OVERLAY_HAND_HISTORY`: history sidebar also obscures game state. This does **not** authorize opening review while seated.
4. `BET_SIZING`: choosing bet amount and confirming are different screen states.
5. `PRE_ACTION` gray buttons vs `ACTIVE_ACTION` colored buttons.
6. `SHOWDOWN` and between-hand animations require separate waiting state.

## Dataset
`datasets/capture_20261017/manifest.json`: 18 *manually reviewed* frames from three videos, time references, labels, SHA256 frame checksums, SHA256 source video checksums.
The dataset is for regression testing, not proof of screen-recognition accuracy. No OCR or live inference was run.
Frames contain personal usernames and avatar images; do not publish without redaction/consent.

## Safety
The new `arc_vision.ui_policy` module **never** authorizes financial actions. An overlay, replay, failed connection, or unknown screen results in observation-only status.
Post-session review is enabled only when a separate trusted component confirms zero open tables and no active session.

## Tests
`cd server && PYTHONPATH=. python -m unittest discover -s tests -p 'test_video_dataset.py' -v`

## Status
Android APK is NOT compiled. GPT image inference and accuracy on new clips are NOT tested. The prior v0.8 source code is carried forward, but no live 1win automation has been enabled.

## Regression verification
Full existing server suite plus new tests: **196 / 196 passed** in this environment.
See `full-test-results-v0.9.txt`. This tests server code and dataset-integrity/policy only, **not** the Android APK or real-world recognition performance.
