"""Download and build the two datasets.

Both datasets are CC BY-NC-SA 4.0 and are never committed (data/ is gitignored).

CLI:
    python -m pa.data download [--only olist|criteo]
    python -m pa.data build [--criteo-sample-frac 0.1] [--only olist|criteo]
"""

import argparse
import shutil
import sys
import urllib.request
import warnings
from pathlib import Path

import duckdb

from pa import config

OLIST_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Zip prefixes have leading zeros, so they must stay text.
OLIST_TEXT_COLUMNS = {
    "customers": {"customer_zip_code_prefix": "VARCHAR"},
    "geolocation": {"geolocation_zip_code_prefix": "VARCHAR"},
    "sellers": {"seller_zip_code_prefix": "VARCHAR"},
}

CRITEO_ROWS = 13_979_592
CRITEO_COLUMNS = 16  # f0..f11 + treatment, conversion, visit, exposure
CRITEO_REQUIRED = ["treatment", "conversion", "visit", "exposure"]


def download_olist(dest: Path | None = None) -> Path:
    """Download Olist via kagglehub into data/raw/olist (public dataset).

    If kagglehub asks for credentials, download the archive manually from
    https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and unzip the
    CSV files into data/raw/olist/.
    """
    import kagglehub

    dest = Path(dest or config.RAW_OLIST_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    if all((dest / f).exists() for f in OLIST_FILES.values()):
        print(f"already downloaded: {dest}")
        return dest
    kagglehub.dataset_download(config.OLIST_KAGGLE_SLUG, output_dir=str(dest))
    return dest


def download_criteo(dest: Path | None = None) -> Path:
    """Download Criteo Uplift v2.1 (about 297 MB gzip) into data/raw/criteo."""
    dest = Path(dest or config.CRITEO_CSV_GZ)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100_000_000:
        print(f"already downloaded: {dest}")
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(config.CRITEO_URL, timeout=60) as resp:
        with open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.rename(dest)
    print(f"downloaded {dest.stat().st_size / 1e6:.0f} MB to {dest}")
    return dest


def build_olist_db(raw_dir: Path | None = None, db_path: Path | None = None):
    """Load the 9 Olist CSV files into DuckDB tables and create the views.

    Returns an open connection. `db_path=None` builds an in-memory database
    (used by tests with the small fixture).
    """
    from pa.db import connect, load_sql

    raw_dir = Path(raw_dir or config.RAW_OLIST_DIR)
    if db_path is not None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(db_path).unlink(missing_ok=True)
    con = connect(db_path)
    for table, fname in OLIST_FILES.items():
        path = raw_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"missing {path}; run `python -m pa.data download`")
        types = OLIST_TEXT_COLUMNS.get(table)
        opts = "header = true"
        if types:
            pairs = ", ".join(f"'{k}': '{v}'" for k, v in types.items())
            opts += f", types = {{{pairs}}}"
        con.execute(
            f"CREATE TABLE {table} AS "
            f"SELECT * FROM read_csv('{path.as_posix()}', {opts})"
        )
    con.execute(load_sql("schema/olist_views"))
    return con


def build_criteo_parquet(
    csv_gz: Path | None = None,
    parquet: Path | None = None,
    sample_frac: float | None = None,
) -> Path:
    """Convert the Criteo CSV to compact parquet (float32 features, int8 flags).

    sample_frac (0..1) keeps a random subset for quick experiments; None keeps
    all rows.
    """
    csv_gz = Path(csv_gz or config.CRITEO_CSV_GZ)
    parquet = Path(parquet or config.CRITEO_PARQUET)
    if not csv_gz.exists():
        raise FileNotFoundError(f"missing {csv_gz}; run `python -m pa.data download`")
    con = duckdb.connect()
    cols = [
        r[0]
        for r in con.execute(
            f"DESCRIBE SELECT * FROM read_csv('{csv_gz.as_posix()}', header = true)"
        ).fetchall()
    ]
    missing = [c for c in CRITEO_REQUIRED if c not in cols]
    if missing:
        raise ValueError(f"unexpected Criteo header, missing {missing}: {cols}")
    select = ", ".join(
        f"CAST({c} AS TINYINT) AS {c}"
        if c in CRITEO_REQUIRED
        else f"CAST({c} AS FLOAT) AS {c}"
        for c in cols
    )
    sample = ""
    if sample_frac is not None:
        sample = f"USING SAMPLE {sample_frac * 100}% (bernoulli, {config.SEED})"
    parquet.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY (SELECT {select} FROM read_csv('{csv_gz.as_posix()}', header = true) "
        f"{sample}) TO '{parquet.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"
    )
    con.close()
    _check_criteo_parquet(parquet, csv_gz, full=sample_frac is None)
    return parquet


def _check_criteo_parquet(parquet: Path, csv_gz: Path, full: bool) -> None:
    """Sanity checks against the published key figures of v2.1."""
    size_mb = csv_gz.stat().st_size / 1e6
    if not 250 <= size_mb <= 350:
        warnings.warn(
            f"{csv_gz.name} is {size_mb:.0f} MB, the dataset page says about 297 MB",
            stacklevel=2,
        )
    chk = duckdb.connect()
    n_rows = chk.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet.as_posix()}')"
    ).fetchone()[0]
    n_cols = len(
        chk.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet.as_posix()}')"
        ).fetchall()
    )
    chk.close()
    if n_cols != CRITEO_COLUMNS:
        raise ValueError(f"expected {CRITEO_COLUMNS} columns, got {n_cols}")
    if full and n_rows != CRITEO_ROWS:
        raise ValueError(
            f"expected {CRITEO_ROWS:,} rows, got {n_rows:,}: "
            "incomplete download or a different file version?"
        )


def register_criteo(con, parquet: Path | str | None = None) -> None:
    """Create a view `criteo` over the parquet file (used by sql/ab/*.sql)."""
    parquet = Path(parquet or config.CRITEO_PARQUET)
    con.execute(
        f"CREATE OR REPLACE VIEW criteo AS "
        f"SELECT * FROM read_parquet('{parquet.as_posix()}')"
    )


def register_segment(con, feature: str) -> None:
    """Create a view `criteo_segments` exposing one feature as segment_feature.

    The feature name is checked against f0..f11 because identifiers cannot be
    passed as SQL parameters.
    """
    if feature not in config.FEATURES:
        raise ValueError(f"unknown feature {feature!r}")
    con.execute(
        "CREATE OR REPLACE VIEW criteo_segments AS "
        f"SELECT treatment, visit, conversion, exposure, {feature} AS segment_feature "
        "FROM criteo"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pa.data")
    parser.add_argument("command", choices=["download", "build"])
    parser.add_argument("--only", choices=["olist", "criteo"])
    parser.add_argument("--criteo-sample-frac", type=float, default=None)
    args = parser.parse_args(argv)
    do_olist = args.only in (None, "olist")
    do_criteo = args.only in (None, "criteo")
    if args.command == "download":
        if do_olist:
            download_olist()
        if do_criteo:
            download_criteo()
    else:
        if do_olist:
            con = build_olist_db(db_path=config.OLIST_DB)
            con.close()
            print(f"built {config.OLIST_DB}")
        if do_criteo:
            p = build_criteo_parquet(sample_frac=args.criteo_sample_frac)
            print(f"built {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
