# Changelog

## [2.0] — 2026-07-25 — Real data + forecasting

Rebuilt the project on the **real 25-month Agmarknet dataset** (33k rows, 111
markets) and added a **next-month price forecaster**.

### Added
- Monthly per-mandi **forecaster** (`src/forecast.py`): persistence and
  seasonal-naive baselines, a LightGBM lag-feature model, and a hybrid ensemble
  with quantile **prediction intervals** and feature-importance interpretability.
- **Variety** dimension end to end (parser → DB → SQL Q7 → dashboard extract):
  answers "which onion category pays best, by month".
- Single **entrypoint** `run_pipeline.py` (full pipeline ≈ 20s).
- **pytest** suite (`tests/`, 9 cases) — parser, cleaning, forecaster leakage.
- Shared **logging** (`logging_config.py`) replacing `print`.
- Numbered data layers (`01_source`/`02_interim`/`03_processed`), `data/README.md`,
  `LICENSE`, pinned `requirements.txt`, architecture diagram in the README.

### Changed
- Parser keeps variety, converts arrivals **tonnes → quintals**, canonicalises
  market names, and assigns **stable name-keyed IDs** (not coverage-rank).
- Cleaning **computes** its audit verdicts (the missingness verdict now correctly
  reports *non-random* on the real data).
- Explanatory OLS now uses **HAC robust standard errors**; curated-market scope.
- Memo PDF is **rendered from the Markdown**, so the two cannot drift.

### Honest findings (see `ai_appendix` M5–M6)
- The synthetic-data "Simpson's paradox" **did not replicate**; reframed F2–F4 to
  the real finding (a mandi's own arrivals barely predict its price).
- The ML forecaster **ties** a naive persistence baseline; the ensemble edges it
  and adds a calibrated interval. Reported plainly rather than dressed up.

### Fixed
- `market_summary` no longer silently empties on NaN districts.
- Dashboard accuracy figures read from JSON instead of being hardcoded.
- `run_sql` handles `Q10+`; SQL scope dates corrected to the real span.

## [1.0] — Synthetic-data scaffold (superseded)
Initial pipeline built and validated on the scaffold's synthetic sample data.
