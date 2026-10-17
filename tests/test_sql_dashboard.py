"""Dashboard SQL on hand-made data, numbers checked by hand.

Two datasets:
- olist_con: plain olist_mini (orders on 2017-03..05, all months are "thin");
- dense_con: olist_mini plus a dense June 2017 (see conftest.add_dense_june).

Hand calculation on olist_mini, sales orders (not canceled, with items):
  o1 SP 165 (late no, review 5)   o2 RJ 220 (late yes, reviews 1 and 3 -> 2)
  o3 SP 90 (no, 4)                o4 MG 65 (no, 5)       o5 SP 135 (no, 4)
Total GMV 675, one late order of five delivered (benchmark late 0.2, review 4.0).
"""

import pandas as pd
import pytest

from pa.db import run_sql


def q(con, name):
    return run_sql(con, f"dashboard/{name}")


def test_meta(olist_con):
    r = q(olist_con, "00_meta").iloc[0]
    assert str(r.first_order_date)[:10] == "2017-03-05"
    assert str(r.last_order_date)[:10] == "2017-05-15"
    assert r.window_orders == 6  # o7 is before the window
    assert r.sales_orders == 5  # o6 is canceled
    assert r.total_gmv == 675.0


def test_kpi_cards_dense_june(dense_con):
    df = q(dense_con, "01_kpi_cards").set_index("period")
    assert df.index.tolist() == ["current", "previous_month", "same_month_last_year"]
    assert [str(m)[:7] for m in df.month_start] == ["2017-06", "2017-05", "2016-06"]
    cur, prev, year = df.loc["current"], df.loc["previous_month"], df.iloc[2]
    # June: 30 orders x 110; j01 late; reviews: j01 = 2, j02 none, 28 x 4
    assert cur.orders == 30
    assert cur.gmv == 3300.0
    assert cur.aov == 110.0
    assert cur.delivered_orders == 30
    assert cur.late_share == pytest.approx(1 / 30)
    assert cur.avg_review == pytest.approx((2 + 28 * 4) / 29)
    # May: o4 (65) and o5 (135), both on time, reviews 5 and 4
    assert prev.orders == 2
    assert prev.gmv == 200.0
    assert prev.aov == 100.0
    assert prev.late_share == 0.0
    assert prev.avg_review == pytest.approx(4.5)
    # nothing in June 2016: zero orders and undefined (NULL) values
    assert year.orders == 0
    assert pd.isna(year.gmv) and pd.isna(year.late_share)


def test_kpi_skips_thin_last_month(dense_con):
    # July has one order on its first day: its last 7 days are empty, so the
    # card month is June, not July.
    df = q(dense_con, "01_kpi_cards")
    assert str(df.month_start.iloc[0])[:7] == "2017-06"


def test_kpi_without_complete_month(olist_con):
    df = q(olist_con, "01_kpi_cards")
    assert df.month_start.isna().all()
    assert df.orders.tolist() == [0, 0, 0]


def test_funnel(olist_con):
    df = q(olist_con, "02_funnel").set_index("stage")
    assert df.orders.to_dict() == {
        "Purchased": 6,
        "Approved": 5,
        "Handed to carrier": 5,
        "Delivered": 5,
        "Canceled": 1,
        "Unavailable": 0,
        "In progress": 0,
    }
    assert df.kind.to_dict()["Canceled"] == "loss"
    assert df.share_of_purchased["Approved"] == pytest.approx(5 / 6)
    assert df.step_conversion["Approved"] == pytest.approx(5 / 6)
    assert df.step_conversion["Handed to carrier"] == 1.0
    assert df.step_conversion["Delivered"] == 1.0
    assert pd.isna(df.step_conversion["Purchased"])
    assert pd.isna(df.step_conversion["Canceled"])


def test_weekly_trend(dense_con):
    df = q(dense_con, "03_weekly_trend").set_index("week_start")
    df.index = [str(d)[:10] for d in df.index]
    # week of Mon 2017-02-27 holds o1 (Sun 03-05) but starts before the first order
    assert df.loc["2017-02-27"].orders == 1
    assert df.loc["2017-02-27"].gmv == 165.0
    assert df.loc["2017-02-27"].is_complete_week == 0
    # week of 2017-03-06: o2 only
    assert df.loc["2017-03-06"].orders == 1
    assert df.loc["2017-03-06"].gmv == 220.0
    assert df.loc["2017-03-06"].is_complete_week == 1
    # week of 2017-06-19: June 19..25 = 7 orders x 110
    assert df.loc["2017-06-19"].orders == 7
    assert df.loc["2017-06-19"].gmv == 770.0
    assert df.loc["2017-06-19"].aov == 110.0
    assert df.loc["2017-06-19"].is_complete_week == 1
    # week of 2017-06-26 runs into July (after the last complete month)
    assert df.loc["2017-06-26"].orders == 6  # Jun 26..30 and k1 on Jul 1
    assert df.loc["2017-06-26"].is_complete_week == 0


def test_category_table(olist_con):
    df = q(olist_con, "04_category_table").set_index("category")
    assert df.index.tolist() == ["health_beauty", "sports_leisure", "unknown"]
    assert df.gmv.tolist() == [465.0, 145.0, 65.0]  # o1+o2+o5, o1+o3, o4
    assert df.share_of_gmv.sum() == pytest.approx(1.0)  # total 675
    assert df.orders.tolist() == [3, 2, 1]  # o1 is in two categories
    assert df.late_share["health_beauty"] == pytest.approx(1 / 3)  # o2 is late
    assert df.late_share["sports_leisure"] == 0.0
    assert df.avg_review["health_beauty"] == pytest.approx((5 + 2 + 4) / 3)
    assert df.avg_review["sports_leisure"] == pytest.approx(4.5)
    assert (df.benchmark_late_share == 0.2).all()
    assert (df.benchmark_review == 4.0).all()
    assert df["rank"].tolist() == [1, 2, 3]


def test_state_table(olist_con):
    df = q(olist_con, "05_state_table").set_index("state")
    assert df.index.tolist() == ["SP", "RJ", "MG"]
    assert df.gmv.to_dict() == {"SP": 390.0, "RJ": 220.0, "MG": 65.0}
    assert df.orders.to_dict() == {"SP": 3, "RJ": 1, "MG": 1}
    assert df.late_share.to_dict() == {"SP": 0.0, "RJ": 1.0, "MG": 0.0}
    assert df.avg_review["SP"] == pytest.approx((5 + 4 + 4) / 3)
    assert df.avg_review["RJ"] == 2.0  # reviews 1 and 3 averaged inside the order
    assert df.share_of_gmv["SP"] == pytest.approx(390 / 675)


def test_seller_table(olist_con):
    df = q(olist_con, "06_seller_table").set_index("seller_id")
    assert df.index.tolist() == ["s1", "s2"]
    assert df.gmv.to_dict() == {"s1": 390.0, "s2": 285.0}  # s1: o1, o3, o5
    assert df.orders.to_dict() == {"s1": 3, "s2": 2}
    assert df.late_share.to_dict() == {"s1": 0.0, "s2": 0.5}  # s2 sold o2 (late), o4
    assert df.avg_review["s1"] == pytest.approx((5 + 4 + 4) / 3)
    assert df.avg_review["s2"] == pytest.approx((2 + 5) / 2)
    assert df.seller_state.to_dict() == {"s1": "SP", "s2": "RJ"}


def test_monthly_series(olist_con):
    df = q(olist_con, "07_monthly_series")
    assert [str(m)[:7] for m in df.month_start] == ["2017-03", "2017-04", "2017-05"]
    assert df.orders.tolist() == [2, 1, 2]
    assert df.gmv.tolist() == [385.0, 90.0, 200.0]
    assert df.aov.tolist() == [192.5, 90.0, 100.0]
    assert df.delivered_orders.tolist() == [2, 1, 2]
    assert df.late_orders.tolist() == [1, 0, 0]  # o2 is the only late order
    assert df.late_share.tolist() == [0.5, 0.0, 0.0]
    # March reviews: o1 = 5, o2 = (1 + 3) / 2 = 2 -> 3.5
    assert df.avg_review.tolist() == pytest.approx([3.5, 4.0, 4.5])


def test_monthly_series_matches_kpi_cards(dense_con):
    series = q(dense_con, "07_monthly_series").set_index("month_start")
    kpi = q(dense_con, "01_kpi_cards").set_index("period")
    cur = kpi.loc["current"]
    row = series.loc[cur.month_start]
    assert row.orders == cur.orders and row.gmv == cur.gmv
    assert row.late_share == pytest.approx(cur.late_share)
    assert row.avg_review == pytest.approx(cur.avg_review)
