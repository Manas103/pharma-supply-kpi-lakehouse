"""The 9 conformed KPI measures, computed exactly once here and reused by
every grouping (global, by plant, by business unit, by month) the same
way a DAX measure is written once and reused across report pages
(powerbi/measures.dax mirrors these definitions 1:1 in DAX syntax).
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

MEASURE_NAMES = [
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


def compute_order_line_measures(fact_order_line_gold: DataFrame) -> dict:
    row = fact_order_line_gold.agg(
        (F.avg(F.col("otif").cast("double")) * 100).alias("otif_pct"),
        (F.sum("qty_shipped") / F.sum("qty_ordered") * 100).alias("order_fill_rate_pct"),
        (F.avg(F.col("on_time_delivery").cast("double")) * 100).alias("on_time_delivery_pct"),
        (F.avg(F.col("in_full_delivery").cast("double")) * 100).alias("in_full_delivery_pct"),
        (F.avg(F.col("backorder").cast("double")) * 100).alias("backorder_rate_pct"),
        F.count("*").alias("n_order_lines"),
    ).collect()[0]
    return row.asDict()


def compute_batch_measures(fact_batch_gold: DataFrame) -> dict:
    row = fact_batch_gold.agg(
        (F.avg(F.col("right_first_time").cast("double")) * 100).alias("rft_pct"),
        F.avg("batch_mfg_cycle_days").alias("batch_mfg_cycle_days"),
        F.avg("batch_release_cycle_days").alias("batch_release_cycle_days"),
        (F.avg(F.col("deviation_flag").cast("double")) * 100).alias("deviation_rate_per_100_batches"),
        F.count("*").alias("n_batches"),
    ).collect()[0]
    return row.asDict()


def compute_all_measures(fact_order_line_gold: DataFrame, fact_batch_gold: DataFrame) -> dict:
    out = {}
    out.update(compute_order_line_measures(fact_order_line_gold))
    out.update(compute_batch_measures(fact_batch_gold))
    return out


def compute_by_group(fact_order_line_gold: DataFrame, fact_batch_gold: DataFrame, group_col: str):
    """Report-page-style breakdown (e.g. by plant_id or business_unit), same measures."""
    ol = fact_order_line_gold.groupBy(group_col).agg(
        (F.avg(F.col("otif").cast("double")) * 100).alias("otif_pct"),
        (F.sum("qty_shipped") / F.sum("qty_ordered") * 100).alias("order_fill_rate_pct"),
        (F.avg(F.col("on_time_delivery").cast("double")) * 100).alias("on_time_delivery_pct"),
        (F.avg(F.col("in_full_delivery").cast("double")) * 100).alias("in_full_delivery_pct"),
        (F.avg(F.col("backorder").cast("double")) * 100).alias("backorder_rate_pct"),
        F.count("*").alias("n_order_lines"),
    )
    bt = None
    if group_col in ("plant_id",):
        bt = fact_batch_gold.groupBy(group_col).agg(
            (F.avg(F.col("right_first_time").cast("double")) * 100).alias("rft_pct"),
            F.avg("batch_mfg_cycle_days").alias("batch_mfg_cycle_days"),
            F.avg("batch_release_cycle_days").alias("batch_release_cycle_days"),
            (F.avg(F.col("deviation_flag").cast("double")) * 100).alias("deviation_rate_per_100_batches"),
            F.count("*").alias("n_batches"),
        )
    return ol, bt
