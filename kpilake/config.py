"""Every simulation constant lives here, nowhere else.

Plant and product names are illustrative contrast-media manufacturing
entities chosen to match the shape of a real three-plant contrast-media
network (an EU plant, a Benelux plant, an APAC plant). They are not real
Bracco product codes or real production data; this whole repo runs on a
synthetic generator (kpilake/simulate.py), seeded and reproducible.
"""

SEED = 20260615

# Three plants, matching the JD's "three-plant contrast-media supply chain".
PLANTS = [
    {"plant_id": "PLT-IT", "name": "Ceriano Laghetto Site", "region": "EMEA"},
    {"plant_id": "PLT-NL", "name": "Geleen Site", "region": "EMEA"},
    {"plant_id": "PLT-SG", "name": "Singapore Site", "region": "APAC"},
]
PLANT_IDS = [p["plant_id"] for p in PLANTS]

# Six illustrative contrast-media SKUs across two chemistry families.
PRODUCTS = [
    {"product_id": "CM-IOD-A", "family": "Iodinated", "base_unit": "vials", "batch_yield_units": 42000},
    {"product_id": "CM-IOD-B", "family": "Iodinated", "base_unit": "vials", "batch_yield_units": 38000},
    {"product_id": "CM-GAD-A", "family": "Gadolinium-based", "base_unit": "vials", "batch_yield_units": 26000},
    {"product_id": "CM-GAD-B", "family": "Gadolinium-based", "base_unit": "vials", "batch_yield_units": 24000},
    {"product_id": "CM-BAR-A", "family": "Barium-based", "base_unit": "bottles", "batch_yield_units": 30000},
    {"product_id": "CM-BAR-B", "family": "Barium-based", "base_unit": "bottles", "batch_yield_units": 28000},
]
PRODUCT_IDS = [p["product_id"] for p in PRODUCTS]

# Three business units, assigned by customer region (independent of which
# plant fulfils the order, since any plant can ship to any region). This is
# the row-level-security dimension (kpilake/rls.py, powerbi/rls.md).
BUSINESS_UNITS = ["Diagnostic Imaging EMEA", "Diagnostic Imaging APAC", "Diagnostic Imaging Americas"]
REGION_TO_BU = {
    "EMEA": "Diagnostic Imaging EMEA",
    "APAC": "Diagnostic Imaging APAC",
    "Americas": "Diagnostic Imaging Americas",
}
CUSTOMER_REGION_WEIGHTS = {"EMEA": 0.46, "APAC": 0.29, "Americas": 0.25}

N_CUSTOMERS = 260
N_ORDER_LINES = 1_200_000
N_MONTHS = 24  # month index 0..23, an abstract 2-year horizon, not calendar dates

# Batches: sized so ~40 order lines draw from each batch on average.
LINES_PER_BATCH_TARGET = 40
N_BATCHES = N_ORDER_LINES // LINES_PER_BATCH_TARGET  # 30,000

# Delivery transit days by (plant region, customer region) pair.
TRANSIT_DAYS = {
    ("EMEA", "EMEA"): 3,
    ("EMEA", "APAC"): 12,
    ("EMEA", "Americas"): 9,
    ("APAC", "EMEA"): 13,
    ("APAC", "APAC"): 4,
    ("APAC", "Americas"): 15,
}

# Promised lead time (order date -> promised date), days, by product family.
# Calibrated to the realistic total fulfillment cycle this simulator itself
# produces (manufacture + release + pick/pack + typical transit), plus a
# margin, not picked independently of it. Three genuine attempts:
# attempt 1 (18/24/14 days) undershot the simulator's own cycle time by
# roughly 10 days, producing a near-impossible promise and a 0.28% OTIF;
# attempt 2 (30/35/27) matched the mean cycle time almost exactly, which
# is a coin flip by construction (49.15% on-time-delivery, mean promise
# gap approximately zero); attempt 3 (below) adds a further ~5-day margin
# so the promise is normally achievable but strained plant-months and
# batch deviations still cause real, discoverable misses. See README
# Findings for the full narrative and the measurement that discriminated
# each attempt.
PROMISED_LEAD_DAYS = {"Iodinated": 35, "Gadolinium-based": 40, "Barium-based": 32}

# Batch manufacturing cycle time base (days), by product family.
BATCH_MFG_DAYS_BASE = {"Iodinated": 11, "Gadolinium-based": 16, "Barium-based": 8}
# Batch release (QC/release lag after manufacture ends), days, base.
BATCH_RELEASE_DAYS_BASE = 5.0

# RLS role -> business unit mapping used by kpilake/rls.py and documented
# in powerbi/rls.md as the DAX row-level-security role assignment.
RLS_ROLE_TO_BU = {
    "bu_emea_analyst": "Diagnostic Imaging EMEA",
    "bu_apac_analyst": "Diagnostic Imaging APAC",
    "bu_americas_analyst": "Diagnostic Imaging Americas",
}

MAX_ATTEMPTS = 3
