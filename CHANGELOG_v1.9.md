## v1.9 — Connection Resilience
- Add read-only local Android observation backoff (p95, consecutive error classification, 3-success recovery).
- Add bounded transport-aware Python network health diagnostics and 8 new unit tests.
- Wire backoff into existing Android fast mode, retaining restrictions, existing frame quality, and stale/superseded result checks.
- Add read-only private-repo GitHub Actions Python CI recipe (not deployed).
- Add synthetic/offline benchmark; no real API requests or monetary operations.
- Preserve original v1.8 sources as separate artifact for multi-step rollback.
