# AI Remote Control GPT v1.9 — Connection Resilience

**Status:** offline-tested source release, based on v1.8. Android APK not built; no real OpenAI API/1win real-money operation tested. No external repository received code in this release.

## Problem

The previous phone uploader used a fixed retry delay, even when a connection experienced repeated timeouts or large p95 round-trip times. Short rapid retries under poor connectivity can waste device resources and send observations that arrive too late to be useful.

## New modules

### Phone — `ObservationBackoff.kt`

- Local, consent-based **read-only screenshot observation** pacing. On success, updates an RTT window; on failure, reduces polling frequency.
- `UNCALIBRATED` while fewer than 10 good RTT samples are available; observing every 1000 ms.
- `HEALTHY` only with adequate samples, no recent failures and p95 up to 1800 ms; observing every 500 ms.
- `DEGRADED` when a failure occurs or p95 > 1800 ms; observing every 1500 ms.
- `UNRELIABLE` after 3 consecutive failures or p95 > 3500 ms; observing every 5000 ms.
- After 3 failures, **3 consecutive successes** are required before leaving the recovery state. The policy resets its RTT sample history if the transport changes (Wi-Fi ↔ cellular). Pacing never increases beyond 2 FPS, and actual observations are still protected by `FastCapturePolicy` and the existing `ClientTraceWindow`.
- `CaptureService.kt` uses the policy in fast/local observation mode only. No automatic monetary touch is authorized.

### Server — `arc_telemetry/link_health.py`

- A separate, bounded, thread-safe **offline monitoring** component for recorded RTT/sequence/outcome data.
- Rejects duplicate/out-of-order sequences and clock regressions; holds at most 64 RTT samples by default; reports p50/p95/p99.
- Independently tracks a network recovery streak, transport changes, and an observation interval recommendation. Stores **no screenshots, cards, balances or player identifiers**.
- Safe for unit tests and replay analysis, not used as permission to interact with third-party apps.

## Real-time implications

These thresholds are provisional engineering values, **not guarantees of responding before the 1win timer expires**. The timer icon's «30 с» / «60 с» is **not** a verified remaining-time countdown; no action is allowed based on it. Local RTT pacing cannot determine whether a strategic decision is correct. Under bad network conditions the system performs fewer observation attempts rather than trying to catch up via stale requests.

## Reproducible offline test

```bash
cd server
python -m unittest discover -s tests -q
cd ../android
kotlinc app/src/main/java/com/example/airemote/ObservationBackoff.kt tests_fast/ObservationBackoffTest.kt -include-runtime -d /tmp/backoff.jar
java -jar /tmp/backoff.jar
cd ..
python benchmark_link_health_v19.py
```

`BENCHMARK_v1.9.json` shows **CPU time of pure Python bookkeeping and SYNTHETIC sample RTTs**. It is *not* a live measurement of network, GPT, Android capture, or full end-to-end latency.

## Delivery and safety gates

- `money_actions_enabled=false`; no instructions to bypass bot detection.
- Requires explicit Android MediaProjection permission for any capture.
- Does not copy personal screen recordings or secrets into GitHub CI; full video files aren't included here.
- Offline source tests do not imply a successful Gradle build or on-device validation. Android SDK is absent from this environment.
- Previous archives v1.8 and earlier remain separately available for rollback.

## Next stage (v2.0 candidate)

Build/debug-install the Android app on a device with Android SDK, then measure actual p50/p95/p99 of capture→reply on Wi-Fi and mobile data. Until verified, keep use limited to read-only diagnostics and local simulations. If GitHub repo permission becomes available, push *only reviewed code* to a private repo with CI and tags.
