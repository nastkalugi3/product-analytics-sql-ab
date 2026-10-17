# Dashboard requirements: Sales & Operations (Olist)

[Русская версия](dashboard_spec.ru.md)

> **This document is simulated.** There is no real client. I wrote it the way I would
> after interviewing a Head of Sales & Operations, to show the method "decisions first,
> then metrics, then the picture". The person, the questions asked and the answers are
> invented; the data and every number below are real Olist figures from this repository.
> Data checked on 2026-10-17 against `data/olist.duckdb`.

## 1. Context

Olist is a Brazilian marketplace: customers order from many independent sellers. The
fictional Head of Sales & Operations owns two things: how much the marketplace sells
and whether orders reach customers on time. Today she gets numbers from separate
exports, and nobody agrees on what a "sale" or a "late order" is. The dashboard is one
page with agreed definitions.

## 2. Users and the decisions it supports

| User | Looks | Decision the page should support |
|---|---|---|
| Head of Sales & Operations | weekly, and at month end | Is the month on track? Which region or category needs attention? Is it a sales problem or a delivery problem? |
| Logistics / carrier manager | weekly | Which states and sellers have late deliveries? Which carrier contract or region to review? |
| Seller manager (the "per-manager" view) | weekly | Which of the biggest sellers to call about late deliveries or low reviews? |
| Category manager | monthly | Which categories grow, which have low reviews? |

Out of scope: pricing, marketing channels (Olist data has no channel or cost fields),
individual customers.

## 3. North Star and guardrails

- **North Star: monthly GMV** (items price plus freight of valid orders). The Head of
  Sales & Operations: "If one number is good, the month was good."
- **Guardrails** (GMV can be bought by shipping late or shipping badly):
  late-delivery share and average review score. A GMV rise with a rise in late
  deliveries is shown as a warning, not as a success.
- Supporting metrics: orders and average order value (they explain a GMV change:
  more orders or bigger orders).

There are **no plans or targets** in Olist data. So the comparison is "against the
previous month and the same month a year earlier", and in tables "against the
average of all orders". With real plans the cards would show "actual vs plan".

## 4. Metric definitions

One definition per metric, used in every block. Source files are in
`sql/dashboard/`; the base views are in `sql/schema/olist_views.sql`.

| Metric | Exact formula | SQL source | Grain |
|---|---|---|---|
| Sales order | order in the analysis window (purchased 2017-01-01 to 2018-08-31), status not `canceled` or `unavailable`, with at least one item | view `sales_orders` | order |
| GMV | `SUM(price + freight_value)` over the items of sales orders | `01_kpi_cards`, `03_weekly_trend`, `04`-`06` | month, week, category, state, seller |
| Orders | `COUNT` of sales orders | same | same |
| Average order value (AOV) | GMV / Orders | `01_kpi_cards`, `03_weekly_trend` | month, week |
| Late deliveries, % | delivered orders with `delivered date > estimated date`, divided by delivered orders. Delivered = status `delivered` and the delivery timestamp filled. Dates are compared as dates (estimates have no time of day) | `01_kpi_cards`, `04`-`06` | month, category, state, seller |
| Average review score | mean over orders of the order's mean `review_score` (one order can have several reviews). Orders without a review are left out | `01_kpi_cards`, `04`-`06` | same |
| Step conversion | orders that reached a step / orders that reached the previous step | `02_funnel` | funnel step |
| Share of purchased | orders at a step (or lost) / all purchased orders in the window | `02_funnel` | funnel step |
| Share of GMV | segment GMV / total GMV in the window | `04`-`06` | category, state, seller |
| Month of an order | month of the purchase timestamp | `01_kpi_cards`, `03_weekly_trend` | month, week |

Rules that matter:

- **Customers are not counted** in this dashboard. In Olist `customer_id` is created
  per order; the real person is `customer_unique_id` (see section 8). If a customer
  metric is added later, it must use `customer_unique_id`.
- **"Last complete month"** for the cards: the latest month whose last 7 days still
  have at least half of that month's average daily order count. For this data it is
  **July 2018**, not August 2018 (section 8, last item).
- **Category and seller tables:** an order with items from several categories (or
  sellers) is counted once in each. So order counts in those tables add up to more
  than total orders, while GMV adds up exactly. Lateness and review of the order are
  attributed to every category or seller in it.
- **12-month late share** in the headline text: pooled over the 12 months that end
  with the card month (all late orders divided by all delivered orders), next to the
  median of the 12 monthly late shares. The median is given because single months
  (2017-11 and 2018-03 are far above the rest) pull the pooled share up.
- **Trend headline:** compares the last 4 complete weeks with the same 4 weeks a year
  earlier (364 days back). The first weeks of 2017 are not used as a baseline: that
  is the ramp-up of the data (about 270 orders a week against about 900 a year later).
- **Highlighting:** a table cell is tinted teal (better) or orange (worse) when it
  is better or worse than the all-orders average (late 6.79%, review 4.12 in the window) by more than 1
  percentage point (late) or 0.1 score points (review). These margins are my
  simulated choice; the "client" would set real ones.

## 5. Funnel steps

Olist keeps only the latest `order_status`, not a history. So the funnel counts a step
as reached when its timestamp is filled in (same idea as in `sql/olist/03`):

| Step | Counted when | Orders (window) |
|---|---|---|
| 1. Purchased | every order in the window | 99,092 |
| 2. Approved | `order_approved_at` is filled | 98,957 |
| 3. Handed to carrier | `order_delivered_carrier_date` is filled | 97,376 |
| 4. Delivered | `order_delivered_customer_date` is filled | 96,204 |

Losses are counted by status: **canceled** 580 and **unavailable** 602. A third group,
**in progress** (1,699), has a non-final status (created, approved, invoiced,
processing, shipped); these orders are neither delivered nor lost yet.

Order statuses in the window (all 99,092 orders): delivered 96,211; shipped 1,097;
unavailable 602; canceled 580; processing 299; invoiced 296; created 5; approved 2.
The statuses `invoiced` and `processing` have no timestamps in the data, so they
cannot be separate funnel steps. The step counts by timestamp (96,204 delivered) and by
status (96,211 delivered) differ slightly because of the timestamp gaps in section 8.

## 6. Slices

- Time: month (cards), week (trend).
- Product category (top 15 by GMV, English names from the translation table).
- Customer state (all 27, with full state names).
- Seller (top 15 by GMV; shown as the first 8 characters of the id plus the seller's
  state, because the data has no seller names).

Filters (period, department) are **not built**: the output is one static HTML file.
In a BI tool (DataLens, Metabase, Power BI) these would be dashboard filters over the
same queries.

## 7. Refresh

- Production proposal: daily, early morning, because the Head looks weekly and at
  month end and nobody acts on hourly changes.
- In this repository: a static snapshot. `python -m pa.dashboard` rebuilds the file
  from `data/olist.duckdb`; the date of the build is in the footer. Olist data ends
  in 2018, so there is nothing to refresh.
- Alerts (proposed, not built): weekly late-delivery share above a set limit sends a
  message to the logistics manager.

## 8. Data-quality issues found

All figures are for the analysis window (orders purchased 2017-01-01 to 2018-08-31,
99,092 orders; the first order in the data is on 2017-01-05), checked by queries on
2026-10-17.

1. **`customer_id` is not a customer.** 99,092 orders have 99,092 different
   `customer_id`s but only 95,774 different `customer_unique_id`s. 2,975 people placed
   more than one order. Counting customers by `customer_id` would overstate them.
2. **Missing or contradictory timestamps.** 8 orders have status `delivered` but no
   delivery date; 14 delivered orders have no approval date; 2 delivered orders have
   no carrier date; 1 canceled order has a delivery date. 1,359 orders have a carrier
   handover date earlier than the approval date, and 19 orders have a delivery date
   earlier than the carrier date. The dashboard uses timestamps as they are and counts
   such orders in each step whose timestamp exists.
3. **Orders without items.** 739 orders have no items (602 unavailable, 132 canceled,
   5 created), so their GMV is undefined. They are in the funnel, not in GMV.
4. **Status is a snapshot, not a history.** There is no event log, so "time in status"
   cannot be measured, and `invoiced` / `processing` have no timestamps.
5. **Reviews.** 727 of the 97,905 sales orders have no review; 539 have more than one
   (averaged per order).
6. **Categories.** 1,435 sales orders contain an item without a category (shown as
   "unknown"); 20 have a category with no English translation (shown in Portuguese).
   783 orders have items from more than one category (counting "unknown" as one) and 1,274 from more than one
   seller.
7. **Delivery estimates have no time of day**, so "late" is a comparison of dates.
8. **The data thins out at its end.** Daily orders are 256 on 2018-08-20 and 243 on
   2018-08-21, then fall to 14 on 2018-08-29, 4 on 2018-08-30 and 1 on 2018-08-31.
   I do not know the reason and did not investigate it. August 2018 is therefore
   not comparable with other months, and the cards and the trend stop at July 2018.

## 9. Layout sketch

```
+--------------------------------------------------------------------------+
| Olist marketplace: Sales & Operations      [simulated requirements banner]|
+-----------+-----------+-----------+------------------+-------------------+
| GMV  *    | Orders    | AOV       | Late deliveries  | Avg review score  |
| 1.04M     | 6,233     | 166.82    | 3.4%             | 4.29              |
| v prev mo | v prev mo | v prev mo | v prev mo        | v prev mo         |
| v year ago| v year ago| v year ago| v year ago       | v year ago        |
+-----------+-----------+-----------+------------------+-------------------+
| Funnel: purchased > approved > carrier > delivered | Lost / still open   |
+--------------------------------------------------------------------------+
| Weekly orders (line)                                                     |
| Weekly GMV (line)                                                        |
+-----------------------------------+--------------------------------------+
| Top 15 categories (table)         | Customer states (table)              |
+-----------------------------------+--------------------------------------+
| Top 15 sellers (table, tinted late % and review)                        |
+--------------------------------------------------------------------------+
| Footer: data source, licence, analysis window, update date               |
+--------------------------------------------------------------------------+
```

Design rules: one question per block, human labels, colours by meaning (orange
only for bad, the teal accent for good, an arrow and a sign as well as a colour), no pie charts,
light background, context for every number (previous month, year ago, average).

## 10. Acceptance check ("done")

- Each card matches the SQL result (`sql/dashboard/01_kpi_cards.sql`) and a
  hand-checked fixture test (`tests/test_sql_dashboard.py`).
- Metric definitions in section 4 are the same as in the SQL files.
- The footer shows source, licence credit and the window dates.
- Real feedback round: not done (the client is simulated). In a real project the next
  step is a prototype review with the user and one iteration on the definitions.
