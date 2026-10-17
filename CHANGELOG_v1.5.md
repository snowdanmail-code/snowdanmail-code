# v1.5

- REPLACE fictional 10-second game timer with nullable unknown state on fast uploader.
- ADD opt-in per-request measured round-trip time, bounded p95 monitoring in Android.
- ADD independent six-stage latency envelope; absence of telemetry means uncalibrated.
- ADD monotonic turn tracker fail-closed state `TIMER_UNVERIFIED`.
- ADD server `deadline_advice` safety annotations; never authorization.
- ADD HTTP and unit regression tests.
- PRESERVE previous vision, math, version registry and demo resources.
