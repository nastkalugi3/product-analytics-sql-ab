"""Sales & Operations dashboard for Olist: SQL blocks -> one HTML file + PNG preview.

Run: python -m pa.dashboard
Every number comes from the queries in sql/dashboard/. This module formats them,
computes deltas between the KPI periods, writes the headlines from the data at
build time (nothing is typed in by hand) and draws the page.

The requirements for the page are in docs/dashboard_spec.md (a simulated brief),
the design reasons are in docs/dashboard_design.md.
"""

import argparse
import html
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from pa import config
from pa.db import connect, run_sql

# One accent for what matters, greys for context, one warm colour for "bad".
# Accent (deep teal) and vermillion differ in hue and lightness, so they stay
# apart for the common kinds of colour blindness; arrows and signs repeat the meaning.
ACCENT = "#0F766E"
WARM = "#D55E00"  # fills and bars
WARM_TEXT = "#B34700"  # text on the light page: contrast 5.3:1 (WARM is 3.7:1)
TEXT = "#1F2328"
MUTED = "#6B7280"
GRID = "#ECEEF0"
BAR_GREY = "#C5CAD1"
BAR_LIGHT = "#E6E9ED"
ACCENT_TINT = "#DCEEEB"
WARM_TINT = "#FBE7D9"
PAGE_BG = "#FAFAF8"
FONT_URL = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap"
)
FONT_STACK = (
    "Inter, 'IBM Plex Sans', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
)
TONE_COLOR = {"good": ACCENT, "bad": WARM_TEXT, "neutral": MUTED}

# A cell is tinted only when it differs from the all-orders average by more than
# these margins (simulated thresholds, see docs/dashboard_spec.md).
LATE_MARGIN = 0.01  # 1 percentage point
REVIEW_MARGIN = 0.10  # 0.1 score points

BLOCKS = {
    "kpi": "dashboard/01_kpi_cards",
    "funnel": "dashboard/02_funnel",
    "trend": "dashboard/03_weekly_trend",
    "category": "dashboard/04_category_table",
    "state": "dashboard/05_state_table",
    "seller": "dashboard/06_seller_table",
    "monthly": "dashboard/07_monthly_series",
    "meta": "dashboard/00_meta",
}

STATE_NAMES = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AM": "Amazonas",
    "AP": "Amapá",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MG": "Minas Gerais",
    "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso",
    "PA": "Pará",
    "PB": "Paraíba",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "PR": "Paraná",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RO": "Rondônia",
    "RR": "Roraima",
    "RS": "Rio Grande do Sul",
    "SC": "Santa Catarina",
    "SE": "Sergipe",
    "SP": "São Paulo",
    "TO": "Tocantins",
}

CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: {PAGE_BG}; color: {TEXT}; font-size: 14px;
  font-family: {FONT_STACK}; line-height: 1.5;
  font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }}
.page {{ max-width: 1200px; margin: 0 auto; padding: 48px 24px 48px; }}
.kicker {{ font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
  color: {ACCENT}; font-weight: 600; margin: 0 0 8px; }}
h1 {{ font-size: 30px; line-height: 1.25; font-weight: 600; margin: 0 0 16px;
  max-width: 960px; }}
.sowhat {{ font-size: 16px; color: {TEXT}; margin: 0 0 8px; max-width: 880px; }}
.note {{ font-size: 12px; color: {MUTED}; margin: 0; max-width: 880px; }}
h2 {{ font-size: 18px; line-height: 1.35; font-weight: 600; margin: 0 0 8px;
  max-width: 880px; }}
section {{ margin-top: 56px; }}
.cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 32px;
  margin-top: 40px; }}
.card .label {{ font-size: 12px; color: {MUTED}; }}
.card .value {{ font-size: 32px; font-weight: 600; line-height: 1.2;
  margin: 4px 0 8px; }}
.card .delta {{ font-size: 12px; line-height: 20px; white-space: nowrap; }}
.card .spark {{ display: block; margin-top: 8px; }}
.card .spark-cap {{ font-size: 11px; color: {MUTED}; }}
.good {{ color: {ACCENT}; font-weight: 600; }}
.bad {{ color: {WARM_TEXT}; font-weight: 600; }}
.neutral {{ color: {MUTED}; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 48px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }}
th {{ text-align: right; padding: 8px; color: {MUTED}; font-weight: 500;
  font-size: 12px; border-bottom: 1px solid {BAR_GREY}; }}
td {{ text-align: right; padding: 4px 8px; height: 32px;
  border-bottom: 1px solid {GRID}; }}
th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
td:first-child, th:first-child {{ color: {MUTED}; width: 24px; }}
.gmv {{ display: flex; align-items: center; gap: 12px; min-width: 150px; }}
.gmv .track {{ flex: 1; min-width: 40px; }}
.gmv .bar {{ height: 8px; background: #D3D8DE; border-radius: 4px; }}
.gmv .num {{ min-width: 64px; text-align: right; }}
.narrow {{ max-width: 900px; }}
td.cell-good {{ background: {ACCENT_TINT}; }}
td.cell-bad {{ background: {WARM_TINT}; }}
.tbl-title {{ font-size: 13px; font-weight: 600; margin: 24px 0 0; }}
.footer {{ margin-top: 64px; padding-top: 16px; border-top: 1px solid {BAR_GREY};
  font-size: 12px; color: {MUTED}; line-height: 1.7; max-width: 960px; }}
@media (max-width: 960px) {{
  .cards {{ grid-template-columns: repeat(2, 1fr); gap: 24px; }}
  .two {{ grid-template-columns: 1fr; gap: 24px; }}
  h1 {{ font-size: 24px; }}
}}
"""


@dataclass(frozen=True)
class Delta:
    """One comparison under a KPI card."""

    text: str  # for example "▲ +2.1% vs Jun 2018"
    tone: str  # good | bad | neutral


@dataclass(frozen=True)
class Card:
    label: str
    value: str
    deltas: list[Delta]
    north_star: bool = False
    spark: list[float] = field(default_factory=list)  # last 12 months, oldest first


# ---------------------------------------------------------------- formatting


def fmt_score(x: float) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.2f}"


def fmt_int(x) -> str:
    return f"{int(x):,}"


def fmt_brl(x: float) -> str:
    """Money with a compact scale: BRL 1.04M, BRL 249k, BRL 9.7k, BRL 166.82.

    From 1,000 up the value always has a k or M suffix; below 1,000 it is shown
    with cents (used for the average order value).
    """
    if x >= 999_500:
        return f"BRL {x / 1e6:.2f}M"
    if x >= 1e3:
        k = x / 1e3
        return f"BRL {k:.0f}k" if round(k, 1) >= 10 else f"BRL {k:.1f}k"
    return f"BRL {x:,.2f}"


def fmt_pct(x: float, digits: int = 1) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{100 * x:.{digits}f}%"


def humanize_category(name: str) -> str:
    """'health_beauty' -> 'Health beauty'."""
    return name.replace("_", " ").capitalize()


def state_label(code: str) -> str:
    return f"{STATE_NAMES.get(code, code)} ({code})"


def seller_label(seller_id: str, state: str | None) -> str:
    return f"Seller {seller_id[:8]} ({state or '?'})"


def month_label(ts) -> str:
    return pd.Timestamp(ts).strftime("%B %Y")


def month_short(ts) -> str:
    return pd.Timestamp(ts).strftime("%b %Y")


# --------------------------------------------------------------- calculations


def delta_tone(change: float, higher_is_better: bool, eps: float = 0.0) -> str:
    """Colour by meaning: a rise is good only when higher is better."""
    if change is None or pd.isna(change) or abs(change) <= eps:
        return "neutral"
    return "good" if (change > 0) == higher_is_better else "bad"


def _arrow(change: float) -> str:
    return "▲" if change > 0 else "▼" if change < 0 else "▬"


def relative_delta(cur, ref, label: str, higher_is_better: bool = True) -> Delta:
    """Percent change cur vs ref, as a Delta. Missing/zero reference -> n/a."""
    if ref is None or pd.isna(ref) or ref == 0 or cur is None or pd.isna(cur):
        return Delta(f"▬ n/a vs {label}", "neutral")
    change = cur / ref - 1
    shown = round(100 * change, 1)
    return Delta(
        f"{_arrow(shown)} {shown:+.1f}% vs {label}",
        delta_tone(shown, higher_is_better),
    )


def absolute_delta(
    cur, ref, label: str, unit: str, scale: float, higher_is_better: bool, digits: int
) -> Delta:
    """Difference cur - ref (times `scale`, shown with `unit`) as a Delta."""
    if ref is None or pd.isna(ref) or cur is None or pd.isna(cur):
        return Delta(f"▬ n/a vs {label}", "neutral")
    shown = round(scale * (cur - ref), digits)
    number = f"{shown:+.{digits}f}" if shown else f"{0:.{digits}f}"
    return Delta(
        f"{_arrow(shown)} {number} {unit} vs {label}",
        delta_tone(shown, higher_is_better),
    )


def spark_values(monthly: pd.DataFrame | None, cur_month, col: str) -> list[float]:
    """The 12 monthly values that end with the card month (oldest first)."""
    if monthly is None:
        return []
    m = monthly[monthly.month_start <= pd.Timestamp(cur_month)].tail(12)
    return [float(v) for v in m[col]]


def make_cards(kpi: pd.DataFrame, monthly: pd.DataFrame | None = None) -> list[Card]:
    """Five KPI cards from the D1 result (rows: current, previous, year ago)."""
    rows = kpi.set_index("period")
    cur = rows.loc["current"]
    if pd.isna(cur.month_start):
        raise ValueError("no complete month in the analysis window (see sql D1)")
    prev = rows.loc["previous_month"]
    year = rows.loc["same_month_last_year"]
    pl, yl = month_short(prev.month_start), month_short(year.month_start)

    def rel(col):
        return [
            relative_delta(cur[col], prev[col], pl),
            relative_delta(cur[col], year[col], yl),
        ]

    def absol(col, unit, scale, higher_is_better, digits):
        return [
            absolute_delta(cur[col], r[col], lab, unit, scale, higher_is_better, digits)
            for r, lab in ((prev, pl), (year, yl))
        ]

    def sp(col):
        return spark_values(monthly, cur.month_start, col)

    return [
        Card(
            "GMV (items + freight)",
            fmt_brl(cur.gmv),
            rel("gmv"),
            north_star=True,
            spark=sp("gmv"),
        ),
        Card("Orders", fmt_int(cur.orders), rel("orders"), spark=sp("orders")),
        Card("Average order value", fmt_brl(cur.aov), rel("aov"), spark=sp("aov")),
        Card(
            "Late deliveries (share of delivered)",
            fmt_pct(cur.late_share),
            absol("late_share", "pp", 100, False, 1),
            spark=sp("late_share"),
        ),
        Card(
            "Average review score (1-5)",
            fmt_score(cur.avg_review),
            absol("avg_review", "pts", 1, True, 2),
            spark=sp("avg_review"),
        ),
    ]


def cell_tone(value, benchmark, higher_is_better: bool, margin: float) -> str:
    """'good' / 'bad' when the value beats / trails the benchmark by > margin."""
    if value is None or pd.isna(value) or pd.isna(benchmark):
        return ""
    diff = value - benchmark
    if abs(diff) <= margin:
        return ""
    return "good" if (diff > 0) == higher_is_better else "bad"


def black_friday(year: int) -> date:
    """Day after the fourth Thursday of November."""
    nov1 = date(year, 11, 1)
    first_thursday = nov1 + timedelta(days=(3 - nov1.weekday()) % 7)
    return first_thursday + timedelta(days=21 + 1)


def peak_week(trend: pd.DataFrame) -> dict:
    """Peak complete week and whether it contains Black Friday."""
    t = trend[trend.is_complete_week == 1]
    row = t.loc[t.orders.idxmax()]
    start = pd.Timestamp(row.week_start).date()
    bf = black_friday(start.year)
    is_bf = start <= bf <= start + timedelta(days=6)
    name = "Black Friday week" if is_bf else "Peak week"
    return {"start": start, "orders": int(row.orders), "name": name}


# ------------------------------------------------------------------ headlines


def _risen(x: float, up: str, down: str) -> str:
    return up if x > 0 else down


def story(blocks: dict[str, pd.DataFrame]) -> dict[str, str]:
    """All headlines and annotations, written from the query results."""
    kpi = blocks["kpi"].set_index("period")
    cur, prev = kpi.loc["current"], kpi.loc["previous_month"]
    year = kpi.loc["same_month_last_year"]
    monthly = blocks["monthly"]
    cm, pm = month_label(cur.month_start), month_short(prev.month_start)

    # page headline: GMV against a year ago (or the previous month), late share
    if pd.notna(year.gmv) and year.gmv > 0:
        ref_gmv, ref_name = year.gmv, month_label(year.month_start)
    else:
        ref_gmv, ref_name = prev.gmv, month_label(prev.month_start)
    chg = 100 * (cur.gmv / ref_gmv - 1)
    head = (
        f"{cm}: GMV {fmt_brl(cur.gmv)}, {_risen(chg, 'up', 'down')} "
        f"{abs(chg):.1f}% on {ref_name}"
    )
    if pd.notna(prev.late_share):
        d_pp = cur.late_share - prev.late_share
        head += (
            f"; late deliveries {_risen(d_pp, 'rose', 'fell')} to "
            f"{fmt_pct(cur.late_share)} from {fmt_pct(prev.late_share)} in {pm}"
        )
    else:
        head += f"; late deliveries at {fmt_pct(cur.late_share)}"

    # so-what: put the late-share move in context of the 12-month level
    upto = monthly[monthly.month_start <= pd.Timestamp(cur.month_start)]
    last12 = upto.tail(12)
    avg12 = last12.late_orders.sum() / last12.delivered_orders.sum()
    low = upto.loc[upto.late_share.idxmin()]
    med12 = last12.late_share.median()
    period = (
        f"{month_short(last12.month_start.iloc[0])} – {month_short(cur.month_start)}"
    )
    ctx = (
        f"the 12-month pooled late share ({period}: {fmt_pct(avg12)}, all late orders "
        f"over all delivered orders) and the median month ({fmt_pct(med12)})"
    )
    cm_short = month_short(cur.month_start)
    below = cur.late_share < min(avg12, med12)
    if pd.Timestamp(low.month_start) == pd.Timestamp(prev.month_start):
        sowhat = (
            f"{pm} had the lowest late share of any month in the window "
            f"({fmt_pct(low.late_share)}), so the rise looks bigger than it is: "
            f"{cm_short} is {'still below both' if below else 'compared with'} {ctx}."
        )
    else:
        sowhat = (
            f"The lowest month was {month_short(low.month_start)} "
            f"({fmt_pct(low.late_share)}); {cm_short} is "
            f"{'below both' if below else 'compared with'} {ctx}."
        )

    # funnel: delivered share and the biggest drop between two purchase steps
    f = blocks["funnel"]
    steps = f[f.kind == "step"].reset_index(drop=True)
    drops = steps.orders.shift(1) - steps.orders
    k = int(drops.iloc[1:].idxmax())
    drop_n = int(drops.iloc[k])
    drop_share = steps.orders.iloc[k] / steps.orders.iloc[k - 1]
    funnel_title = (
        f"{fmt_pct(steps.share_of_purchased.iloc[-1])} of purchased orders are "
        f"delivered; the biggest drop is at “{steps.stage.iloc[k]}”: "
        f"{fmt_int(drop_n)} orders ({fmt_pct(1 - drop_share)} of the previous step; "
        "includes canceled, unavailable and still-open orders)"
    )

    # trend: growth from the first to the last four complete weeks, plus the peak
    t = blocks["trend"]
    t = t[t.is_complete_week == 1]
    # Early 2017 is the data ramp-up, so compare the last 4 complete weeks with the
    # same 4 weeks a year earlier (364 days back), not with the first weeks.
    recent = t.tail(4)
    year_ago = t[t.week_start.isin(recent.week_start - pd.Timedelta(days=364))]
    pk = peak_week(blocks["trend"])
    spike = (
        f"with one spike: the {pk['name']} of {pk['start']:%d %b %Y} "
        f"({fmt_int(pk['orders'])} orders)"
    )
    if len(year_ago) == 4:
        before = fmt_int(round(year_ago.orders.mean(), -1))
        trend_title = (
            f"Weekly orders rose from about {before}"
            f" ({year_ago.week_start.iloc[0]:%b %Y}) to about "
            f"{fmt_int(round(recent.orders.mean(), -1))} "
            f"({recent.week_start.iloc[0]:%b %Y}), {spike}"
        )
    else:
        trend_title = (
            f"Weekly orders average about {fmt_int(round(recent.orders.mean(), -1))} "
            f"over the last 4 complete weeks, {spike}"
        )

    # tables
    cat = blocks["category"]
    worst = cat.loc[cat.avg_review.idxmin()]
    category_title = (
        f"The top {len(cat)} categories bring {fmt_pct(cat.share_of_gmv.sum())} of "
        f"GMV; {humanize_category(worst.category)} has the lowest review "
        f"({fmt_score(worst.avg_review)})"
    )
    st = blocks["state"]
    lo, hi, big = (
        st.loc[st.late_share.idxmin()],
        st.loc[st.late_share.idxmax()],
        st.iloc[0],
    )
    state_title = (
        f"Late share runs from {fmt_pct(lo.late_share)} in "
        f"{STATE_NAMES.get(lo.state, lo.state)} to {fmt_pct(hi.late_share)} in "
        f"{STATE_NAMES.get(hi.state, hi.state)}; the biggest state, "
        f"{STATE_NAMES.get(big.state, big.state)}, is at {fmt_pct(big.late_share)}"
    )
    sl = blocks["seller"]
    n_bad = sum(
        cell_tone(r.late_share, r.benchmark_late_share, False, LATE_MARGIN) == "bad"
        for r in sl.itertuples()
    )
    seller_title = (
        f"The {len(sl)} biggest sellers hold {fmt_pct(sl.share_of_gmv.sum())} of GMV; "
        f"{n_bad} of them deliver late more than 1 pp above the average"
    )
    return {
        "headline": head,
        "sowhat": sowhat,
        "funnel_title": funnel_title,
        "trend_title": trend_title,
        "category_title": category_title,
        "state_title": state_title,
        "seller_title": seller_title,
        "avg12": fmt_pct(avg12),
        "med12": fmt_pct(med12),
    }


# --------------------------------------------------------------- data loading


def load_blocks(con) -> dict[str, pd.DataFrame]:
    """Run every dashboard query once."""
    return {key: run_sql(con, name) for key, name in BLOCKS.items()}


# ------------------------------------------------------------------ HTML page


def sparkline_svg(
    values: list[float], width: int = 128, height: int = 32, label: str = ""
) -> str:
    """Tiny inline line chart: no axes, last point in the accent colour."""
    vals = [v for v in values if v is not None and not pd.isna(v)]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 4
    pts = [
        (
            pad + i * (width - 2 * pad) / (len(vals) - 1),
            height - pad - (v - lo) / span * (height - 2 * pad),
        )
        for i, v in enumerate(vals)
    ]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    x, y = pts[-1]
    return (
        f'<svg class="spark" width="{width}" height="{height}" role="img" '
        f'aria-label="{html.escape(label or "last 12 months")}" '
        f'viewBox="0 0 {width} {height}">'
        f'<polyline points="{path}" fill="none" stroke="{BAR_GREY}" '
        f'stroke-width="1.5" stroke-linejoin="round"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{ACCENT}"/></svg>'
    )


def _cards_html(cards: list[Card]) -> str:
    out = []
    for c in cards:
        deltas = "".join(
            f'<div class="delta {d.tone}">{html.escape(d.text)}</div>' for d in c.deltas
        )
        star = ' <span class="neutral">· North Star</span>' if c.north_star else ""
        spark = sparkline_svg(
            c.spark, label=f"{c.label}, last 12 months, latest value {c.value}"
        )
        cap = '<div class="spark-cap">last 12 months</div>' if spark else ""
        out.append(
            f'<div class="card"><div class="label">{html.escape(c.label)}{star}</div>'
            f'<div class="value">{html.escape(c.value)}</div>{deltas}{spark}{cap}</div>'
        )
    return f'<div class="cards">{"".join(out)}</div>'


def _table_html(df: pd.DataFrame, first_col: str, labels: list[str]) -> str:
    """Rank, name, GMV with an inline bar, orders, late %, review (two tinted)."""
    head = ["#", first_col, "GMV", "Orders", "Late %", "Avg review"]
    top = df.gmv.max() or 1.0
    rows = []
    for r, label in zip(df.itertuples(), labels, strict=True):
        late = cell_tone(r.late_share, r.benchmark_late_share, False, LATE_MARGIN)
        rev = cell_tone(r.avg_review, r.benchmark_review, True, REVIEW_MARGIN)
        rows.append(
            "<tr>"
            f"<td>{r.rank}</td><td>{html.escape(label)}</td>"
            f'<td><div class="gmv"><div class="track"><div class="bar" '
            f'style="width:{100 * r.gmv / top:.1f}%"></div></div>'
            f'<span class="num">{fmt_brl(r.gmv)}</span></div></td>'
            f"<td>{fmt_int(r.orders)}</td>"
            f'<td class="cell-{late}">{fmt_pct(r.late_share)}</td>'
            f'<td class="cell-{rev}">{fmt_score(r.avg_review)}</td></tr>'
        )
    cols = "".join(f"<th>{h}</th>" for h in head)
    return f"<table><tr>{cols}</tr>{''.join(rows)}</table>"


def _legend(bench_late: float, bench_review: float) -> str:
    return (
        '<p class="note" style="margin-top:16px">Tinted cells are measured against '
        f"the average of all orders in the window (late {fmt_pct(bench_late)}, review "
        f"{fmt_score(bench_review)}): teal is better, orange is worse, by more than "
        f"{100 * LATE_MARGIN:.0f} pp (late) or {REVIEW_MARGIN:.1f} points (review). "
        "The bar in the GMV column is relative to the largest row of the table. An "
        "order with items from several categories or sellers counts once in each.</p>"
    )


def _style_axes(fig, height: int, unified: bool = False) -> None:
    """Shared Plotly look: transparent, no axis lines, light y grid, one font."""
    fig.update_layout(
        height=height,
        showlegend=False,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT_STACK, "size": 12, "color": MUTED},
        margin={"l": 0, "r": 8, "t": 24, "b": 8},
        hovermode="x unified" if unified else "closest",
        hoverlabel={
            "bgcolor": "white",
            "bordercolor": BAR_GREY,
            "font": {"family": FONT_STACK, "size": 12, "color": TEXT},
        },
    )
    fig.update_xaxes(showgrid=False, showline=False, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, showline=False, zeroline=False)


def funnel_figure(funnel: pd.DataFrame):
    """Purchase steps as horizontal bars with direct drop-off labels."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    steps = funnel[funnel.kind == "step"].reset_index(drop=True)
    side = funnel[funnel.kind != "step"].reset_index(drop=True)
    drops = (steps.orders.shift(1) - steps.orders).fillna(0)
    biggest = int(drops.iloc[1:].idxmax())
    text = []
    for i, r in enumerate(steps.itertuples()):
        t = fmt_int(r.orders)
        if i > 0:
            t += (
                f"   {fmt_pct(r.step_conversion)} of previous step · "
                f"−{fmt_int(drops.iloc[i])}"
            )
        text.append(t)
    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.68, 0.32],
        horizontal_spacing=0.04,
        subplot_titles=("Purchase steps reached", "Not delivered: lost or still open"),
    )
    fig.add_trace(
        go.Bar(
            y=steps.stage,
            x=steps.orders,
            orientation="h",
            marker={
                "color": [ACCENT if i == biggest else BAR_GREY for i in steps.index]
            },
            text=text,
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            hovertemplate="%{y}: %{x:,} orders<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            y=side.stage,
            x=side.orders,
            orientation="h",
            marker={"color": [WARM if k == "loss" else BAR_GREY for k in side.kind]},
            text=[
                f"{fmt_int(o)} · {fmt_pct(s, 2)} of purchased"
                for o, s in zip(side.orders, side.share_of_purchased, strict=True)
            ],
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            hovertemplate="%{y}: %{x:,} orders<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(visible=False)
    fig.update_xaxes(range=[0, steps.orders.max() * 1.75], row=1, col=1)
    fig.update_xaxes(range=[0, side.orders.max() * 2.6], row=1, col=2)
    _style_axes(fig, 280)
    fig.update_yaxes(showgrid=False)
    for a, x in zip(
        fig.layout.annotations, (0, fig.layout.xaxis2.domain[0]), strict=True
    ):
        a.update(x=x, xanchor="left", font={"size": 12, "color": MUTED})
    return fig


def trend_figure(trend: pd.DataFrame, last_order_day=None):
    """Weekly orders and GMV (complete weeks), labelled peak and incomplete tail."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    t = trend[trend.is_complete_week == 1]
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=("Orders per week", "GMV per week (BRL)"),
    )
    for row, col, tmpl, name in (
        (1, "orders", "%{y:,.0f}", "Orders"),
        (2, "gmv", "BRL %{y:,.0f}", "GMV"),
    ):
        fig.add_trace(
            go.Scatter(
                x=t.week_start,
                y=t[col],
                name=name,
                mode="lines",
                line={"color": ACCENT, "width": 2},
                hovertemplate=tmpl + "<extra></extra>",
            ),
            row=row,
            col=1,
        )
        last = t.iloc[-1]
        label = fmt_int(last.orders) if col == "orders" else fmt_brl(last.gmv)
        fig.add_annotation(
            x=last.week_start,
            y=last[col],
            text=label,
            showarrow=False,
            xanchor="left",
            xshift=6,
            font={"size": 12, "color": ACCENT},
            row=row,
            col=1,
        )
    pk = peak_week(trend)
    peak_x = pd.Timestamp(pk["start"])
    fig.add_trace(
        go.Scatter(
            x=[peak_x],
            y=[pk["orders"]],
            mode="markers",
            marker={"color": ACCENT, "size": 8},
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    fig.add_annotation(
        x=peak_x,
        y=pk["orders"],
        text=f"{pk['name']}, {pk['start']:%d %b %Y}: {fmt_int(pk['orders'])} orders",
        showarrow=False,
        xanchor="right",
        xshift=-10,
        font={"size": 12, "color": TEXT},
        row=1,
        col=1,
    )
    # the incomplete tail: the data thins out, so these weeks are not drawn
    tail_start = pd.Timestamp(t.week_start.max()) + pd.Timedelta(days=7)
    end_day = pd.Timestamp(last_order_day or trend.week_start.max()) + pd.Timedelta(
        days=1
    )
    last_day = end_day - pd.Timedelta(days=1)
    if end_day > tail_start:
        for row in (1, 2):
            fig.add_vrect(
                x0=tail_start,
                x1=end_day,
                fillcolor=BAR_LIGHT,
                opacity=0.7,
                line_width=0,
                layer="below",
                row=row,
                col=1,
            )
        fig.add_annotation(
            yref="y domain",
            y=1.0,
            text=f"Shaded: not drawn, orders thin out in {last_day:%b %Y}",
            showarrow=False,
            xref="x domain",
            x=1,
            xanchor="right",
            yanchor="bottom",
            yshift=6,
            font={"size": 11, "color": MUTED},
        )
        fig.update_xaxes(range=[t.week_start.min(), end_day])
    fig.update_yaxes(rangemode="tozero", tickformat=",")
    _style_axes(fig, 520, unified=True)
    fig.update_xaxes(hoverformat="%d %b %Y", tickformat="%b %Y")
    for a in fig.layout.annotations[:2]:
        a.update(x=0, xanchor="left", font={"size": 12, "color": MUTED})
    return fig


PLOT_CONFIG = {"displayModeBar": False, "responsive": True, "displaylogo": False}


def build_html(blocks: dict[str, pd.DataFrame], generated: date | None = None) -> str:
    """Assemble the whole page as one HTML string."""
    generated = generated or date.today()
    cards = make_cards(blocks["kpi"], blocks["monthly"])
    s = story(blocks)
    meta = blocks["meta"].iloc[0]
    cat, state, seller = blocks["category"], blocks["state"], blocks["seller"]
    bench_late = cat.benchmark_late_share.iloc[0]
    bench_review = cat.benchmark_review.iloc[0]
    cur_month = month_label(
        blocks["kpi"].set_index("period").loc["current"].month_start
    )

    funnel_html = funnel_figure(blocks["funnel"]).to_html(
        full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG
    )
    trend_html = trend_figure(blocks["trend"], meta.last_order_date).to_html(
        full_html=False, include_plotlyjs=False, config=PLOT_CONFIG
    )
    cat_tbl = _table_html(
        cat, "Product category", [humanize_category(c) for c in cat.category]
    )
    state_tbl = _table_html(
        state, "Customer state", [state_label(c) for c in state.state]
    )
    seller_tbl = _table_html(
        seller,
        "Seller (first 8 characters of the id)",
        [seller_label(r.seller_id, r.seller_state) for r in seller.itertuples()],
    )
    first = pd.Timestamp(meta.first_order_date).strftime("%Y-%m-%d")
    last = pd.Timestamp(meta.last_order_date).strftime("%Y-%m-%d")
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist: Sales &amp; Operations dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONT_URL}">
<style>{CSS}</style></head>
<body><div class="page">
<header>
<p class="kicker">Olist marketplace · Sales &amp; Operations</p>
<h1>{e(s["headline"])}</h1>
<p class="sowhat">{e(s["sowhat"])}</p>
<p class="note">Portfolio project: the requirements are simulated (no real client),
the data is the public Olist dataset. Cards show {e(cur_month)}, the last complete
month; definitions are in <code>docs/dashboard_spec.md</code>.</p>
</header>

{_cards_html(cards)}

<section>
<h2>{e(s["funnel_title"])}</h2>
{funnel_html}
<p class="note">Whole analysis window. A step counts when its timestamp is filled in.
The accent bar marks the biggest drop between two steps.</p>
</section>

<section>
<h2>{e(s["trend_title"])}</h2>
{trend_html}
<p class="note">Complete weeks only; the shaded part is not drawn because order
volume thins out at the very end of the data.</p>
</section>

<section>
<h2>Where the money and the delays are</h2>
<div class="two">
<div><p class="tbl-title">{e(s["category_title"])}</p>{cat_tbl}</div>
<div><p class="tbl-title">{e(s["state_title"])}</p>{state_tbl}</div>
</div>
{_legend(bench_late, bench_review)}
</section>

<section>
<h2>{e(s["seller_title"])}</h2>
<div class="narrow">{seller_tbl}</div>
</section>

<div class="footer">
<b>Data source:</b> Olist Brazilian E-Commerce Public Dataset (Kaggle); orders
purchased {first} to {last} (analysis window), {fmt_int(meta.window_orders)} orders,
{fmt_int(meta.sales_orders)} of them sales orders with total GMV
{fmt_brl(meta.total_gmv)}. Data: Olist, CC BY-NC-SA 4.0.<br>
<b>Requirements:</b> simulated for this portfolio project.
<b>Updated:</b> {generated:%Y-%m-%d} (static snapshot; refresh with
<code>python -m pa.dashboard</code>). Analysis: Anastasia Kalugina.
</div>
</div></body></html>
"""


# ---------------------------------------------------------------- PNG preview


def _pick_font() -> str:
    """Inter or IBM Plex Sans when installed, otherwise DejaVu Sans."""
    from matplotlib import font_manager

    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Inter", "IBM Plex Sans"):
        if name in have:
            return name
    return "DejaVu Sans"


def build_png(blocks: dict[str, pd.DataFrame], path: Path) -> None:
    """Static preview for the README, in the same visual language as the page."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = _pick_font()
    plt.rcParams["text.color"] = TEXT
    plt.rcParams["axes.facecolor"] = PAGE_BG
    cards = make_cards(blocks["kpi"], blocks["monthly"])
    s = story(blocks)
    fig = plt.figure(figsize=(15, 16), facecolor=PAGE_BG)
    gs = fig.add_gridspec(
        5,
        10,
        height_ratios=[1.7, 1.6, 2.3, 3.2, 4.4],
        hspace=0.5,
        wspace=0.9,
        left=0.11,
        right=0.95,
        top=0.97,
        bottom=0.03,
    )

    def clean(ax, keep_left=False):
        for sp in ("top", "right", "bottom", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0, labelcolor=MUTED, labelsize=9)
        if not keep_left:
            ax.set_yticks([])

    # header: kicker, headline, so-what
    ax = fig.add_subplot(gs[0, :])
    ax.axis("off")
    ax.text(
        0,
        1.0,
        "OLIST MARKETPLACE · SALES & OPERATIONS",
        fontsize=9,
        color=ACCENT,
        fontweight="bold",
        va="top",
    )
    ax.text(
        0,
        0.86,
        textwrap.fill(s["headline"], 78),
        fontsize=19,
        fontweight="bold",
        va="top",
        linespacing=1.3,
    )
    ax.text(
        0,
        0.12,
        textwrap.fill(s["sowhat"], 120),
        fontsize=10.5,
        va="top",
        linespacing=1.4,
    )
    ax.text(
        0,
        -0.55,
        "Requirements are simulated; data: public Olist dataset.",
        fontsize=8.5,
        color=MUTED,
        va="top",
    )

    # cards with sparklines
    for i, card in enumerate(cards):
        ax = fig.add_subplot(gs[1, 2 * i : 2 * i + 2])
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(
            0,
            0.97,
            card.label + (" · North Star" if card.north_star else ""),
            fontsize=8,
            color=MUTED,
            va="top",
        )
        ax.text(0, 0.80, card.value, fontsize=19, fontweight="bold", va="top")
        for j, d in enumerate(card.deltas):
            ax.text(
                0,
                0.45 - 0.14 * j,
                d.text,
                fontsize=7.8,
                color=TONE_COLOR[d.tone],
                va="top",
            )
        vals = [v for v in card.spark if pd.notna(v)]
        if len(vals) > 1:
            inset = ax.inset_axes([0, -0.02, 0.9, 0.2])
            inset.axis("off")
            inset.plot(range(len(vals)), vals, color=BAR_GREY, lw=1.5)
            inset.plot(len(vals) - 1, vals[-1], "o", color=ACCENT, ms=4)
            inset.margins(0.05, 0.2)

    # funnel
    fun = blocks["funnel"]
    steps = fun[fun.kind == "step"].reset_index(drop=True)
    drops = (steps.orders.shift(1) - steps.orders).fillna(0)
    biggest = int(drops.iloc[1:].idxmax())
    ax = fig.add_subplot(gs[2, :])
    ax.set_title(
        textwrap.fill(s["funnel_title"], 130),
        loc="left",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax.barh(
        steps.stage,
        steps.orders,
        color=[ACCENT if i == biggest else BAR_GREY for i in steps.index],
        height=0.62,
    )
    for y, r in enumerate(steps.itertuples()):
        t = fmt_int(r.orders)
        if y > 0:
            t += (
                f"   {fmt_pct(r.step_conversion)} of previous step · "
                f"−{fmt_int(drops[y])}"
            )
        ax.text(r.orders + steps.orders.max() * 0.01, y, t, va="center", fontsize=9)
    ax.set_xlim(0, steps.orders.max() * 1.6)
    ax.invert_yaxis()
    clean(ax, keep_left=True)
    ax.set_xticks([])
    ax.tick_params(labelsize=10, labelcolor=TEXT)
    side = fun[fun.kind != "step"]
    lost = "  ·  ".join(
        f"{r.stage.lower()} {fmt_int(r.orders)} ({fmt_pct(r.share_of_purchased, 2)})"
        for r in side.itertuples()
    )
    ax.text(
        0,
        -0.04,
        "Not delivered: " + lost,
        transform=ax.transAxes,
        fontsize=8.5,
        color=MUTED,
        va="top",
    )

    # trend: two stacked panels, direct labels, annotated peak and tail
    trend = blocks["trend"]
    t = trend[trend.is_complete_week == 1]
    pk = peak_week(trend)
    sub = gs[3, :].subgridspec(2, 1, hspace=0.45)
    tail0 = pd.Timestamp(t.week_start.max()) + pd.Timedelta(days=7)
    tail1 = pd.Timestamp(blocks["meta"].iloc[0].last_order_date) + pd.Timedelta(days=1)
    for k, (col, ttl, lab) in enumerate(
        (("orders", "Orders per week", fmt_int), ("gmv", "GMV per week (BRL)", fmt_brl))
    ):
        ax = fig.add_subplot(sub[k])
        if k == 0:
            ax.set_title(
                textwrap.fill(s["trend_title"], 130),
                loc="left",
                fontsize=12,
                fontweight="bold",
                pad=22,
            )
        ax.text(0, 1.02, ttl, transform=ax.transAxes, fontsize=9, color=MUTED)
        ax.plot(t.week_start, t[col], color=ACCENT, lw=2)
        ax.axvspan(tail0, tail1, color=BAR_LIGHT, lw=0)
        ax.set_xlim(t.week_start.min(), tail1)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        clean(ax, keep_left=True)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
        ax.text(
            t.week_start.iloc[-1],
            t[col].iloc[-1],
            "  " + lab(t[col].iloc[-1]),
            color=ACCENT,
            fontsize=9,
            va="center",
        )
        if k == 0:
            px = pd.Timestamp(pk["start"])
            ax.plot(px, pk["orders"], "o", color=ACCENT, ms=5)
            ax.text(
                px - pd.Timedelta(days=8),
                pk["orders"],
                f"{pk['name']}, {pk['start']:%d %b %Y}: {fmt_int(pk['orders'])} orders",
                ha="right",
                va="center",
                fontsize=9,
            )
            ax.text(
                tail0 + (tail1 - tail0) / 2,
                ax.get_ylim()[1] * 0.97,
                f"Not shown:\norders thin\nout in {tail1 - pd.Timedelta(days=1):%b %Y}",
                ha="center",
                va="top",
                fontsize=7.5,
                color=MUTED,
            )
        if k == 0:
            ax.set_xticklabels([])

    # tables: top 8 categories and top 8 sellers, inline bars, two tinted cells
    def draw_table(spec, df, labels, title):
        axt = fig.add_subplot(spec)
        axt.axis("off")
        n = len(df)
        axt.set_xlim(0, 1)
        axt.set_ylim(n + 1.2, -2.6)
        axt.text(
            0,
            -1.9,
            textwrap.fill(title, 62),
            fontsize=10.5,
            fontweight="bold",
            va="top",
            linespacing=1.3,
        )
        cols = {"gmv": 0.66, "orders": 0.79, "late": 0.90, "rev": 1.0}
        for key, label in (
            ("gmv", "GMV"),
            ("orders", "Orders"),
            ("late", "Late %"),
            ("rev", "Review"),
        ):
            axt.text(
                cols[key], 0, label, ha="right", va="center", fontsize=8, color=MUTED
            )
        axt.plot([0, 1], [0.55, 0.55], color=BAR_GREY, lw=0.8)
        top = df.gmv.max()
        pick = {"good": ACCENT_TINT, "bad": WARM_TINT}
        for i, (r, label) in enumerate(zip(df.itertuples(), labels, strict=True), 1):
            axt.barh(
                i,
                0.22 * r.gmv / top,
                left=cols["gmv"] - 0.22,
                height=0.62,
                color=BAR_LIGHT,
            )
            axt.text(0, i, label, va="center", fontsize=8.5)
            axt.text(
                cols["gmv"], i, fmt_brl(r.gmv), ha="right", va="center", fontsize=8.5
            )
            axt.text(
                cols["orders"],
                i,
                fmt_int(r.orders),
                ha="right",
                va="center",
                fontsize=8.5,
            )
            for key, val, tone in (
                (
                    "late",
                    fmt_pct(r.late_share),
                    cell_tone(r.late_share, r.benchmark_late_share, False, LATE_MARGIN),
                ),
                (
                    "rev",
                    fmt_score(r.avg_review),
                    cell_tone(r.avg_review, r.benchmark_review, True, REVIEW_MARGIN),
                ),
            ):
                if tone:
                    axt.add_patch(
                        plt.Rectangle(
                            (cols[key] - 0.085, i - 0.45),
                            0.095,
                            0.9,
                            color=pick[tone],
                            lw=0,
                        )
                    )
                axt.text(
                    cols[key] - 0.005, i, val, ha="right", va="center", fontsize=8.5
                )

    cat = blocks["category"].head(8)
    draw_table(
        gs[4, :5],
        cat,
        [humanize_category(c) for c in cat.category],
        s["category_title"],
    )
    sel = blocks["seller"].head(8)
    draw_table(
        gs[4, 5:],
        sel,
        [seller_label(r.seller_id, r.seller_state) for r in sel.itertuples()],
        s["seller_title"],
    )
    fig.text(
        0.11,
        0.012,
        "Tint: teal better, orange worse than the all-orders average "
        "(late: 1 pp, review: 0.1 points). Tables show the top 8 rows; the HTML has "
        "15 rows and all states. Data: Olist, CC BY-NC-SA 4.0.",
        fontsize=8,
        color=MUTED,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor=PAGE_BG)
    plt.close(fig)


# ------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pa.dashboard")
    parser.add_argument("--db", type=Path, default=config.OLIST_DB)
    parser.add_argument(
        "--html", type=Path, default=config.DASHBOARD_DIR / "olist_dashboard.html"
    )
    parser.add_argument(
        "--png", type=Path, default=config.FIGURES_DIR / "olist_dashboard_preview.png"
    )
    parser.add_argument("--no-png", action="store_true", help="skip the PNG preview")
    args = parser.parse_args(argv)
    if not args.db.exists():
        print(
            f"missing {args.db}; run `python -m pa.data build` first", file=sys.stderr
        )
        return 1
    con = connect(args.db, read_only=True)
    try:
        blocks = load_blocks(con)
    finally:
        con.close()
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(blocks), encoding="utf-8")
    print(f"wrote {args.html}")
    if not args.no_png:
        build_png(blocks, args.png)
        print(f"wrote {args.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
