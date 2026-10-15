"""Exact expected numbers for every Olist query on the hand-made olist_mini data.

The fixture (tests/fixtures/olist_mini) is tiny on purpose, so each number can
be checked by hand. Key traps built into it:
- customer u1 has two customer_ids (c1 in March, c5 in May);
- order o2 is delivered late, o6 is canceled, o7 is before the analysis window;
- order o1 is paid with two methods; one payment has no parent order.
"""

from pathlib import Path

import pandas as pd
import pytest

from pa.data import build_olist_db
from pa.db import run_sql


def q(con, name):
    return run_sql(con, f"olist/{name}")


def test_data_quality(olist_con):
    df = q(olist_con, "01_data_quality")
    val = {(r.section, r.check_name): r.value for r in df.itertuples()}
    assert val[("rows", "orders")] == 7
    assert val[("rows", "customers")] == 8
    assert val[("rows", "order_items")] == 8
    assert val[("rows", "order_payments")] == 11
    assert val[("duplicate_keys", "orders.order_id")] == 0
    assert val[("orphans", "order_payments -> orders")] == 1
    assert val[("orphans", "order_items -> products")] == 0
    months = df[df.section == "orders_per_month"].set_index("check_name").value
    assert months.to_dict() == {
        "2016-10-01": 1,
        "2017-03-01": 2,
        "2017-04-01": 2,
        "2017-05-01": 2,
    }


def test_monthly_kpi(olist_con):
    df = q(olist_con, "02_monthly_kpi")
    assert [str(m)[:7] for m in df.month] == ["2017-03", "2017-04", "2017-05"]
    assert df.orders.tolist() == [2, 1, 2]
    assert df.buyers.tolist() == [2, 1, 2]
    assert df.gmv.tolist() == [385.0, 90.0, 200.0]
    assert df.aov.tolist() == [192.5, 90.0, 100.0]
    assert pd.isna(df.gmv_mom.iloc[0])
    assert df.gmv_mom.iloc[1] == pytest.approx(90 / 385 - 1)
    assert df.gmv_mom.iloc[2] == pytest.approx(200 / 90 - 1)


def test_order_funnel(olist_con):
    df = q(olist_con, "03_order_funnel").set_index("stage")
    assert df.orders.to_dict() == {
        "purchased": 6,
        "approved": 5,
        "handed_to_carrier": 5,
        "delivered": 5,
        "canceled": 1,
        "unavailable": 0,
    }
    assert df.share_of_purchased["approved"] == pytest.approx(5 / 6)
    assert df.share_of_purchased["unavailable"] == 0
    assert df.median_hours_from_prev["approved"] == 2
    assert df.median_hours_from_prev["handed_to_carrier"] == 24
    assert df.median_hours_from_prev["delivered"] == 96


def test_delivery_sla(olist_con):
    df = q(olist_con, "04_delivery_sla").set_index("state")
    assert df.delivered_orders.to_dict() == {"RJ": 1, "ALL": 5, "MG": 1, "SP": 3}
    assert df.late_orders["ALL"] == 1
    assert df.late_share["ALL"] == pytest.approx(0.2)
    assert df.late_share["RJ"] == 1.0
    # o2 has two reviews (1 and 3): averaged per order before comparing
    assert df.avg_score_late["ALL"] == pytest.approx(2.0)
    assert df.avg_score_on_time["ALL"] == pytest.approx(4.5)


def test_top_categories(olist_con):
    df = q(olist_con, "05_top_categories")
    rows = [
        (str(r.quarter)[:7], r.rank_in_quarter, r.category, r.revenue)
        for r in df.itertuples()
    ]
    assert rows == [
        ("2017-01", 1, "health_beauty", 300.0),
        ("2017-01", 2, "sports_leisure", 50.0),
        ("2017-04", 1, "health_beauty", 120.0),
        ("2017-04", 2, "sports_leisure", 80.0),
        ("2017-04", 3, "unknown", 60.0),
    ]


def test_cohort_retention_uses_unique_customer(olist_con):
    df = q(olist_con, "06_cohort_retention")
    cells = {
        (str(r.cohort_month)[:7], int(r.month_number)): (
            r.active_customers,
            r.cohort_size,
            r.retention,
        )
        for r in df.itertuples()
    }
    # u1 bought in March (c1) and May (c5): she is retained at M2, not a new
    # customer in the May cohort.
    assert cells[("2017-03", 0)] == (2, 2, 1.0)
    assert cells[("2017-03", 2)] == (1, 2, 0.5)
    assert cells[("2017-05", 0)] == (1, 1, 1.0)
    assert len(cells) == 4


def test_repeat_purchase(olist_con):
    r = q(olist_con, "07_repeat_purchase").iloc[0]
    assert r.customers == 4
    assert r.repeat_customers == 1
    assert r.repeat_share == pytest.approx(0.25)
    assert r.max_orders == 2
    # 2017-03-05 10:00 -> 2017-05-15 11:00 = 71 days and 1 hour
    assert r.median_days == pytest.approx(71 + 1 / 24)


def test_rfm_segments_cover_all_customers(olist_con):
    df = q(olist_con, "08_rfm")
    assert df.customers.sum() == 4
    assert df.customer_share.sum() == pytest.approx(1.0)
    assert df.revenue.sum() == pytest.approx(385 + 90 + 200)
    assert df.revenue_share.sum() == pytest.approx(1.0)
    # the only repeat buyer (u1, last order the day before the snapshot)
    row = df.set_index("segment").loc["active repeat"]
    assert row.customers == 1
    assert row.revenue == pytest.approx(165 + 135)


def test_seller_pareto(olist_con):
    df = q(olist_con, "09_seller_pareto")
    assert df.seller_id.tolist() == ["s1", "s2"]
    assert df.revenue.tolist() == [350.0, 260.0]
    assert df.cum_revenue_share.tolist() == pytest.approx([350 / 610, 1.0])
    assert df.cum_seller_share.tolist() == [0.5, 1.0]


def test_rolling_orders(olist_con):
    df = q(olist_con, "10_rolling_orders")
    assert df.orders.tolist() == [1, 1, 1, 1, 1, 1]
    ma = df.orders_ma7.tolist()
    # 2017-03-05 and 2017-03-08 are 3 days apart, so the second day sees 2 orders
    assert ma[:2] == pytest.approx([1 / 7, 2 / 7])
    assert ma[2:] == pytest.approx([1 / 7] * 4)


def test_payments(olist_con):
    df = q(olist_con, "11_payments")
    got = {
        (r.dimension, r.bucket): (r.orders, r.avg_order_value) for r in df.itertuples()
    }
    assert got[("payment_type", "credit_card")] == (4, pytest.approx(146.25))
    # o1 (165, two voucher rows) and o3 (90): counted once each, not per row
    assert got[("payment_type", "voucher")] == (2, pytest.approx(127.5))
    assert got[("payment_type", "boleto")] == (1, 90.0)
    assert got[("methods_per_order", "2+")] == (2, pytest.approx(127.5))
    assert got[("methods_per_order", "1")] == (3, pytest.approx(140.0))
    assert got[("installments", "1")] == (2, 155.0)
    assert got[("installments", "7-10")] == (1, 135.0)
    shares = df[df.dimension == "methods_per_order"].share_of_orders.sum()
    assert shares == pytest.approx(1.0)


def test_pk_check_finds_planted_duplicate():
    con = build_olist_db(Path(__file__).parent / "fixtures" / "olist_mini")
    con.execute("INSERT INTO sellers SELECT * FROM sellers WHERE seller_id = 's1'")
    df = run_sql(con, "olist/01_data_quality")
    row = df[df.check_name == "sellers.seller_id"].iloc[0]
    assert row.value == 1
