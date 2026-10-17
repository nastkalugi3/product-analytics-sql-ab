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


def add_dense_june(con) -> None:
    """Add a dense month to the olist_mini data so the dashboard has a "complete month".

    30 delivered orders j01..j30, one per day of 2017-06, customer c2 (RJ),
    seller s1, product p1: price 100 + freight 10 each. j01 arrives late (estimated
    date 2 days after purchase, delivered after 5), j02 has no review, j01 has
    score 2, the others score 4. One more order k1 on 2017-07-01 makes July a
    thin month (no orders in its last 7 days), so June is the last complete one.
    """
    from datetime import datetime, timedelta

    def order(oid, day, estimate_days):
        t0 = day
        return (
            oid, "c2", "delivered", t0, t0 + timedelta(hours=1),
            t0 + timedelta(days=1), t0 + timedelta(days=5),
            (t0 + timedelta(days=estimate_days)).replace(hour=0),
        )  # fmt: skip

    days = [datetime(2017, 6, d, 10) for d in range(1, 31)]
    orders = [
        order(f"j{i + 1:02d}", t, 2 if i == 0 else 10) for i, t in enumerate(days)
    ]
    orders.append(order("k1", datetime(2017, 7, 1, 10), 10))
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders)
    items = [(o[0], 1, "p1", "s1", o[3], 100.0, 10.0) for o in orders]
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?,?)", items)
    reviews = [
        (f"rj{i + 1:02d}", o[0], 2 if i == 0 else 4, None, None, o[6], o[6])
        for i, o in enumerate(orders)
        if i != 1 and o[0] != "k1"
    ]
    con.executemany("INSERT INTO order_reviews VALUES (?,?,?,?,?,?,?)", reviews)


@pytest.fixture(scope="session")
def dense_con():
    """olist_mini plus a dense June 2017 (see add_dense_june), in memory."""
    con = build_olist_db(FIXTURES / "olist_mini", db_path=None)
    add_dense_june(con)
    yield con
    con.close()


@pytest.fixture(scope="session")
def dense_db_file(tmp_path_factory):
    """Same data as dense_con, saved to a DuckDB file (for the CLI test)."""
    path = tmp_path_factory.mktemp("dense") / "olist_dense.duckdb"
    con = build_olist_db(FIXTURES / "olist_mini", db_path=path)
    add_dense_june(con)
    con.close()
    return path


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
