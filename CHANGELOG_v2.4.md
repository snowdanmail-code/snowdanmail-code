# v2.4 — Read-only Android↔Server RTT Diagnostic

- Added authenticated, read-only `GET /diagnostics/ping` with explicit non-action response.
- Added Android button for six timed HTTP probes plus one warm-up, no screenshots or GPT.
- Added pure Kotlin `RttSummary` median / nearest-rank p95 and safety-oriented status.
- Added four server HTTP tests and one Kotlin/JVM test suite.
- Extended offline smoke test with auth and non-action assertions.
- Corrected Windows APK scripts from stale v2.1 to v2.4 artifact names.
- Hardened Android preflight with version consistency checks and a regression test.
- No Android APK produced or tested; external game actions remain disabled.
