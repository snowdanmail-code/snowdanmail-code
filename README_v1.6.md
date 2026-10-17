# AI Remote Control GPT v1.6 — Stopwatch Cue (research only)

This version builds on v1.5, retains the earlier version-registry and read-only vision/maths modules, and adds the independently replaceable `arc_turn.stopwatch.StopwatchCue` component.

## Measured improvements

- A local crop of a stopwatch icon (no usernames or face imagery) is the first offline reference template.
- A normalized ROI detector matches stopwatch presence across the two Android resolutions tested: 709×1536 and 1080×2340.
- In 10 previously supplied screenshots, it identified a visible stopwatch icon in two images; eight others yielded no reliable stopwatch icon. This is a narrow, **non-independent** dataset and is NOT a timer-recognition accuracy metric.
- Scene blocks for replay, menu, showdown, disconnect and overlays return `BLOCKED_SCENE`.
- Fast observer now emits a `stopwatch_cue` field on a fresh observation.
- `seconds_remaining` stays **null** in every response. Presence of an icon does not prove there are 30 seconds remaining, nor that it is our turn.

## Tests and status

```
cd server && python -m unittest discover -s tests -q
```

279 Python unit/server tests passed. The independent Kotlin checks from v1.5 passed and remain unchanged in this source archive. The complete output is summarized in `BENCHMARK_STOPWATCH_v1.6.json`.

Not verified: actual countdown digits, other UI themes, cropped/occluded clock behavior outside these frames, Android APK, OpenAI API, wireless latency, real-game actions. No new touch or wager action was implemented.

## Next module v1.7

Collect a larger anonymized, time-aligned sample of actual countdown values and explicit occlusion labels from recordings; train/calibrate an abstaining timer digit reader, evaluate separately across different hands/recordings. Then measure real on-device end-to-end latency, rather than extrapolating from server CPU processing alone.

## Source control

GitHub username authenticated, but no repositories are available to the GitHub integration. Do not upload personal source recordings, player profiles, full personal screenshots or API secrets without auditing them. Existing previous ZIP checkpoints must remain immutable.
