"""Silver layer: clean, deduplicate, conform to dimensions, enforce referential integrity.

Grain: one row per order line in ``fact_order_line_silver``, one row per
batch in ``fact_batch_silver``. Both are joined against conformed
dimensions (``dim_plant``, ``dim_product``, ``dim_customer``,
``dim_business_unit``) built here, once, and reused by every downstream
gold table and measure.
"""
from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from kpilake import config


def build_dimensions(spark: SparkSession, bronze: dict[str, DataFrame]) -> dict[str, DataFrame]:
    dim_plant = spark.createDataFrame(config.PLANTS)
    dim_product = spark.createDataFrame(config.PRODUCTS)
    dim_business_unit = spark.createDataFrame(
        [{"business_unit": bu} for bu in config.BUSINESS_UNITS]
    )
    dim_customer = (
        bronze["raw_customers"]
        .dropDuplicates(["customer_id"])
        .select("customer_id", "region", "business_unit")
    )
    n_days = config.N_MONTHS * 30
    dim_date = spark.range(0, n_days).withColumnRenamed("id", "day_index").withColumn(
        "month_index", (F.col("day_index") / F.lit(30)).cast("int")
    )
    return {
        "dim_plant": dim_plant,
        "dim_product": dim_product,
        "dim_business_unit": dim_business_unit,
        "dim_customer": dim_customer,
        "dim_date": dim_date,
    }


def build_fact_batch_silver(bronze: dict[str, DataFrame]) -> DataFrame:
    b = bronze["raw_batches"].dropDuplicates(["batch_id"])
    # Referential integrity: every batch must reference a known plant and product.
    b = b.filter(F.col("plant_id").isin(config.PLANT_IDS) & F.col("product_id").isin(config.PRODUCT_IDS))
    b = b.withColumn("batch_mfg_cycle_days", F.col("batch_mfg_end_day") - F.col("batch_start_day"))
    b = b.withColumn("batch_release_cycle_days", F.col("batch_release_day") - F.col("batch_mfg_end_day"))
    b = b.withColumn("month_index", (F.col("batch_start_day") / F.lit(30)).cast("int"))
    return b


def build_fact_order_line_silver(
    bronze: dict[str, DataFrame], dims: dict[str, DataFrame], fact_batch_silver: DataFrame
) -> DataFrame:
    orders = bronze["raw_orders"].dropDuplicates(["order_id"])
    shipments = bronze["raw_shipments"].dropDuplicates(["order_id"])
    link = bronze["raw_order_batch_link"].dropDuplicates(["order_id"])

    known_customers = dims["dim_customer"].select("customer_id")
    known_batches = fact_batch_silver.select(F.col("batch_id").alias("_known_batch_id"))

    fact = (
        orders.join(shipments, "order_id", "inner")
        .join(link, "order_id", "inner")
        .join(known_customers, "customer_id", "inner")  # referential integrity: drop orphan customer refs
        .join(known_batches, F.col("batch_id") == F.col("_known_batch_id"), "inner")
        .drop("_known_batch_id")
    )
    fact = fact.filter(
        F.col("plant_id").isin(config.PLANT_IDS)
        & F.col("product_id").isin(config.PRODUCT_IDS)
        & (F.col("qty_ordered") > 0)
        & (F.col("qty_shipped") >= 0)
        & (F.col("qty_shipped") <= F.col("qty_ordered"))
    )
    fact = fact.withColumn("month_index", (F.col("order_date_day") / F.lit(30)).cast("int"))
    return fact


def build_silver(spark: SparkSession, bronze_dir: str, silver_dir: str) -> dict[str, DataFrame]:
    from kpilake.bronze import read_bronze

    bronze = read_bronze(spark, bronze_dir)
    # Bronze's ingestion marker is per-source metadata, not a conformed
    # column; joining raw_orders and raw_shipments (each carrying their own
    # _ingested_at_run) without dropping it first collides on write. Drop it
    # here, once, rather than in every downstream join.
    bronze = {name: df.drop("_ingested_at_run") for name, df in bronze.items()}
    dims = build_dimensions(spark, bronze)
    fact_batch = build_fact_batch_silver(bronze)
    fact_order_line = build_fact_order_line_silver(bronze, dims, fact_batch)

    os.makedirs(silver_dir, exist_ok=True)
    tables = {**dims, "fact_batch_silver": fact_batch, "fact_order_line_silver": fact_order_line}
    out = {}
    for name, df in tables.items():
        dst = os.path.join(silver_dir, name)
        if name in ("fact_batch_silver", "fact_order_line_silver"):
            df.write.mode("overwrite").partitionBy("month_index").parquet(dst)
        else:
            df.write.mode("overwrite").parquet(dst)
        out[name] = spark.read.parquet(dst)
    return out
