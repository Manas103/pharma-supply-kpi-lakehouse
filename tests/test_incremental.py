import os

from kpilake.incremental import full_rebuild, incremental_refresh


def test_incremental_refresh_preserves_total_row_count(spark, test_data_dir, silver_tables):
    silver_dir = str(test_data_dir / "silver")
    gold_dir = str(test_data_dir / "gold_incr_test")

    full_rebuild(spark, silver_dir, gold_dir)
    total_after_full = spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold")).count()

    latest_month = (
        spark.read.parquet(os.path.join(silver_dir, "fact_order_line_silver"))
        .agg({"month_index": "max"})
        .collect()[0][0]
    )
    incremental_refresh(spark, silver_dir, gold_dir, latest_month)
    total_after_incremental = spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold")).count()

    assert total_after_incremental == total_after_full


def test_incremental_refresh_only_rewrites_the_target_partition(spark, test_data_dir, silver_tables):
    silver_dir = str(test_data_dir / "silver")
    gold_dir = str(test_data_dir / "gold_incr_test2")

    full_rebuild(spark, silver_dir, gold_dir)
    other_month_before = (
        spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold"))
        .filter("month_index = 0")
        .count()
    )

    latest_month = (
        spark.read.parquet(os.path.join(silver_dir, "fact_order_line_silver"))
        .agg({"month_index": "max"})
        .collect()[0][0]
    )
    assert latest_month != 0
    incremental_refresh(spark, silver_dir, gold_dir, latest_month)

    other_month_after = (
        spark.read.parquet(os.path.join(gold_dir, "fact_order_line_gold"))
        .filter("month_index = 0")
        .count()
    )
    assert other_month_after == other_month_before
