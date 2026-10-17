# Technical video review: 2026-10-17

The following times are **sampled reference frames**, not an exhaustive hand-by-hand transcription. No evaluation of user's choices was performed.

| Video | At | Observed UI | Why it matters |
|---|---:|---|---|
| 025551 | 00:13 | Statistics overlay | Masked game areas must not be interpreted as empty |
| 025551 | 00:20 | Waiting-list overlay | Visibility/missing data are distinct from absent players |
| 025551 | 00:23 | Hand-history overlay | Post-session review remains gated by complete exit |
| 024504 | 00:40 | Showdown | Compare board reveal & end-of-hand transitions |
| 024504 | 01:40 | Gray pre-action controls | Distinguish provisional selection vs actual turn |
| 024504 | 05:42 | Bet-size panel | Slider and confirmation are distinct states |
| 024504 | 06:22 | Colored active-action controls | Distinguish from pre-action buttons |
| 023653 | 00:30 | Showdown | Hand/board highlighting and transition |
| 023653 | 03:47 | Active choice state | Timer and action buttons may be visible |

Additional observations: avatars and circular seats change/shift visually; a card animation may temporarily cover parts of the bank, and some players may be folded yet remain seated. All screenshot-derived classifications are *candidates* pending a full-frame, sequential benchmark.

## v0.10 recognition plan
- Generate privacy-sensitive ground-truth labels for more frames across each transition.
- Compare frame-by-frame recognition using stratified sequences, not random stills only.
- Metrics: precision/recall per screen-state; numeric OCR exact match; card suit/rank accuracy; uncertain abstention; median and p95 latency.
- Explicitly verify state machines for pre-action -> active-action, sizing -> confirmation -> result, board animations -> stable frame, session active -> fully exited.
- Do not enable autonomous real-money actions from unvalidated visual guesses.
