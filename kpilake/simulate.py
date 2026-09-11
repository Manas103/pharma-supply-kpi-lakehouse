"""Generates the five raw source extracts this lakehouse ingests.

Everything here is synthetic and reproducible from ``config.SEED``. The
generator is deliberately correlated, not independent noise per row: a
batch's QC outcome (``deviation_count``, ``qc_result``) drives the
fulfilment outcome of every order line drawn from that batch, and a
per-(plant, month) "capacity strain" factor drives both manufacturing
cycle time and deviation probability that month. This is what makes the
measured KPIs below (README, "Findings") show a real, discoverable
pattern (a strained plant-month) rather than flat noise around a mean.

Five raw extracts are written, one per simulated source system:
  raw_customers   (CRM)
  raw_batches     (MES / QC)
  raw_orders      (OMS)
  raw_shipments   (WMS)
  raw_order_batch_link (MES, which batch fulfilled which order line)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from kpilake import config


def _rng() -> np.random.Generator:
    return np.random.default_rng(config.SEED)


def simulate_customers(rng: np.random.Generator, n: int = config.N_CUSTOMERS) -> pd.DataFrame:
    regions = list(config.CUSTOMER_REGION_WEIGHTS.keys())
    weights = np.array(list(config.CUSTOMER_REGION_WEIGHTS.values()))
    region = rng.choice(regions, size=n, p=weights)
    business_unit = np.array([config.REGION_TO_BU[r] for r in region])
    return pd.DataFrame(
        {
            "customer_id": [f"CUST-{i:05d}" for i in range(n)],
            "region": region,
            "business_unit": business_unit,
        }
    )


def simulate_batches(
    rng: np.random.Generator, n: int = config.N_BATCHES, n_months: int = config.N_MONTHS
) -> tuple[pd.DataFrame, np.ndarray]:
    """Returns (raw_batches, capacity_strain[plant_idx, month]) for reuse by order generation."""
    plant_weights = np.array([0.40, 0.35, 0.25])  # IT, NL, SG: relative plant size
    plant_idx = rng.choice(len(config.PLANT_IDS), size=n, p=plant_weights)
    plant_id = np.array(config.PLANT_IDS)[plant_idx]

    product_idx = rng.integers(0, len(config.PRODUCT_IDS), size=n)
    product_id = np.array(config.PRODUCT_IDS)[product_idx]
    family = np.array([config.PRODUCTS[i]["family"] for i in product_idx])

    month = rng.integers(0, n_months, size=n)
    day_in_month = rng.integers(0, 28, size=n)
    batch_start_day = month * 30 + day_in_month  # abstract day-index calendar

    # Per (plant, month) capacity strain, shared by every batch and every
    # order line touching that plant-month: N_PLANTS x N_MONTHS matrix in
    # [0, 1], right-skewed so most plant-months are calm and a few are hot.
    strain_matrix = rng.beta(1.5, 6.0, size=(len(config.PLANT_IDS), n_months))
    strain = strain_matrix[plant_idx, month]

    mfg_base = np.array([config.BATCH_MFG_DAYS_BASE[f] for f in family])
    mfg_days = mfg_base * (1.0 + 0.35 * strain) + rng.normal(0, 0.8, size=n)
    mfg_days = np.clip(mfg_days, 2.0, None)
    batch_mfg_end_day = batch_start_day + mfg_days

    deviation_prob = np.clip(0.05 + 0.28 * strain, 0.0, 0.85)
    deviation_count = rng.poisson(deviation_prob * 1.4)
    qc_result = np.where(
        deviation_count == 0,
        "Pass",
        np.where(deviation_count <= 2, "Conditional Pass", "Fail"),
    )

    release_base = config.BATCH_RELEASE_DAYS_BASE * (1.0 + 0.45 * strain)
    rework_delay = np.where(deviation_count > 0, deviation_count * rng.uniform(2.0, 4.5, size=n), 0.0)
    release_days = release_base + rework_delay + rng.normal(0, 0.6, size=n)
    release_days = np.clip(release_days, 1.0, None)
    batch_release_day = batch_mfg_end_day + release_days

    rft = (deviation_count == 0) & (qc_result == "Pass")

    df = pd.DataFrame(
        {
            "batch_id": [f"BATCH-{i:06d}" for i in range(n)],
            "plant_id": plant_id,
            "product_id": product_id,
            "batch_start_day": batch_start_day.astype("int32"),
            "batch_mfg_end_day": batch_mfg_end_day.astype("float64"),
            "batch_release_day": batch_release_day.astype("float64"),
            "qc_result": qc_result,
            "deviation_count": deviation_count.astype("int32"),
            "right_first_time": rft,
        }
    )
    return df, strain_matrix


def simulate_orders_shipments(
    rng: np.random.Generator,
    batches: pd.DataFrame,
    customers: pd.DataFrame,
    n_order_lines: int = config.N_ORDER_LINES,
    lines_per_batch_target: int = config.LINES_PER_BATCH_TARGET,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Explodes each batch into ~lines_per_batch_target order lines, correlated with that batch's QC outcome.

    Returns (raw_orders, raw_shipments, raw_order_batch_link).
    """
    n_batches = len(batches)
    # A multinomial allocation over Poisson-shaped weights guarantees the
    # per-batch counts sum to exactly n_order_lines (some batches can land
    # on 0 order lines, which is fine, rather than the earlier "adjust only
    # the last batch" approach, which under-corrected when the last batch's
    # own count was smaller than the required correction; see Findings in
    # the README for the concrete number that surfaced this).
    weights = rng.poisson(lines_per_batch_target, size=n_batches).astype("float64") + 0.1
    proportions = weights / weights.sum()
    lines_per_batch = rng.multinomial(n_order_lines, proportions)

    batch_row_idx = np.repeat(np.arange(n_batches), lines_per_batch)
    n = len(batch_row_idx)
    assert n == n_order_lines, f"order line count drifted: {n} != {n_order_lines}"

    plant_id = batches["plant_id"].to_numpy()[batch_row_idx]
    product_id = batches["product_id"].to_numpy()[batch_row_idx]
    batch_id = batches["batch_id"].to_numpy()[batch_row_idx]
    batch_start_day = batches["batch_start_day"].to_numpy()[batch_row_idx]
    batch_release_day = batches["batch_release_day"].to_numpy()[batch_row_idx]
    deviation_count = batches["deviation_count"].to_numpy()[batch_row_idx]

    plant_region = {p["plant_id"]: p["region"] for p in config.PLANTS}
    plant_region_arr = np.array([plant_region[p] for p in plant_id])

    family_by_product = {p["product_id"]: p["family"] for p in config.PRODUCTS}
    family = np.array([family_by_product[p] for p in product_id])
    lead_days = np.array([config.PROMISED_LEAD_DAYS[f] for f in family])

    yield_by_product = {p["product_id"]: p["batch_yield_units"] for p in config.PRODUCTS}
    typical_qty = np.array([yield_by_product[p] for p in product_id]) / lines_per_batch_target
    qty_ordered = np.round(rng.lognormal(mean=np.log(typical_qty), sigma=0.35)).astype("int64")
    qty_ordered = np.clip(qty_ordered, 1, None)

    customer_idx = rng.integers(0, len(customers), size=n)
    customer_id = customers["customer_id"].to_numpy()[customer_idx]
    customer_region = customers["region"].to_numpy()[customer_idx]

    order_date_day = batch_start_day - rng.integers(0, 6, size=n)
    order_date_day = np.clip(order_date_day, 0, None)
    promised_date_day = order_date_day + lead_days + rng.normal(0, 1.2, size=n)

    # Fulfilment risk rises with the fulfilling batch's own deviation count.
    shortfall_prob = np.clip(0.04 + 0.06 * deviation_count, 0.0, 0.6)
    backorder_prob = np.clip(0.01 + 0.03 * deviation_count, 0.0, 0.35)
    u = rng.uniform(size=n)
    is_backorder = u < backorder_prob
    is_partial = (~is_backorder) & (u < backorder_prob + shortfall_prob)

    shortfall_frac = rng.uniform(0.10, 0.60, size=n)
    qty_shipped = np.where(
        is_backorder,
        0,
        np.where(is_partial, np.round(qty_ordered * (1 - shortfall_frac)).astype("int64"), qty_ordered),
    )
    qty_shipped = np.clip(qty_shipped, 0, qty_ordered)

    pick_pack_days = rng.uniform(1.0, 3.0, size=n)
    ship_variability = rng.normal(0, 1.0, size=n)
    ship_date_day = batch_release_day + pick_pack_days + ship_variability
    ship_date_day = np.where(qty_shipped == 0, np.nan, ship_date_day)

    transit = np.array(
        [config.TRANSIT_DAYS[(plant_region_arr[i], customer_region[i])] for i in range(n)]
    )
    delivery_date_day = ship_date_day + transit + rng.normal(0, 0.7, size=n)

    order_id = np.array([f"ORD-{i:08d}" for i in range(n)])

    raw_orders = pd.DataFrame(
        {
            "order_id": order_id,
            "plant_id": plant_id,
            "product_id": product_id,
            "customer_id": customer_id,
            "order_date_day": order_date_day.astype("int32"),
            "promised_date_day": promised_date_day.astype("float64"),
            "qty_ordered": qty_ordered.astype("int64"),
        }
    )
    raw_shipments = pd.DataFrame(
        {
            "order_id": order_id,
            "ship_date_day": ship_date_day,
            "delivery_date_day": delivery_date_day,
            "qty_shipped": qty_shipped.astype("int64"),
        }
    )
    raw_order_batch_link = pd.DataFrame({"order_id": order_id, "batch_id": batch_id})
    return raw_orders, raw_shipments, raw_order_batch_link


def generate_all(
    n_customers: int = config.N_CUSTOMERS,
    n_batches: int = config.N_BATCHES,
    n_months: int = config.N_MONTHS,
    n_order_lines: int = config.N_ORDER_LINES,
) -> dict[str, pd.DataFrame]:
    rng = _rng()
    customers = simulate_customers(rng, n=n_customers)
    batches, _strain = simulate_batches(rng, n=n_batches, n_months=n_months)
    orders, shipments, link = simulate_orders_shipments(
        rng, batches, customers, n_order_lines=n_order_lines
    )
    return {
        "raw_customers": customers,
        "raw_batches": batches,
        "raw_orders": orders,
        "raw_shipments": shipments,
        "raw_order_batch_link": link,
    }


def write_raw(out_dir: str, **generate_kwargs) -> dict[str, str]:
    import os

    os.makedirs(out_dir, exist_ok=True)
    tables = generate_all(**generate_kwargs)
    paths = {}
    for name, df in tables.items():
        path = os.path.join(out_dir, f"{name}.parquet")
        df.to_parquet(path, index=False)
        paths[name] = path
    return paths


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    written = write_raw(out)
    for name, path in written.items():
        print(f"{name}: {path}")
