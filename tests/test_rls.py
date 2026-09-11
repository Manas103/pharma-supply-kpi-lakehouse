import pytest

from kpilake.config import RLS_ROLE_TO_BU
from kpilake.rls import apply_rls


def test_rls_role_sees_only_its_own_business_unit(gold_tables):
    fact = gold_tables["fact_order_line_gold"]
    for role, bu in RLS_ROLE_TO_BU.items():
        filtered = apply_rls(fact, role)
        distinct_bus = [r["business_unit"] for r in filtered.select("business_unit").distinct().collect()]
        assert distinct_bus in ([], [bu]), f"role {role} leaked rows outside {bu}: saw {distinct_bus}"


def test_rls_filtered_totals_sum_to_the_unfiltered_total(gold_tables):
    fact = gold_tables["fact_order_line_gold"]
    total = fact.count()
    summed = sum(apply_rls(fact, role).count() for role in RLS_ROLE_TO_BU)
    assert summed == total


def test_rls_unknown_role_rejected(gold_tables):
    fact = gold_tables["fact_order_line_gold"]
    with pytest.raises(ValueError):
        apply_rls(fact, "not_a_real_role")
