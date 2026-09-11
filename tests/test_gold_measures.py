from kpilake.measures import MEASURE_NAMES, compute_all_measures, compute_by_group


def test_all_nine_measures_present(gold_tables):
    result = compute_all_measures(gold_tables["fact_order_line_gold"], gold_tables["fact_batch_gold"])
    for name in MEASURE_NAMES:
        assert name in result
        assert result[name] is not None


def test_measures_are_in_plausible_ranges(gold_tables):
    result = compute_all_measures(gold_tables["fact_order_line_gold"], gold_tables["fact_batch_gold"])
    pct_fields = [
        "otif_pct",
        "rft_pct",
        "order_fill_rate_pct",
        "on_time_delivery_pct",
        "in_full_delivery_pct",
        "backorder_rate_pct",
    ]
    for f in pct_fields:
        assert 0.0 <= result[f] <= 100.0, f"{f}={result[f]} out of [0, 100]"
    assert result["batch_mfg_cycle_days"] > 0
    assert result["batch_release_cycle_days"] > 0


def test_otif_is_never_greater_than_either_component(gold_tables):
    fact = gold_tables["fact_order_line_gold"]
    bad = fact.filter("otif = true and (on_time_delivery = false or in_full_delivery = false)")
    assert bad.count() == 0


def test_backorder_flag_means_zero_shipped_quantity(gold_tables):
    fact = gold_tables["fact_order_line_gold"]
    bad = fact.filter("backorder = true and qty_shipped != 0")
    assert bad.count() == 0
    bad2 = fact.filter("backorder = false and qty_shipped = 0")
    assert bad2.count() == 0


def test_deviation_flag_matches_deviation_count(gold_tables):
    fact = gold_tables["fact_batch_gold"]
    bad = fact.filter("(deviation_flag = true) != (deviation_count > 0)")
    assert bad.count() == 0


def test_hand_computed_otif_fixture(spark):
    """Two rows worked out by hand: one OTIF, one late-and-short."""
    rows = [
        {"otif": True, "on_time_delivery": True, "in_full_delivery": True, "qty_shipped": 10, "qty_ordered": 10, "backorder": False},
        {"otif": False, "on_time_delivery": False, "in_full_delivery": False, "qty_shipped": 4, "qty_ordered": 10, "backorder": False},
    ]
    df = spark.createDataFrame(rows)
    from pyspark.sql import functions as F

    row = df.agg((F.avg(F.col("otif").cast("double")) * 100).alias("otif_pct")).collect()[0]
    assert row["otif_pct"] == 50.0


def test_compute_by_group_returns_one_row_per_plant(gold_tables):
    ol_by_plant, batch_by_plant = compute_by_group(
        gold_tables["fact_order_line_gold"], gold_tables["fact_batch_gold"], "plant_id"
    )
    assert ol_by_plant.count() == 3
    assert batch_by_plant.count() == 3
