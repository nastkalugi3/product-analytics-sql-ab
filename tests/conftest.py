from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pa.data import build_olist_db, register_criteo, register_segment

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def olist_con():
    """In-memory DuckDB built from the hand-made olist_mini fixture."""
    con = build_olist_db(FIXTURES / "olist_mini", db_path=None)
    yield con
    con.close()


@pytest.fixture(scope="session")
def criteo_df() -> pd.DataFrame:
    """Synthetic Criteo-like table: 2000 users, seed 42 (not committed)."""
    rng = np.random.default_rng(42)
    n = 2000
    df = pd.DataFrame(
        {f"f{i}": rng.normal(i, 1 + i / 10, n).astype("float32") for i in range(12)}
    )
    for i in (1, 3, 4, 5, 6, 8, 9, 11):  # hashed categorical features
        df[f"f{i}"] = rng.integers(0, 15, n).astype("float32")
    df["treatment"] = (rng.random(n) < 0.85).astype("int8")
    p_visit = 0.05 + 0.02 * df["treatment"] + 0.01 * (df["f0"] > 0)
    df["visit"] = (rng.random(n) < p_visit).astype("int8")
    df["conversion"] = ((rng.random(n) < 0.1) & (df["visit"] == 1)).astype("int8")
    df["exposure"] = ((df["treatment"] == 1) & (rng.random(n) < 0.7)).astype("int8")
    return df


@pytest.fixture(scope="session")
def criteo_con(tmp_path_factory, criteo_df):
    """DuckDB connection with views `criteo` and `criteo_segments` (feature f3)."""
    import duckdb

    path = tmp_path_factory.mktemp("criteo") / "criteo_mini.parquet"
    criteo_df.to_parquet(path)
    con = duckdb.connect(":memory:")
    register_criteo(con, path)
    register_segment(con, "f3")
    yield con
    con.close()
