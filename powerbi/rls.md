# Row-level security by business unit

Power BI Desktop is not installed on this build machine, so this role
cannot be assigned or tested inside a live `.pbix`. What is real: the
identical filter logic is implemented in `kpilake/rls.py` and exercised
against the same gold fact table by `tests/test_rls.py` (role isolation,
no leakage, filtered totals sum to the unfiltered total).

## Role definition (as it would be entered in Power BI Desktop's
Modeling > Manage Roles)

A `UserBUMapping` table maps a user principal name to exactly one
business unit:

| UserPrincipalName | BusinessUnit |
|---|---|
| bu_emea_analyst | Diagnostic Imaging EMEA |
| bu_apac_analyst | Diagnostic Imaging APAC |
| bu_americas_analyst | Diagnostic Imaging Americas |

Role filter on `fact_order_line_gold`:

```
[business_unit] = LOOKUPVALUE(
    UserBUMapping[BusinessUnit],
    UserBUMapping[UserPrincipalName],
    USERPRINCIPALNAME()
)
```

## What `kpilake/rls.py` actually tests

`apply_rls(fact_order_line_gold, role)` filters the gold fact table to
`business_unit == RLS_ROLE_TO_BU[role]`, the same mapping as
`UserBUMapping` above. `tests/test_rls.py` checks, on the built gold
table: (1) each role sees only its own business unit's rows, never
another's; (2) the three roles' filtered counts sum exactly to the
unfiltered total (no row is silently dropped or double-counted); (3) an
unknown role is rejected. This is the isolation property RLS exists to
guarantee, tested at the data-filter layer that Power BI's own RLS
engine would apply, even though the `.pbix` itself was not built.
