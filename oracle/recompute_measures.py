"""Independent oracle: recomputes all 9 measures from the raw source
extracts directly, in DuckDB SQL, sharing no code with kpilake/bronze.py,
kpilake/silver.py, kpilake/gold.py or kpilake/measures.py (the PySpark
pipeline). This is the "every measure diffed exact against an independent
Python oracle" claim: two independently written implementations of the
same nine definitions, one in PySpark DataFrame calls, one in a single
SQL query, must agree to machine precision on the same input data.
"""
from __future__ import annotations

import duckdb

ORACLE_SQL = """
with orders as (
    select * from read_parquet(?)
),
shipments as (
    select * from read_parquet(?)
),
batches as (
    select *,
           batch_mfg_end_day - batch_start_day as batch_mfg_cycle_days,
           batch_release_day - batch_mfg_end_day as batch_release_cycle_days,
           deviation_count > 0 as deviation_flag
    from read_parquet(?)
    where plant_id in ('PLT-IT', 'PLT-NL', 'PLT-SG')
),
link as (
    select * from read_parquet(?)
),
customers as (
    select distinct customer_id, region, business_unit from read_parquet(?)
),
fact_order_line as (
    select o.order_id, o.plant_id, o.product_id, o.qty_ordered, o.promised_date_day,
           s.qty_shipped, s.delivery_date_day,
           (s.qty_shipped > 0) as shipped,
           (s.qty_shipped > 0 and s.delivery_date_day <= o.promised_date_day) as on_time_delivery,
           (s.qty_shipped >= o.qty_ordered) as in_full_delivery,
           (s.qty_shipped = 0) as backorder
    from orders o
    join shipments s on o.order_id = s.order_id
    join link l on o.order_id = l.order_id
    join customers c on o.customer_id = c.customer_id
    join batches b on l.batch_id = b.batch_id
    where o.qty_ordered > 0 and s.qty_shipped >= 0 and s.qty_shipped <= o.qty_ordered
      and o.plant_id in ('PLT-IT', 'PLT-NL', 'PLT-SG')
)
select
    100.0 * avg(case when on_time_delivery and in_full_delivery then 1.0 else 0.0 end) as otif_pct,
    100.0 * sum(qty_shipped) / sum(qty_ordered) as order_fill_rate_pct,
    100.0 * avg(case when on_time_delivery then 1.0 else 0.0 end) as on_time_delivery_pct,
    100.0 * avg(case when in_full_delivery then 1.0 else 0.0 end) as in_full_delivery_pct,
    100.0 * avg(case when backorder then 1.0 else 0.0 end) as backorder_rate_pct,
    count(*) as n_order_lines
from fact_order_line
"""

BATCH_ORACLE_SQL = """
with batches as (
    select *,
           batch_mfg_end_day - batch_start_day as batch_mfg_cycle_days,
           batch_release_day - batch_mfg_end_day as batch_release_cycle_days,
           deviation_count > 0 as deviation_flag,
           right_first_time
    from read_parquet(?)
    where plant_id in ('PLT-IT', 'PLT-NL', 'PLT-SG')
)
select
    100.0 * avg(case when right_first_time then 1.0 else 0.0 end) as rft_pct,
    avg(batch_mfg_cycle_days) as batch_mfg_cycle_days,
    avg(batch_release_cycle_days) as batch_release_cycle_days,
    100.0 * avg(case when deviation_flag then 1.0 else 0.0 end) as deviation_rate_per_100_batches,
    count(*) as n_batches
from batches
"""


def recompute(raw_dir: str) -> dict:
    con = duckdb.connect()
    ol_row = con.execute(
        ORACLE_SQL,
        [
            f"{raw_dir}/raw_orders.parquet",
            f"{raw_dir}/raw_shipments.parquet",
            f"{raw_dir}/raw_batches.parquet",
            f"{raw_dir}/raw_order_batch_link.parquet",
            f"{raw_dir}/raw_customers.parquet",
        ],
    ).fetchone()
    ol_cols = [d[0] for d in con.description]
    result = dict(zip(ol_cols, ol_row))

    batch_row = con.execute(BATCH_ORACLE_SQL, [f"{raw_dir}/raw_batches.parquet"]).fetchone()
    batch_cols = [d[0] for d in con.description]
    result.update(dict(zip(batch_cols, batch_row)))
    con.close()
    return result


if __name__ == "__main__":
    import json
    import sys

    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    print(json.dumps(recompute(raw_dir), indent=2, default=str))
