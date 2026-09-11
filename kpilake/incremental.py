"""Incremental refresh vs full rebuild of the gold star schema.

Full rebuild reprocesses every month_index partition of silver into gold.
Incremental refresh reprocesses only the most recent month_index partition
and overwrites just that partition (Spark's dynamic partition overwrite
mode), leaving the other 23 months' gold partitions untouched. This is
the same idea Power BI's own incremental refresh policy uses (refresh
only the current period's partition), applied here at the Spark layer
that feeds it.
"""
from __future__ import annotations

import os
import time

from pyspark.sql import SparkSession

from kpilake.gold import build_fact_batch_gold, build_fact_order_line_gold


def _write_partitioned(df, dst: str, mode_dynamic: bool = False):
    writer = df.write.mode("overwrite").partitionBy("month_index")
    if mode_dynamic:
        writer = writer.option("partitionOverwriteMode", "dynamic")
    writer.parquet(dst)


def full_rebuild(spark: SparkSession, silver_dir: str, gold_dir: str) -> float:
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "static")
    t0 = time.perf_counter()
    fact_order_line_silver = spark.read.parquet(os.path.join(silver_dir, "fact_order_line_silver"))
    fact_batch_silver = spark.read.parquet(os.path.join(silver_dir, "fact_batch_silver"))
    dim_customer = spark.read.parquet(os.path.join(silver_dir, "dim_customer"))

    fact_order_line_gold = build_fact_order_line_gold(fact_order_line_silver, dim_customer)
    fact_batch_gold = build_fact_batch_gold(fact_batch_silver)

    _write_partitioned(fact_order_line_gold, os.path.join(gold_dir, "fact_order_line_gold"))
    _write_partitioned(fact_batch_gold, os.path.join(gold_dir, "fact_batch_gold"))
    spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold")).count()
    return time.perf_counter() - t0


def incremental_refresh(spark: SparkSession, silver_dir: str, gold_dir: str, month_index: int) -> float:
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    t0 = time.perf_counter()
    fact_order_line_silver = spark.read.parquet(
        os.path.join(silver_dir, "fact_order_line_silver")
    ).filter(f"month_index = {month_index}")
    fact_batch_silver = spark.read.parquet(os.path.join(silver_dir, "fact_batch_silver")).filter(
        f"month_index = {month_index}"
    )
    dim_customer = spark.read.parquet(os.path.join(silver_dir, "dim_customer"))

    fact_order_line_gold = build_fact_order_line_gold(fact_order_line_silver, dim_customer)
    fact_batch_gold = build_fact_batch_gold(fact_batch_silver)

    _write_partitioned(fact_order_line_gold, os.path.join(gold_dir, "fact_order_line_gold"), mode_dynamic=True)
    _write_partitioned(fact_batch_gold, os.path.join(gold_dir, "fact_batch_gold"), mode_dynamic=True)
    spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold")).filter(
        f"month_index = {month_index}"
    ).count()
    return time.perf_counter() - t0
