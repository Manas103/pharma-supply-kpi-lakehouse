import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)

from kpilake import simulate  # noqa: E402
from kpilake.bronze import ingest_to_bronze  # noqa: E402
from kpilake.gold import build_gold  # noqa: E402
from kpilake.silver import build_silver  # noqa: E402
from kpilake.spark_session import build_spark  # noqa: E402

# Small, fast test-scale sizes, independent of the full 1.2M-row build.
TEST_N_CUSTOMERS = 40
TEST_N_BATCHES = 60
TEST_N_MONTHS = 6
TEST_N_ORDER_LINES = 2400


@pytest.fixture(scope="session")
def spark():
    s = build_spark(app_name="pharma-supply-kpi-lakehouse-tests", cores=2)
    yield s
    s.stop()


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("kpilake_test_data")
    raw_dir = d / "raw"
    simulate.write_raw(
        str(raw_dir),
        n_customers=TEST_N_CUSTOMERS,
        n_batches=TEST_N_BATCHES,
        n_months=TEST_N_MONTHS,
        n_order_lines=TEST_N_ORDER_LINES,
    )
    return d


@pytest.fixture(scope="session")
def bronze_tables(spark, test_data_dir):
    bronze_dir = str(test_data_dir / "bronze")
    return ingest_to_bronze(spark, str(test_data_dir / "raw"), bronze_dir)


@pytest.fixture(scope="session")
def silver_tables(spark, test_data_dir, bronze_tables):
    silver_dir = str(test_data_dir / "silver")
    bronze_dir = str(test_data_dir / "bronze")
    return build_silver(spark, bronze_dir, silver_dir)


@pytest.fixture(scope="session")
def gold_tables(spark, test_data_dir, silver_tables):
    gold_dir = str(test_data_dir / "gold")
    silver_dir = str(test_data_dir / "silver")
    return build_gold(spark, silver_dir, gold_dir)
