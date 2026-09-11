"""Diffs the gold-layer PySpark measures against the independent DuckDB
oracle, exact (to floating-point noise). Requires data/gold_measures.json
to exist (run scripts/run_pipeline.py first). Writes docs/oracle_diff_output.txt.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle.recompute_measures import recompute

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("KPILAKE_DATA_DIR", os.path.join(ROOT, "data"))
RAW_DIR = os.path.join(DATA_DIR, "raw")
GOLD_MEASURES_PATH = os.path.join(DATA_DIR, "gold_measures.json")
DOCS_DIR = os.path.join(ROOT, "docs")

MEASURE_KEYS = [
    "otif_pct",
    "rft_pct",
    "batch_mfg_cycle_days",
    "batch_release_cycle_days",
    "order_fill_rate_pct",
    "on_time_delivery_pct",
    "in_full_delivery_pct",
    "deviation_rate_per_100_batches",
    "backorder_rate_pct",
]


def main():
    with open(GOLD_MEASURES_PATH) as f:
        gold = json.load(f)
    oracle = recompute(RAW_DIR)

    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log("=== oracle diff: gold (PySpark) vs independent oracle (DuckDB SQL) ===")
    max_abs_diff = 0.0
    all_exact = True
    for key in MEASURE_KEYS:
        g = float(gold[key])
        o = float(oracle[key])
        diff = abs(g - o)
        max_abs_diff = max(max_abs_diff, diff)
        ok = diff < 1e-9
        all_exact = all_exact and ok
        log(f"{key}: gold={g!r} oracle={o!r} abs_diff={diff:.2e} exact={ok}")

    log(f"n_order_lines gold={gold['n_order_lines']} oracle={oracle['n_order_lines']}")
    log(f"n_batches gold={gold['n_batches']} oracle={oracle['n_batches']}")
    log(f"max abs diff across all 9 measures: {max_abs_diff:.2e}")
    log(f"all 9 measures diffed exact: {all_exact}")

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "oracle_diff_output.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log("wrote docs/oracle_diff_output.txt")

    if not all_exact:
        sys.exit(1)


if __name__ == "__main__":
    main()
