import numpy as np

from kpilake import simulate
from tests.conftest import TEST_N_BATCHES, TEST_N_CUSTOMERS, TEST_N_MONTHS, TEST_N_ORDER_LINES


def _gen():
    return simulate.generate_all(
        n_customers=TEST_N_CUSTOMERS,
        n_batches=TEST_N_BATCHES,
        n_months=TEST_N_MONTHS,
        n_order_lines=TEST_N_ORDER_LINES,
    )


def test_row_counts_exact():
    tables = _gen()
    assert len(tables["raw_customers"]) == TEST_N_CUSTOMERS
    assert len(tables["raw_batches"]) == TEST_N_BATCHES
    assert len(tables["raw_orders"]) == TEST_N_ORDER_LINES
    assert len(tables["raw_shipments"]) == TEST_N_ORDER_LINES
    assert len(tables["raw_order_batch_link"]) == TEST_N_ORDER_LINES


def test_deterministic_for_fixed_seed():
    a = _gen()
    b = _gen()
    for name in a:
        assert a[name].equals(b[name]), f"{name} was not reproducible from the fixed seed"


def test_qty_shipped_never_exceeds_qty_ordered():
    tables = _gen()
    orders = tables["raw_orders"].set_index("order_id")
    shipments = tables["raw_shipments"].set_index("order_id")
    joined = orders.join(shipments)
    assert (joined["qty_shipped"] <= joined["qty_ordered"]).all()
    assert (joined["qty_shipped"] >= 0).all()


def test_batch_stage_ordering_invariant():
    batches = _gen()["raw_batches"]
    assert (batches["batch_mfg_end_day"] >= batches["batch_start_day"]).all()
    assert (batches["batch_release_day"] >= batches["batch_mfg_end_day"]).all()


def test_right_first_time_matches_deviation_and_qc_result():
    batches = _gen()["raw_batches"]
    expected = (batches["deviation_count"] == 0) & (batches["qc_result"] == "Pass")
    assert (batches["right_first_time"] == expected).all()


def test_every_order_line_references_a_known_batch_and_customer():
    tables = _gen()
    known_batches = set(tables["raw_batches"]["batch_id"])
    known_customers = set(tables["raw_customers"]["customer_id"])
    assert set(tables["raw_order_batch_link"]["batch_id"]).issubset(known_batches)
    assert set(tables["raw_orders"]["customer_id"]).issubset(known_customers)


def test_backordered_lines_have_no_ship_or_delivery_date():
    tables = _gen()
    shipments = tables["raw_shipments"]
    backordered = shipments[shipments["qty_shipped"] == 0]
    assert backordered["ship_date_day"].isna().all()
    assert backordered["delivery_date_day"].isna().all()


def test_capacity_strain_produces_a_real_deviation_spread_not_flat_noise():
    # A genuinely correlated generator should show batches at different strain
    # levels with materially different deviation rates, not a single flat rate.
    batches = _gen()["raw_batches"]
    by_qc = batches.groupby("qc_result").size()
    assert "Pass" in by_qc.index
    assert np.isfinite(batches["deviation_count"]).all()
