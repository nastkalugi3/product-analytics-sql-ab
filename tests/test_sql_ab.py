"""A/B SQL on a synthetic Criteo-like table: sums must match pandas."""

import numpy as np
import pytest

from pa.db import run_sql


def test_group_sizes(criteo_con, criteo_df):
    df = run_sql(criteo_con, "ab/01_group_sizes").set_index("treatment")
    counts = criteo_df.treatment.value_counts()
    assert df.n[0] == counts[0]
    assert df.n[1] == counts[1]
    assert df.share.sum() == pytest.approx(1.0)
    assert df.share[1] == pytest.approx(criteo_df.treatment.mean())


def test_group_metrics(criteo_con, criteo_df):
    df = run_sql(criteo_con, "ab/02_group_metrics").set_index("treatment")
    g = criteo_df.groupby("treatment")
    for col, out in [
        ("visit", "visits"),
        ("conversion", "conversions"),
        ("exposure", "exposed"),
    ]:
        assert df[out].tolist() == g[col].sum().tolist()
    v, c = criteo_df.visit, criteo_df.conversion
    t = criteo_df.treatment
    for grp in (0, 1):
        m = t == grp
        assert df.n_v0_c0[grp] == ((v == 0) & (c == 0) & m).sum()
        assert df.n_v1_c0[grp] == ((v == 1) & (c == 0) & m).sum()
        assert df.n_v1_c1[grp] == ((v == 1) & (c == 1) & m).sum()
        assert df.n_v0_c1[grp] == ((v == 0) & (c == 1) & m).sum()
        cells = df.loc[grp, ["n_v0_c0", "n_v1_c0", "n_v1_c1", "n_v0_c1"]].sum()
        assert cells == df.n[grp]


def test_covariate_balance_continuous_only(criteo_con, criteo_df):
    df = run_sql(criteo_con, "ab/03_covariate_balance").set_index("treatment")
    g = criteo_df.groupby("treatment")
    assert df.n.tolist() == g.size().tolist()
    for f in ("f0", "f2", "f7", "f10"):
        np.testing.assert_allclose(df[f"{f}_mean"], g[f].mean(), rtol=1e-5)
        np.testing.assert_allclose(df[f"{f}_sd"], g[f].std(ddof=1), rtol=1e-5)
    assert "f1_mean" not in df.columns


def test_strata_counts(criteo_con, criteo_df):
    df = run_sql(criteo_con, "ab/05_strata_counts")
    assert set(df.feature) == {"f1", "f3", "f4", "f5", "f6", "f8", "f9", "f11"}
    for f in ("f1", "f9"):
        sql = df[df.feature == f].set_index(["category", "treatment"])
        pdf = criteo_df.groupby([f, "treatment"]).agg(
            n=("visit", "size"), visits=("visit", "sum")
        )
        assert len(sql) == len(pdf)
        assert sql.n.to_numpy().tolist() == pdf.n.to_numpy().tolist()
        assert sql.visits.to_numpy().tolist() == pdf.visits.to_numpy().tolist()
    # every feature covers all users
    assert (df.groupby("feature").n.sum() == len(criteo_df)).all()


def test_segment_metrics(criteo_con, criteo_df):
    df = run_sql(criteo_con, "ab/04_segment_metrics")
    assert df.n.sum() == len(criteo_df)
    assert df.visits.sum() == criteo_df.visit.sum()
    assert sorted(df.quartile.unique()) == [1, 2, 3, 4]
    # same quartile rule in pandas
    x = criteo_df.f3.astype("float64")
    q1, q2, q3 = np.quantile(x, [0.25, 0.5, 0.75])
    quartile = np.where(x <= q1, 1, np.where(x <= q2, 2, np.where(x <= q3, 3, 4)))
    pdf = (
        criteo_df.assign(quartile=quartile)
        .groupby(["quartile", "treatment"])
        .agg(n=("visit", "size"), visits=("visit", "sum"))
        .reset_index()
    )
    merged = df.merge(pdf, on=["quartile", "treatment"], suffixes=("_sql", "_pd"))
    assert len(merged) == len(df) == len(pdf)
    assert (merged.n_sql == merged.n_pd).all()
    assert (merged.visits_sql == merged.visits_pd).all()
