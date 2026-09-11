"""Bronze layer: PySpark ingests the five raw source extracts as-landed.

Bronze does the minimum a real landing zone does: read the source file,
attach an ingestion timestamp, and partition by the field a real ingestion
job would partition by, with no cleaning, deduplication or type
correction (that is silver's job, kpilake/silver.py). This mirrors the
medallion pattern the JD names, run locally rather than on a Databricks
workspace; see README "Honest framing".
"""
from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

RAW_TABLES = ["raw_customers", "raw_batches", "raw_orders", "raw_shipments", "raw_order_batch_link"]

# partition column per bronze table, "" means no partitioning (small dim source)
BRONZE_PARTITION_COL = {
    "raw_customers": None,
    "raw_batches": "plant_id",
    "raw_orders": "plant_id",
    "raw_shipments": None,
    "raw_order_batch_link": None,
}


def ingest_to_bronze(spark: SparkSession, raw_dir: str, bronze_dir: str) -> dict[str, DataFrame]:
    os.makedirs(bronze_dir, exist_ok=True)
    out = {}
    for table in RAW_TABLES:
        src = os.path.join(raw_dir, f"{table}.parquet")
        df = spark.read.parquet(src).withColumn("_ingested_at_run", F.lit(1))
        dst = os.path.join(bronze_dir, table)
        part_col = BRONZE_PARTITION_COL[table]
        writer = df.write.mode("overwrite")
        if part_col:
            writer = writer.partitionBy(part_col)
        writer.parquet(dst)
        out[table] = spark.read.parquet(dst)
    return out


def read_bronze(spark: SparkSession, bronze_dir: str) -> dict[str, DataFrame]:
    return {table: spark.read.parquet(os.path.join(bronze_dir, table)) for table in RAW_TABLES}
