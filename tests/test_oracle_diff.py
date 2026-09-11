from kpilake.measures import compute_all_measures
from oracle.recompute_measures import recompute

TOLERANCE = 1e-9


def test_oracle_matches_gold_exactly_on_all_nine_measures(test_data_dir, gold_tables):
    gold = compute_all_measures(gold_tables["fact_order_line_gold"], gold_tables["fact_batch_gold"])
    oracle = recompute(str(test_data_dir / "raw"))

    keys = [
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
    for key in keys:
        assert abs(float(gold[key]) - float(oracle[key])) < TOLERANCE, key
    assert gold["n_order_lines"] == oracle["n_order_lines"]
    assert gold["n_batches"] == oracle["n_batches"]
