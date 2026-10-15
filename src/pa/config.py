"""Project-wide constants and paths."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_OLIST_DIR = DATA_DIR / "raw" / "olist"
RAW_CRITEO_DIR = DATA_DIR / "raw" / "criteo"
OLIST_DB = DATA_DIR / "olist.duckdb"
CRITEO_CSV_GZ = RAW_CRITEO_DIR / "criteo-uplift-v2.1.csv.gz"
# PA_CRITEO_PARQUET / PA_FIGURES_DIR let tests and smoke runs point elsewhere.
CRITEO_PARQUET = Path(
    os.environ.get("PA_CRITEO_PARQUET", DATA_DIR / "criteo_v2_1.parquet")
)
SQL_DIR = ROOT / "sql"
FIGURES_DIR = Path(os.environ.get("PA_FIGURES_DIR", ROOT / "reports" / "figures"))
# Pre-registered choices (tracked): written by notebook 02, read by notebook 03.
DESIGN_FILE = Path(
    os.environ.get("PA_DESIGN_FILE", ROOT / "docs" / "preregistration.json")
)

OLIST_KAGGLE_SLUG = "olistbr/brazilian-ecommerce"
# Official Criteo mirror; the go.criteo.net storage host no longer resolves (2026-10).
CRITEO_URL = (
    "https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/"
    "criteo-research-uplift-v2.1.csv.gz"
)

SEED = 42
ALPHA = 0.05
EXPECTED_TREATMENT_SHARE = 0.85
FEATURES = [f"f{i}" for i in range(12)]
