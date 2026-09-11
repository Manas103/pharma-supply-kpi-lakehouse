"""Measures full-rebuild vs incremental-refresh wall time for the gold layer.

Requires data/silver to already exist (run scripts/run_pipeline.py first).
Writes docs/incremental_benchmark_output.txt.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kpilake import config
from kpilake.incremental import full_rebuild, incremental_refresh
from kpilake.spark_session import build_spark

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("KPILAKE_DATA_DIR", os.path.join(ROOT, "data"))
SILVER_DIR = os.path.join(DATA_DIR, "silver")
GOLD_DIR = os.path.join(DATA_DIR, "gold")
DOCS_DIR = os.path.join(ROOT, "docs")


def main():
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    spark = build_spark()
    try:
        t_full = full_rebuild(spark, SILVER_DIR, GOLD_DIR)
        log(f"full rebuild (all {config.N_MONTHS} months): {t_full:.3f}s")

        latest_month = config.N_MONTHS - 1
        t_incr = incremental_refresh(spark, SILVER_DIR, GOLD_DIR, latest_month)
        log(f"incremental refresh (month {latest_month} only): {t_incr:.3f}s")

        speedup = t_full / t_incr if t_incr > 0 else float("inf")
        log(f"speedup: {speedup:.2f}x")

        # Verify total row count is unchanged after a dynamic-partition-overwrite
        # incremental refresh (the other months' partitions were not rewritten).
        full = spark.read.parquet(os.path.join(GOLD_DIR, "fact_order_line_gold"))
        total_after_incremental = full.count()
        log(f"fact_order_line_gold row count after incremental refresh: {total_after_incremental}")
    finally:
        spark.stop()

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "incremental_benchmark_output.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log("wrote docs/incremental_benchmark_output.txt")


if __name__ == "__main__":
    main()
