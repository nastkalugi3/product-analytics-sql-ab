"""Small DuckDB helpers: connect, load a SQL file, run it."""

from pathlib import Path

import duckdb
import pandas as pd

from pa.config import SQL_DIR


def connect(path: str | Path | None = None, read_only: bool = False):
    """Open a DuckDB connection (in-memory if path is None)."""
    if path is None:
        return duckdb.connect(":memory:")
    return duckdb.connect(str(path), read_only=read_only)


def load_sql(name: str) -> str:
    """Return the text of a SQL file.

    `name` is a path relative to the sql/ folder, with or without ".sql",
    for example "olist/02_monthly_kpi" or "ab/01_group_sizes".
    """
    rel = name if name.endswith(".sql") else f"{name}.sql"
    return (SQL_DIR / rel).read_text(encoding="utf-8")


def run_sql(con, name: str, **params) -> pd.DataFrame:
    """Run a SQL file and return a DataFrame.

    Keyword arguments are passed as DuckDB named parameters ($name in SQL).
    A/B files read from a view called `criteo` that the caller creates
    (see pa.data.register_criteo).
    """
    sql = load_sql(name)
    if params:
        return con.execute(sql, params).df()
    return con.execute(sql).df()
