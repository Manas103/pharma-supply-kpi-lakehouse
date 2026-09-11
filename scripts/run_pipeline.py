"""End-to-end: simulate -> bronze -> silver -> gold -> measures -> powerbi exports.

Writes docs/benchmark_output.txt with every measured number and
data/gold_measures.json for the oracle-diff script to compare against.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kpilake import config, simulate
from kpilake.bronze import ingest_to_bronze
from kpilake.gold import build_gold
from kpilake.measures import compute_all_measures, compute_by_group
from kpilake.silver import build_silver
from kpilake.spark_session import build_spark

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("KPILAKE_DATA_DIR", os.path.join(ROOT, "data"))
RAW_DIR = os.path.join(DATA_DIR, "raw")
BRONZE_DIR = os.path.join(DATA_DIR, "bronze")
SILVER_DIR = os.path.join(DATA_DIR, "silver")
GOLD_DIR = os.path.join(DATA_DIR, "gold")
DOCS_DIR = os.path.join(ROOT, "docs")
POWERBI_DIR = os.path.join(ROOT, "powerbi")


def main():
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log(f"=== pharma-supply-kpi-lakehouse pipeline run ===")
    log(f"target order lines: {config.N_ORDER_LINES}")

    t0 = time.perf_counter()
    written = simulate.write_raw(RAW_DIR)
    t_sim = time.perf_counter() - t0
    import pyarrow.parquet as pq

    for name, path in written.items():
        n = pq.ParquetFile(path).metadata.num_rows
        log(f"raw source {name}: {n} rows -> {path}")
    log(f"simulation wall time: {t_sim:.2f}s")

    spark = build_spark()
    try:
        t0 = time.perf_counter()
        bronze = ingest_to_bronze(spark, RAW_DIR, BRONZE_DIR)
        t_bronze = time.perf_counter() - t0
        log(f"bronze ingest wall time: {t_bronze:.2f}s")
        for name, df in bronze.items():
            log(f"bronze.{name}: {df.count()} rows")

        t0 = time.perf_counter()
        silver = build_silver(spark, BRONZE_DIR, SILVER_DIR)
        t_silver = time.perf_counter() - t0
        log(f"silver build wall time: {t_silver:.2f}s")
        n_ol_silver = silver["fact_order_line_silver"].count()
        n_batch_silver = silver["fact_batch_silver"].count()
        log(f"silver.fact_order_line_silver: {n_ol_silver} rows (raw had {config.N_ORDER_LINES})")
        log(f"silver.fact_batch_silver: {n_batch_silver} rows (raw had {config.N_BATCHES})")
        log(f"referential-integrity drop: {config.N_ORDER_LINES - n_ol_silver} order lines dropped")

        t0 = time.perf_counter()
        gold = build_gold(spark, SILVER_DIR, GOLD_DIR)
        t_gold = time.perf_counter() - t0
        log(f"gold build wall time: {t_gold:.2f}s")

        measures = compute_all_measures(gold["fact_order_line_gold"], gold["fact_batch_gold"])
        log("")
        log("=== 9 conformed KPI measures (gold layer, PySpark) ===")
        for k, v in measures.items():
            log(f"{k}: {v}")

        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "gold_measures.json"), "w") as f:
            json.dump(measures, f, indent=2, default=str)

        # Report-page-style breakdown by plant, exported for Power BI (small CSVs).
        ol_by_plant, batch_by_plant = compute_by_group(
            gold["fact_order_line_gold"], gold["fact_batch_gold"], "plant_id"
        )
        os.makedirs(POWERBI_DIR, exist_ok=True)
        ol_by_plant.toPandas().to_csv(os.path.join(POWERBI_DIR, "measures_by_plant_order_line.csv"), index=False)
        batch_by_plant.toPandas().to_csv(os.path.join(POWERBI_DIR, "measures_by_plant_batch.csv"), index=False)
        log("")
        log("measures by plant written to powerbi/measures_by_plant_order_line.csv and measures_by_plant_batch.csv")

        # Small dimension exports for the documented Power BI star schema.
        gold["dim_plant"].toPandas().to_csv(os.path.join(POWERBI_DIR, "dim_plant.csv"), index=False)
        gold["dim_product"].toPandas().to_csv(os.path.join(POWERBI_DIR, "dim_product.csv"), index=False)
        gold["dim_business_unit"].toPandas().to_csv(os.path.join(POWERBI_DIR, "dim_business_unit.csv"), index=False)
        sample = gold["fact_order_line_gold"].limit(500).toPandas()
        sample.to_csv(os.path.join(POWERBI_DIR, "fact_gold_sample.csv"), index=False)
        log("dim_plant.csv, dim_product.csv, dim_business_unit.csv, fact_gold_sample.csv written to powerbi/")

    finally:
        spark.stop()

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "benchmark_output.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log("")
    log("wrote docs/benchmark_output.txt")


if __name__ == "__main__":
    main()
