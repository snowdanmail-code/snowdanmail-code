# AI Remote Control GPT v1.0 — mathematical core + temporal scene verification

**Build type:** incremental source release over v0.9. Not an Android APK, not a deployed GPT model, not a verified 1win automator.

## New, separate modules

- `server/arc_poker_math/holdem.py`: deterministic independent No-Limit Texas Hold'em five/seven card rank, all nine hand categories, seven-card showdown ranking, exact river equity against a uniformly random two-card opponent, reproducible Monte Carlo estimates before the river, mathematical pot-odds and highly simplified EV example. **No betting decisions** and **no live action**. Does not support Omaha.
- `server/arc_vision/consistency.py`: cross-checks of typed observations for duplicate cards, board sizes, variant mismatches, replay/disconnect/overlay and inconsistent active controls. Rejects inconsistent data; does not recognize JPEG itself.
- `server/arc_vision/timeline.py`: tracks one hand across provided frame observations; rejects inconsistent streets/board/hero cards, pauses after an overlay or connection loss and requires a new stable observation. No taps.
- `POST /math/equity`: token-protected, read-only API with hard cap of 2,500 Monte Carlo samples, strictly typed inputs. Reuses existing backend and does not require a GPT API key. Other existing HTTP endpoints are preserved.
- `server/tests/test_poker_math.py`, `server/tests/test_timeline.py` new regression tests.
- `examples/offline_completed_hands.json`: three card-combination examples manually taken from previously supplied screenshots. These **do not** evaluate the user's play.

## Observations and limitations

1. Equity **vs uniformly random** cards is not equity against a real opponent's range. The sample EV excludes rake, future betting, multiway action, stack dynamics and opponent adaptation. It cannot substantiate a professional winrate.
2. The new checker consumes **structured card strings**, not screen pixels. A real JPEG card/value recognizer with measured false-positive/false-negative rates is **not yet implemented**; earlier visual hints are not sufficient.
3. A programmatic HTTP math request proves neither that the Android client works nor that a neural model can correctly perceive a screenshot.
4. No Android build, no real OpenAI API call, and no live real-money poker session was tested.
5. Existing v0.9 archive's anonymization warning still applies: fixture JPGs contain opponents' nicknames/avatars. Do not publish the dataset.
6. Replay analysis remains disallowed during an active table session; existing post-session policy applies. Betting automation remains off in this release.

## Tests

```shell
cd server
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'
```

The release was verified in this container: **217/217 tests passed**. These are offline server, contract and invariant tests, not evidence of Android integration or live model accuracy.

## Example: read-only math endpoint

Set `ARC_DEVICE_TOKEN` on the server (random private string with >=12 characters). Local-only server by default.

```http
POST /math/equity
X-Device-Token: YOUR_LOCAL_SECRET
Content-Type: application/json

{"request":"math_equity","hero_cards":["Qc","Qs"],"board_cards":["Qd","2s","Ks","4c","Kc"],"samples":100,"seed":42}
```

No gesture, button, bet or deposit instruction is returned. The river result enumerates 990 possible villain hands exactly, irrespective of the `samples` field.

## Next measured milestones

- Build a gold-standard, user-reviewed screenshot benchmark with per-card and per-amount labels; measure precision, recall and abstention on genuinely unseen frames.
- Implement a replaceable image-reader adapter; confirm GPT API model, key, cost and end-to-end latency on real-device captures.
- Integrate structured observations with `arc_vision.consistency` and `arc_vision.timeline` without changing the public Android protocol.
- Retain rollback checkpoints; compare regression metrics before selecting a new recognizer.
- Compile and validate a signed Android APK on the actual phone. No claim of full autonomy until separately tested.
