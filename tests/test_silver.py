from kpilake import config


def test_silver_fact_order_line_has_no_duplicate_order_ids(silver_tables):
    fact = silver_tables["fact_order_line_silver"]
    n = fact.count()
    n_distinct = fact.select("order_id").distinct().count()
    assert n == n_distinct


def test_silver_fact_batch_has_no_duplicate_batch_ids(silver_tables):
    fact = silver_tables["fact_batch_silver"]
    n = fact.count()
    n_distinct = fact.select("batch_id").distinct().count()
    assert n == n_distinct


def test_silver_referential_integrity_customer(silver_tables):
    fact = silver_tables["fact_order_line_silver"]
    dim_customer = silver_tables["dim_customer"]
    orphans = fact.join(dim_customer, "customer_id", "left_anti")
    assert orphans.count() == 0


def test_silver_referential_integrity_plant_and_product(silver_tables):
    fact = silver_tables["fact_order_line_silver"]
    rows = fact.select("plant_id", "product_id").distinct().collect()
    for r in rows:
        assert r["plant_id"] in config.PLANT_IDS
        assert r["product_id"] in config.PRODUCT_IDS


def test_silver_quantity_invariant(silver_tables):
    fact = silver_tables["fact_order_line_silver"]
    bad = fact.filter("qty_shipped > qty_ordered or qty_ordered <= 0 or qty_shipped < 0")
    assert bad.count() == 0


def test_silver_batch_cycle_time_columns_nonnegative(silver_tables):
    fact = silver_tables["fact_batch_silver"]
    bad = fact.filter("batch_mfg_cycle_days < 0 or batch_release_cycle_days < 0")
    assert bad.count() == 0


def test_dim_business_unit_has_three_rows(silver_tables):
    assert silver_tables["dim_business_unit"].count() == 3
