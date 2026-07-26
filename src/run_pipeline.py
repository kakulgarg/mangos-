"""
Single entrypoint -- runs the whole pipeline in order and fails loudly.

    python run_pipeline.py            # full pipeline
    python run_pipeline.py --from clean   # resume from a step

Each step is a module with a main(); they share config and the SQLite DB, so
running them in sequence reproduces every figure, table, and JSON artefact from
the raw Agmarknet exports in data/01_source.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time

from logging_config import get_logger

log = get_logger("pipeline")

# Ordered pipeline. Each entry is (module, human label).
STEPS = [
    ("parse_agmarknet", "Parse Agmarknet exports -> interim tables"),
    ("load_db", "Load interim tables -> SQLite (as sourced)"),
    ("clean", "Clean + feature-engineer -> clean tables + audit"),
    ("run_sql", "Run analytical SQL -> query CSVs"),
    ("eda", "Exploration -> 6 figures + findings"),
    ("model", "Explanatory OLS -> coefficients + diagnostics"),
    ("forecast", "Monthly forecaster -> next-month CSV + backtest"),
    ("build_extracts", "Dashboard extracts -> dashboard/data"),
    ("build_dashboard_html", "Interactive web dashboard -> dashboard/mandi_dashboard.html"),
]


def run(from_step: str | None) -> None:
    names = [s[0] for s in STEPS]
    start = names.index(from_step) if from_step else 0
    if from_step and from_step not in names:
        sys.exit(f"Unknown step '{from_step}'. Choices: {names}")

    log.info("=" * 60)
    log.info("Mandi Price Watch pipeline -- %d steps", len(STEPS) - start)
    log.info("=" * 60)
    t0 = time.time()
    for module_name, label in STEPS[start:]:
        log.info(">>> %s", label)
        step_t = time.time()
        try:
            mod = importlib.import_module(module_name)
            mod.main()
        except Exception:  # noqa: BLE001 -- surface which step broke, then re-raise
            log.exception("Pipeline FAILED at step '%s'", module_name)
            raise
        log.info("<<< %s done in %.1fs\n", module_name, time.time() - step_t)
    log.info("Pipeline complete in %.1fs.", time.time() - t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run the Mandi Price Watch pipeline.")
    ap.add_argument("--from", dest="from_step", default=None,
                    help="Resume from this step (module name).")
    run(ap.parse_args().from_step)
