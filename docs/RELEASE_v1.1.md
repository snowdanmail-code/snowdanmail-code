# Release v1.1 — scope and compatibility

- Parent version: AI Remote Control GPT v1.0 (immutable source baseline)
- Added: `arc_vision.card_reader`, `arc_vision.glyph_atlas`, `arc_vision.benchmark_cards`, private cropped-card regression fixtures, and `POST /vision/cards` read-only route.
- Changed: requirements-vision; increased image-processing dependencies (`numpy`, `opencv-python-headless`).
- Unchanged contracts: /math/equity, /poker/screen, /stream/observe, Android, rollback system, post-session-only replay policy.
- No app APK, no GPT production integration tested.
- Rollback: revert to archived v1.0 source/release and restore dependencies; never overwrite user event log or funds. Do not switch during an active session.
- New component version: `arc_fixed_glyph_v1.1.0`; checkpoint candidate only, **not promoted for live financial decisions**.
- Quality gate: stable lab tests plus a new genuinely independent hand dataset required before broader deployment.
