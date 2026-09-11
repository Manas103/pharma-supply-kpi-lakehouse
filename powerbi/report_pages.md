# Report pages

Six pages, all built on the one star schema (`star_schema.md`) and the
nine measures written once in `measures.dax`. No page redefines a
measure; every page only changes filters, visuals and grouping.

1. **Executive OTIF Scorecard.** Card visuals for `OTIF %`, `Order Fill
   Rate %`, `On-Time Delivery %`, `In-Full Delivery %` at the top,
   trended by `dim_date[month_index]` below. The one page a non-analyst
   reader opens first.
2. **Plant Performance.** All nine measures broken out by `dim_plant`,
   matrix visual, conditional formatting against a target column.
   Sourced from the same `measures_by_plant_order_line.csv` /
   `measures_by_plant_batch.csv` breakdown `scripts/run_pipeline.py`
   writes.
3. **Right-First-Time and Quality.** `Right-First-Time %` and `Deviation
   Rate (per 100 batches)` by plant and product family, with a QC-result
   breakdown (`Pass` / `Conditional Pass` / `Fail`) from `fact_batch_gold`.
4. **Batch Cycle Time Trend.** `Avg Batch Manufacturing Cycle Time` and
   `Avg Batch Release Cycle Time` trended by month, split by plant, to
   show where release (QC/paperwork) lag rather than manufacturing
   itself is the bottleneck.
5. **Fill Rate and Backorders.** `Order Fill Rate %` and `Backorder Rate
   %` by plant and product, with a drill-through to the order-line grain
   for the current filter context.
6. **Business Unit Drilldown.** The same nine measures sliced by
   `dim_business_unit`, the page the row-level-security role in `rls.md`
   restricts: a `bu_emea_analyst` signed in against this page sees only
   `Diagnostic Imaging EMEA` rows.
