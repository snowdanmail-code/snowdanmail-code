# Change log v1.4

- Added conservative turn-color UI cues and temporal stability analysis.
- Fast endpoint retains backward-compatible fields and adds nested read-only `turn_cues` / `turn_timeline` on fresh observations.
- Preserves `action:null`, `can_place_wager:false`, `money_actions_enabled:false`.
- Updated Android fast observation text; no change to gesture dispatch or live betting.
- Added 18 automated tests, now 266 total; benchmark matches 19 preselected screenshots, a non-independent measure.
- Never claims a verified turn from color cues alone or from client-supplied scene labels.
