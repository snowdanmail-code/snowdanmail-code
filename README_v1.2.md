# AI Remote Control GPT v1.2 — laboratory visual measurements

**Status:** Source code and offline tests, NOT a finished APK, poker agent, autonomous player, or validated real-money system. OpenAI API was not called for these tests.

## Implemented now

- `server/arc_vision/money_reader.py` — independently replaceable, calibrated fixed-layout money-label recognizer. Reads the **pot** as integer USD cents from a 709×1536 canonical poker HUD. Separately reads the **central pile label** where visible. This second quantity is **not** automatically a player bet or call amount.
- `server/arc_vision/money_glyphs.json` — anonymous binary digit masks for **0–9** built from manually confirmed in-game text. No full video, usernames or avatars in this atlas.
- `server/arc_vision/combined_observer.py` — merges card and money observations and uses existing `arc_poker_math` only when card evidence is complete. Never invents missing cards or derives action commands.
- HTTP `POST /vision/measure` — authenticated read-only endpoint. Body: `{ "request":"vision_measure", "image_base64":"<JPEG BASE64>", "screen_state":"live_table" }`. The caller's scene label is only a hint, not authorization. Returns `money_actions_enabled:false`, `action:null`, `can_place_wager:false`.
- `datasets/money_gold/` — bank-label crops with original screenshot labels, **no full screenshots**; `datasets/video_money_checks/` — 16 small money-only video crops. These support reproducible offline testing and protect unrelated on-screen content.
- `server/requirements-vision.txt` — now lists numpy + opencv-headless + Pillow, which older package versions omitted.

## Scope limitations

1. Exact **1win font and HUD geometry** only; changing orientation, app version, table skin or layout may invalidate recognition. Amount confidence is *uncalibrated*. Decimal '$' marker and bank caption are required, otherwise abstain.
2. The numeric reader can extract the pot, but **does not fully recognize all seat-level bets, call amounts, button amounts or side pots**. The central chip pile is not interpreted as a bet. Do not use amounts to perform financial actions.
3. Full recognition of **every rank of hero/board cards** is **not complete**; v1.1's limited card template atlas is unchanged. On uncertain cards the combined endpoint withholds made-hand conclusions.
4. Replay, overlay, disconnected screens and unverified scenes must be rejected by an independent verified screen-state module; caller-supplied `screen_state=live_table` is not sufficient evidence. Current code remains read-only for this reason.
5. Only unit/integration tests were executed here; **no Android APK build, Android touch loop, external OpenAI call, or end-to-end real money gameplay** was performed.
6. The release manager code is preserved, but this version is a **candidate source release**, not a promoted deployment. Version rollback on a running phone remains unverified.

## Offline tests

```bash
cd server
python -m pip install -r requirements-vision.txt
python -m unittest discover -s tests -q
```

All **bank-money fixtures are anonymized**. Existing card reader fixtures also contain masked player names. Bundled regression tests compare both annotated training and same-app holdout examples; they are *not independent game-level field accuracy measurements*. The sampled video cases include some same hands and an image used to add the missing digit 9. Do not claim accuracy for unseen games.

## Architecture invariants

- Each component is separately versioned and replaceable.
- The money reader deals only in integer cents; no binary float money totals.
- A missing/uncertain amount is `null`, never `0`. Confirmed literal `$0` is 0 cents.
- The combined reader never produces an Android gesture or money wager.
- Overlays/replay/disconnections are explicitly blocked.
- Historical session logs must survive rollback, and post-session reviewing must run only after confirmed zero open tables.

## Next version targets

- Profile-backed geometry calibration for dynamically positioned bet/call labels.
- Independent board-card/hero-card coverage and accuracy measurement from new unseen games.
- Signed/pinned vision templates and a manual Android video-consent test with no financial clicks.
- First-party state classifier proof independent from caller scene labels.
