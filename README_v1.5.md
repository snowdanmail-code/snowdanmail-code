# AI Remote Control GPT v1.5 — Deadline & RTT Telemetry

**Stage:** Offline/laboratory source release. Not a working Android APK and not a real-money poker automation release.

## Problem solved

The previous Android source sent `remaining_ms=10000` as a **fabricated training timer** on the `/fast/observe` route. This could mislead future runtime logic into believing a game clock was actually observed.

In v1.5 the Android uploader sends **JSON null** until a validated OCR/visual timer exists. The server accepts `null` for **read-only observation**; the turn-cue tracker returns `TIMER_UNVERIFIED` no matter how stable the button colors look. Other malformed values (bool, negative, huge) remain rejected. A missing timer never authorizes an action.

## New independent modules

- `server/arc_turn/deadlines.py`: `LatencyEnvelope`, bounded p95 measurements for six phases (capture, uplink, vision, model, downlink, verify) and a conservative non-authoritative advisory. With incomplete samples or an unknown game timer it returns `LATENCY_UNCALIBRATED` / `TIMER_UNVERIFIED`; it never authorizes wagering or UI actions.
- `android/.../LatencyWindow.kt`: bounded, thread-safe RTT p95 telemetry from *actual HTTP round trips* measured by Android elapsed realtime clock. 50 sample default window; no network/mock timing assumptions.
- `server/arc_fastloop/observe.py`: measured local vision time fed into the envelope; `deadline_advice` and `timer_status` included only as safety annotations. Note the server does NOT know Android network or GPT latency from these measurements.
- `server/arc_fastloop/gate.py` and `server/arc_turn/timeline.py`: optional unknown timer for observation only, preserving stale frame and ordering guards.
- `android/.../CaptureService.kt`: sends `remaining_ms = null`, shows measured RTT and p95; replaces inaccurate text implying timer was measured.

## Verified checks

- Python: `cd server && python -m unittest discover -s tests -q` — **274 passed** on the development machine.
- Kotlin pure-unit latency test: compile `LatencyWindow.kt` and `LatencyWindowTest.kt` with `kotlinc` — **passed**.
- Existing Kotlin frame-selection tests — **7 passed**.
- Server HTTP test `/fast/observe` for a missing game timer — **passed**, returned no action.
- Release ZIP integrity and hashes — checked during packaging.

## Not tested or not implemented

- Visual OCR and independent validation of the real 1win timer.
- Mobile p50/p95 networking latency, end-to-end GPT and Android touch timing (no Android device attached).
- Android APK build or MediaProjection capture on a physical device.
- Full use of all six actual measured latency phases; most are unmeasured, so the budget cannot be declared safe.
- Real-money bet placement, real-time autonomous operation, anti-bot evasion. There are **no new wager actions** in v1.5.

## Next work package v1.6

Create an isolated replay/timer benchmark from **anonymized recorded clips**. Establish a verified timer read or explicit unknown; timestamp scene changes, time captured-to-upload, RTT, model latency when API is permitted, and completion checks. Validate by replaying known frames against a non-wagering training application. Only then evaluate feasibility of a response within the observed clock.

## GitHub

The GitHub identity is authenticated, but no repository or GitHub App installation is yet accessible. This ZIP remains the source of truth until a private repository with access is verified. Never upload API secrets, personal recordings, full screenshots with usernames, or live account data to source control.
