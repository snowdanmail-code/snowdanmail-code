# AI Remote Control GPT — v1.1: conservative JPEG card recognizer

**Release status:** offline development source. Read-only image parsing, not a poker-playing Android application. No APK compiled, no live OpenAI API call, no money wagers placed.

## What is actually implemented

- `server/arc_vision/card_reader.py`: independent image-reader adapter for a fixed 1win Hold'em layout. It consumes JPEG and returns **either an all-confirmed set of community/hero cards or ABSTAIN**. Does not use OCR, GPT or hand-coded poker decisions. At this stage it uses a restricted rank/suit glyph atlas made from manually inspected user-provided screens.
- `server/arc_vision/glyph_atlas.json`: only binary rank/suit glyph shapes; excludes full screenshots, personal nicknames, avatars, balances and unrelated visible data. **Incomplete training coverage.**
- `POST /vision/cards`: authenticated, read-only local HTTP endpoint; no bet, wager, tap, checkout, or navigation response. Explicitly reports `authoritative:false`, `money_actions_enabled:false`, `action:null`.
- `datasets/cards_gold`: eleven privacy-reduced test JPEGs containing **card regions only** with SHA-256 integrity labels, plus `server/arc_vision/benchmark_cards.py` for benchmarking original and recompressed (55,75,88) JPEGs.
- Existing math/rollback/Android modules retained; no changes to their public contracts. Old source is still available in the v1.0 ZIP.

## Local test and benchmark

```bash
cd server
pip install -r requirements-vision.txt
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=. python -m arc_vision.benchmark_cards ../datasets/cards_gold
```

A real device can send one JPEG to localhost if the backend runs on-device (or via an explicitly secured relay). The server's loopback listener does not accept arbitrary internet connections.

```http
POST /vision/cards
X-Device-Token: YOUR_SECRET
Content-Type: application/json

{"request":"vision_cards","screen_state":"live_table","image_base64":"<base64 JPEG>"}
```

Example complete result (fixture only):

```json
{
  "mode": "offline_glyph_reader",
  "quality": "complete",
  "hero_cards": ["4d", "Qd"],
  "board_cards": ["2h", "Ts", "Qc"],
  "action": null,
  "money_actions_enabled": false,
  "authoritative": false
}
```

## Measured benchmark (local, NOT unseen-table accuracy)

- Eleven card-region screenshots selected from user-provided material, including **one atlas-training-overlap** test and several different snapshots of the same hand. These are *not* eleven independent game situations.
- On these exact screenshots: 5/5 designated readable examples returned the expected full card list, and 6/6 intentionally dimmed/empty examples abstained. **4/4** readable examples excluding the direct template-training-overlap also matched.
- JPEG quality 55/75/88: same observed classifications for these exact 11 test states.
- Typical JPEG bytes after recompression: roughly 26 KB for q55, 29 KB q75, 34 KB q88, for these **privacy-masked black-background fixtures**. Full real screenshots have very different sizes.
- Typical local server processing was a few milliseconds on the current workstation; **not a measured Android latency or GPT API turnaround**.
- No measured error rates on genuinely independent hands, screen sizes, UI themes, animations or poor connections. The atlas is incomplete and insufficient for unattended gameplay.

## Fail-closed restrictions

1. Darkened folded cards, unsupported card symbols, unusual device geometry, unreadable glyphs, duplicate card identities, impossible board card counts, replay, session history, known overlays and disconnect all return `abstain` rather than a guessed card list.
2. The endpoint accepts a caller-supplied `screen_state` hint; **it has not independently proven whether the screenshot is live or free of overlay**. The result must not be used as proof that an action is safe.
3. It cannot read pot sizes, numeric bets, blinds, all-in labels, timers or arbitrary lobby layouts. These are future research tasks.
4. Visual masks do not establish hand/range correctness or professional decision quality. No earnings/winrate guarantees.
5. The inherited v0.9 regression directory contains source-derived video captures; treat the whole archive as **private** even though the *new* glyph atlas and card benchmark are privacy-reduced. Do not redistribute.
6. **No money action should depend on this experimental classifier**, regardless of `quality`.

## Next development targets

- Collect genuinely unseen sessions with non-overlapping hands and independently review labels; report false-confidence risk separately from abstention coverage.
- Build an independent state/overlay detector and scene geometry calibration (current coordinates assume fixed resized 709×1536 portrait).
- Expand recognition of the complete 52-card symbol space and card orientation under alternate seat arrangements.
- Add numeric region detection for pot/call/stack amounts with a rejection metric; consider model-based OCR only after explicit validation.
- Reconcile card observations with `arc_vision.consistency` and `arc_vision.timeline`, then with math; simulate before device integration.
- Compile Android APK and test capture/latency on-device; separately test actual OpenAI API availability.

**No claims of autonomous 1win real-money gameplay or account-rule compliance.**
