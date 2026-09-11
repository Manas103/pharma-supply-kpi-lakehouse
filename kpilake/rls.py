"""Row-level security by business unit, emulated and unit-tested.

Power BI Desktop is not installed on this build machine (see README,
"Honest framing"), so the RLS role documented in powerbi/rls.md cannot be
exercised inside Power BI itself. This module implements the identical
filter logic the documented DAX RLS role uses,
``[BusinessUnit] = LOOKUPVALUE(UserBUMapping[BusinessUnit],
UserBUMapping[UserPrincipalName], USERPRINCIPALNAME())``, against the
same gold fact table, so the isolation property (a role sees only its
own business unit, and nothing else) is genuinely tested even though the
.pbix file itself is not built.
"""
from __future__ import annotations

from pyspark.sql import DataFrame

from kpilake.config import RLS_ROLE_TO_BU


def apply_rls(fact_order_line_gold: DataFrame, role: str) -> DataFrame:
    if role not in RLS_ROLE_TO_BU:
        raise ValueError(f"unknown RLS role: {role}")
    bu = RLS_ROLE_TO_BU[role]
    return fact_order_line_gold.filter(fact_order_line_gold.business_unit == bu)
