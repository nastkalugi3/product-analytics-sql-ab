"""Dashboard module: formatting, deltas, colours by meaning, page and CLI."""

from datetime import date

import pandas as pd
import pytest

from pa import dashboard as d
from pa.db import connect


def test_delta_tone_depends_on_meaning():
    assert d.delta_tone(5, higher_is_better=True) == "good"
    assert d.delta_tone(5, higher_is_better=False) == "bad"
    assert d.delta_tone(-5, higher_is_better=False) == "good"
    assert d.delta_tone(-5, higher_is_better=True) == "bad"
    assert d.delta_tone(0, higher_is_better=True) == "neutral"
    assert d.delta_tone(float("nan"), higher_is_better=True) == "neutral"


def test_relative_delta_text_and_missing_reference():
    up = d.relative_delta(110, 100, "June 2018")
    assert (up.text, up.tone) == ("▲ +10.0% vs June 2018", "good")
    down = d.relative_delta(90, 100, "June 2018")
    assert (down.text, down.tone) == ("▼ -10.0% vs June 2018", "bad")
    assert d.relative_delta(1, None, "x").text == "▬ n/a vs x"
    assert d.relative_delta(1, 0, "x").tone == "neutral"
    assert d.relative_delta(1, float("nan"), "x").tone == "neutral"


def test_absolute_delta_late_share_rise_is_bad():
    r = d.absolute_delta(0.034, 0.012, "June", "pp", 100, False, 1)
    assert (r.text, r.tone) == ("▲ +2.2 pp vs June", "bad")
    flat = d.absolute_delta(4.29, 4.29, "June", "pts", 1, True, 2)
    assert (flat.text, flat.tone) == ("▬ 0.00 pts vs June", "neutral")


def test_cell_tone_margins():
    assert d.cell_tone(0.09, 0.068, False, d.LATE_MARGIN) == "bad"
    assert d.cell_tone(0.05, 0.068, False, d.LATE_MARGIN) == "good"
    assert d.cell_tone(0.07, 0.068, False, d.LATE_MARGIN) == ""
    assert d.cell_tone(3.8, 4.1, True, d.REVIEW_MARGIN) == "bad"
    assert d.cell_tone(4.4, 4.1, True, d.REVIEW_MARGIN) == "good"
    assert d.cell_tone(None, 4.1, True, d.REVIEW_MARGIN) == ""


def test_labels_and_formats():
    assert d.humanize_category("health_beauty") == "Health beauty"
    assert d.state_label("SP") == "São Paulo (SP)"
    assert d.state_label("ZZ") == "ZZ (ZZ)"
    assert d.fmt_brl(1_039_783.58) == "BRL 1.04M"
    assert d.fmt_brl(249_393.44) == "BRL 249k"
    assert d.fmt_brl(166.8191) == "BRL 166.82"
    assert d.fmt_pct(float("nan")) == "n/a"
    assert d.fmt_score(float("nan")) == "n/a"
    assert d.fmt_score(4.2899) == "4.29"
    assert d.fmt_int(6233) == "6,233"
    assert d.fmt_pct(0.0338, 1) == "3.4%"
    assert d.month_label(pd.Timestamp("2018-07-01")) == "July 2018"


def test_make_cards_on_dense_june(dense_con):
    blocks = d.load_blocks(dense_con)
    cards = {c.label: c for c in d.make_cards(blocks["kpi"], blocks["monthly"])}
    gmv = cards["GMV (items + freight)"]
    assert gmv.north_star
    assert gmv.value == "BRL 3.3k"
    # June 3300 vs May 200 = +1550%; no June 2016 data -> n/a
    assert gmv.deltas[0].text == "▲ +1550.0% vs May 2017"
    assert gmv.deltas[1].text == "▬ n/a vs Jun 2016"
    # sparkline: months Mar..Jun 2017 (the data has no earlier month)
    assert gmv.spark == [385.0, 90.0, 200.0, 3300.0]
    late = cards["Late deliveries (share of delivered)"]
    assert late.value == "3.3%"  # 1 late of 30
    assert (late.deltas[0].text, late.deltas[0].tone) == (
        "▲ +3.3 pp vs May 2017",
        "bad",
    )
    review = cards["Average review score (1-5)"]
    assert review.value == "3.93"  # (2 + 28 * 4) / 29
    assert (review.deltas[0].text, review.deltas[0].tone) == (
        "▼ -0.57 pts vs May 2017",
        "bad",
    )


def test_make_cards_needs_a_complete_month(olist_con):
    blocks = d.load_blocks(olist_con)
    with pytest.raises(ValueError, match="no complete month"):
        d.make_cards(blocks["kpi"])


def test_build_html_contains_required_parts(dense_con):
    page = d.build_html(d.load_blocks(dense_con), generated=date(2026, 10, 17))
    assert page.count("cdn.plot.ly") == 1  # Plotly is loaded once, from the CDN
    assert "Olist, CC BY-NC-SA 4.0" in page
    assert "2017-03-05 to 2017-07-01 (analysis window)" in page
    assert "Updated:</b> 2026-10-17" in page
    assert "simulated" in page
    assert "BRL 3.3k" in page
    assert "Late %" in page and "cell-bad" in page
    assert "Health beauty" in page and "Rio de Janeiro (RJ)" in page
    blocks = d.load_blocks(dense_con)
    figures = [d.funnel_figure(blocks["funnel"]), d.trend_figure(blocks["trend"])]
    kinds = {t.type for fig in figures for t in fig.data}
    assert kinds == {"bar", "scatter"}  # no pie charts


def test_cli_writes_html_and_png(dense_db_file, tmp_path):
    html_path = tmp_path / "out" / "dash.html"
    png_path = tmp_path / "fig" / "dash.png"
    code = d.main(
        ["--db", str(dense_db_file), "--html", str(html_path), "--png", str(png_path)]
    )
    assert code == 0
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # the database file was only read
    con = connect(dense_db_file, read_only=True)
    assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 38
    con.close()


def test_cli_missing_database(tmp_path, capsys):
    code = d.main(["--db", str(tmp_path / "nope.duckdb"), "--no-png"])
    assert code == 1
    assert "missing" in capsys.readouterr().err


def test_toolbar_is_disabled_and_font_is_set(dense_con):
    page = d.build_html(d.load_blocks(dense_con), generated=date(2026, 10, 17))
    assert page.count('"displayModeBar": false') == 2  # funnel and trend
    assert "font-variant-numeric: tabular-nums" in page
    assert "fonts.googleapis.com" in page and "Inter" in page


def test_headlines_come_from_the_data(dense_con):
    blocks = d.load_blocks(dense_con)
    s = d.story(blocks)
    # June 2017 on the dense fixture: GMV 3300, May GMV 200 (the reference,
    # because June 2016 has no data), late 1/30 vs 0 in May
    assert s["headline"] == (
        "June 2017: GMV BRL 3.3k, up 1550.0% on May 2017; "
        "late deliveries rose to 3.3% from 0.0% in May 2017"
    )
    # pooled 12-month late share: 2 late of 35 delivered (Mar, Apr, May, Jun)
    assert s["avg12"] == "5.7%"
    # median of the monthly shares 0.5, 0, 0, 1/30 is 1/60
    assert s["med12"] == "1.7%"
    assert "Mar 2017 – Jun 2017" in s["sowhat"] and "median month (1.7%)" in s["sowhat"]
    # the dense fixture has no week a year back: the title falls back
    assert "last 4 complete weeks" in s["trend_title"]
    assert "includes canceled, unavailable and still-open orders" in s["funnel_title"]
    assert "5.7%" in s["sowhat"]
    page = d.build_html(blocks, generated=date(2026, 10, 17))
    assert s["headline"] in page
    # change the data and the headline changes with it
    blocks["kpi"].loc[blocks["kpi"].period == "current", "gmv"] = 6600.0
    assert "BRL 6.6k" in d.story(blocks)["headline"]


def test_black_friday_date_and_peak_label():
    assert d.black_friday(2017) == date(2017, 11, 24)
    assert d.black_friday(2018) == date(2018, 11, 23)
    trend = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2017-11-13", "2017-11-20", "2017-11-27"]),
            "orders": [10, 50, 20],
            "gmv": [1.0, 5.0, 2.0],
            "is_complete_week": [1, 1, 1],
        }
    )
    pk = d.peak_week(trend)
    assert pk["name"] == "Black Friday week" and pk["orders"] == 50
    trend["week_start"] = pd.to_datetime(["2017-05-01", "2017-05-08", "2017-05-15"])
    assert d.peak_week(trend)["name"] == "Peak week"


def test_sparkline_svg():
    svg = d.sparkline_svg([1.0, 3.0, 2.0, float("nan"), 4.0])
    assert svg.startswith("<svg") and d.ACCENT in svg  # last point in the accent
    assert d.sparkline_svg([1.0]) == ""


def test_sparkline_aria_label_and_contrast():
    svg = d.sparkline_svg(
        [1.0, 2.0], label="Orders, last 12 months, latest value 6,233"
    )
    assert 'aria-label="Orders, last 12 months, latest value 6,233"' in svg

    def lum(h):
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (1, 3, 5))

        def f(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def ratio(fg, bg):
        hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    for colour in (d.WARM_TEXT, d.ACCENT, d.MUTED, d.TEXT):
        assert ratio(colour, d.PAGE_BG) >= 4.5


def test_gmv_cells_use_compact_format():
    import re

    values = [1_432_213.38, 249_393.44, 999_600.0, 9_960.0, 9_743.72, 1_000.0, 999.5]
    df = pd.DataFrame(
        {
            "rank": range(1, len(values) + 1),
            "gmv": values,
            "orders": 10,
            "late_share": 0.05,
            "avg_review": 4.0,
            "benchmark_late_share": 0.05,
            "benchmark_review": 4.0,
        }
    )
    page = d._table_html(df, "Name", [f"row {i}" for i in range(len(values))])
    cells = re.findall(r'class="num">([^<]+)<', page)
    assert cells == [
        "BRL 1.43M", "BRL 249k", "BRL 1.00M", "BRL 10k", "BRL 9.7k", "BRL 1.0k",
        "BRL 999.50",
    ]  # fmt: skip
    for text, value in zip(cells, values, strict=True):
        if value >= 1000:
            assert re.fullmatch(r"BRL \d{1,3}(\.\d)?k|BRL \d\.\d\dM", text), text
    assert 'class="track"' in page and "height" not in page.split("<table>")[1]


def test_real_page_tables_have_no_raw_amounts(dense_con):
    import re

    page = d.build_html(d.load_blocks(dense_con), generated=date(2026, 10, 17))
    for text in re.findall(r'class="num">([^<]+)<', page):
        assert not re.search(r"\d,\d{3}", text), text
