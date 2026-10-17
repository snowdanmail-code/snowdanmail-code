# Release decision v1.0

## Completed

- Mathematics separate from GPT (`arc_poker_math`) with a clean Python API.
- Data-quality gate separate from visual model (`arc_vision.consistency`).
- Stateful cross-frame checking separate from screenshot reading (`arc_vision.timeline`).
- Offline research API for equity, bounded and token protected.
- Regression fixtures from previously supplied completed hands.
- Original v0.9 versioning registry, Android sources and screenshot manifest preserved.

## Risk register

| Risk | Status | Control |
| --- | --- | --- |
| Image parser hallucinates a card | Open | Duplicate/phase checks only; unverified values still possible. Needs labeled benchmark. |
| Percent equity mistaken for profitability | Open | Explicit uniform-opponent assumption and no wagering recommendations. |
| Replay mistaken for live table | Reduced, unproven on Android | Gate forbids replay/overlay to qualify for live inference. |
| Swapped hero cards between frames | Reduced | Timeline rejects within same hand ID. |
| Incomplete connection resumed | Reduced | Timeline requires reconfirmation after pause. |
| Android APK doesn't compile | Open | Android SDK build required. |
| Version rollback fails on phone | Open | Only server laboratory verification exists. |
| Original site restricts automated play | Unknown/not resolved | No new monetary automation enabled. |

## Acceptance gate for v1.1

Do not describe vision as reliable until labeled unseen screenshots have been processed by the *actual* intended inference backend, with per-field precision/recall and error analysis. Do not describe client as working until install and user-permission flows are exercised on Android.
