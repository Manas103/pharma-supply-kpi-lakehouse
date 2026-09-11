"""Gold layer: the star schema this repo's Power BI semantic model is built on.

``fact_order_line_gold`` and ``fact_batch_gold`` add the row-level flags
every measure in ``kpilake/measures.py`` aggregates. No flag here is
itself a measure; DAX (and this module's Spark equivalent) always
aggregates a flag or a quantity column, never hardcodes a percentage,
which is what "measures written once, reused across report pages" means
in practice (powerbi/measures.dax).

Definitions (also stated in powerbi/star_schema.md and the README):
  on_time_delivery:  order was shipped and delivered_date_day <= promised_date_day.
                      A never-shipped (backordered) line is NOT on time.
  in_full_delivery:  qty_shipped >= qty_ordered (any amount shipped, even if late).
  otif:               on_time_delivery AND in_full_delivery.
  backorder:           qty_shipped == 0, i.e. nothing at all has shipped.
                       This is the complement of "any amount shipped", which is a
                       strictly narrower condition than "not in_full" (a line that
                       shipped a partial quantity is not in_full but is also not
                       a backorder under this definition).
"""
from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def build_fact_order_line_gold(fact_order_line_silver: DataFrame, dim_customer: DataFrame) -> DataFrame:
    df = fact_order_line_silver.join(
        dim_customer.select("customer_id", "business_unit"), "customer_id", "left"
    )
    df = df.withColumn("shipped", F.col("qty_shipped") > 0)
    df = df.withColumn(
        "on_time_delivery",
        F.col("shipped") & (F.col("delivery_date_day") <= F.col("promised_date_day")),
    )
    df = df.withColumn("in_full_delivery", F.col("qty_shipped") >= F.col("qty_ordered"))
    df = df.withColumn("otif", F.col("on_time_delivery") & F.col("in_full_delivery"))
    df = df.withColumn("backorder", F.col("qty_shipped") == 0)
    return df


def build_fact_batch_gold(fact_batch_silver: DataFrame) -> DataFrame:
    df = fact_batch_silver.withColumn("deviation_flag", F.col("deviation_count") > 0)
    return df


def build_gold(spark: SparkSession, silver_dir: str, gold_dir: str) -> dict[str, DataFrame]:
    fact_order_line_silver = spark.read.parquet(os.path.join(silver_dir, "fact_order_line_silver"))
    fact_batch_silver = spark.read.parquet(os.path.join(silver_dir, "fact_batch_silver"))
    dim_customer = spark.read.parquet(os.path.join(silver_dir, "dim_customer"))

    fact_order_line_gold = build_fact_order_line_gold(fact_order_line_silver, dim_customer)
    fact_batch_gold = build_fact_batch_gold(fact_batch_silver)

    os.makedirs(gold_dir, exist_ok=True)
    out = {}
    for name, df in [
        ("fact_order_line_gold", fact_order_line_gold),
        ("fact_batch_gold", fact_batch_gold),
    ]:
        dst = os.path.join(gold_dir, name)
        df.write.mode("overwrite").partitionBy("month_index").parquet(dst)
        out[name] = spark.read.parquet(dst)

    # Dimensions pass through gold unchanged, copied so gold is self-contained.
    for dim_name in ["dim_plant", "dim_product", "dim_business_unit", "dim_customer", "dim_date"]:
        src = os.path.join(silver_dir, dim_name)
        dst = os.path.join(gold_dir, dim_name)
        spark.read.parquet(src).write.mode("overwrite").parquet(dst)
        out[dim_name] = spark.read.parquet(dst)
    return out
