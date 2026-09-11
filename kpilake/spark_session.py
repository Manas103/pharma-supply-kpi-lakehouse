"""Local Spark session builder, capped per this repo's resource-courtesy rule.

No Databricks workspace exists on this build machine, so every stage below
runs against PySpark's local[*] mode rather than a Databricks cluster; see
the README's "Honest framing" section. The number of cores used is capped
to half of what WSL2 reports, per playbook section 3z, not the full core
count.
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession


def build_spark(app_name: str = "pharma-supply-kpi-lakehouse", cores: int | None = None) -> SparkSession:
    if cores is None:
        cpu_count = os.cpu_count() or 4
        cores = max(1, cpu_count // 2)
    master = f"local[{cores}]"
    return (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", str(max(4, cores * 2)))
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
