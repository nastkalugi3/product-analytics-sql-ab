> **Note.** Original plan written before the stress test; superseded where it
> mentions CACE estimate, per-1M business conclusion, ROI sensitivity and
> |SMD|<0.1 balance. See README and notebook 03 for the final framing.

# Plan: product-analytics-sql-ab (architect, 2026-10-15)

Goal: portfolio repo showing SQL + A/B testing for junior data analyst vacancies. No ML.

## Data (licences checked 2026-10-15, both CC BY-NC-SA 4.0; data NOT committed, downloaded by script)
- Olist Brazilian E-Commerce — https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce — 9 tables, ~100k orders 2016–2018, 126 MB. Download: `kagglehub.dataset_download("olistbr/brazilian-ecommerce")` (public, may work without token; fallback: manual download to data/raw/olist/ or ~/.kaggle/kaggle.json — describe in README).
- Criteo Uplift Prediction **v2.1** — https://ailab.criteo.com/criteo-uplift-prediction-dataset/ — real randomized ad test, treatment share ~0.85, labels visit/conversion/exposure, features f0–f11 anonymised pre-treatment. 13,979,592 rows, 16 cols, ~297 MB gz. URL: https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz (go.criteo.net dead as of 2026-10-15) . Use v2.1 (original had a leak, see erratum on page). Citation required: Diemert E. et al. A Large Scale Benchmark for Uplift Modeling. AdKDD 2018.
- Code MIT; DATA_LICENSE.md with both licences, links, citation, check date; figures in reports/figures marked CC BY-NC-SA with attribution.

## Scope
Do: 11 SQL queries on Olist in DuckDB, PostgreSQL-compatible subset (checked by sqlglot parse read="postgres"); full A/B cycle on Criteo (design, A/A, SRM, covariate balance, metrics, CUPED, bootstrap, ITT + CACE, Holm, business conclusion, limitations); pytest + CI.
Don't: ML/uplift models, Docker, DB server, dashboard, running notebooks in CI.

## Stack
Python 3.14 locally; CI matrix 3.13/3.14. duckdb (pin the installed version), pandas, numpy, scipy, matplotlib, pyarrow, kagglehub, jupyter/nbconvert. Dev: pytest, ruff, sqlglot. No statsmodels (own power/MDE formulas, tested).

## Tree
```
product-analytics-sql-ab/
├── README.md / README.ru.md
├── LICENSE (MIT, "Anastasia Kalugina", 2026)
├── DATA_LICENSE.md
├── pyproject.toml          # ruff line-length 88, pytest config (pythonpath=["src"], testpaths)
├── requirements.txt / requirements-dev.txt (pinned)
├── run_all.sh              # download -> build -> execute notebooks
├── .gitignore              # data/, *.duckdb, *.parquet, .ipynb_checkpoints, .venv, __pycache__, .claude/
├── .github/workflows/ci.yml
├── data/                   # gitignored
├── sql/
│   ├── schema/olist_views.sql
│   ├── olist/01_data_quality.sql … 11_payments.sql
│   └── ab/01_group_sizes.sql 02_group_metrics.sql 03_covariate_balance.sql 04_segment_metrics.sql
├── src/pa/ __init__.py config.py data.py db.py stats.py
├── notebooks/ 01_olist_sql_analytics.ipynb 02_ab_design.ipynb 03_ab_analysis.ipynb
├── reports/figures/*.png
└── tests/ conftest.py fixtures/olist_mini/*.csv test_sql_olist.py test_sql_ab.py test_sql_dialect.py test_stats.py
```
config.py: paths, SEED=42, ALPHA=0.05, EXPECTED_TREATMENT_SHARE=0.85.
data.py: download_olist(), download_criteo(), build_olist_db(), build_criteo_parquet(sample_frac=None); CLI `python -m pa.data {download,build}` with `--criteo-sample-frac`.
db.py: connect(path), load_sql(name)->str, run_sql(con, name, **params)->DataFrame.

## SQL rules
Only constructs valid in both DuckDB and PostgreSQL: CTE, window functions, date_trunc, EXTRACT, FILTER (WHERE …), percentile_cont … WITHIN GROUP. NO QUALIFY, GROUP BY ALL, DuckDB list functions. Month diff: EXTRACT(year)*12+EXTRACT(month). Customer = customer_unique_id (customer_id is per order — main trap). Trim near-empty edge months (late 2016, after Aug 2018); threshold set in 01, explained in notebook.

Olist questions (one file each):
1 data_quality — row counts, PK uniqueness, orphan FKs, orders per month.
2 monthly_kpi — GMV, orders, AOV, buyers per month, MoM via LAG.
3 order_funnel — purchase→approved→carrier→delivered conversion, median hours between steps, canceled/unavailable shares.
4 delivery_sla — late share (delivered > estimated) by state, avg review_score on-time vs late.
5 top_categories — top-3 categories by revenue per quarter (ROW_NUMBER in subquery), English names.
6 cohort_retention — monthly first-purchase cohorts, retention M0…M6.
7 repeat_purchase — share of repeat customers, days to 2nd order (LEAD), median.
8 rfm — NTILE(5) RFM, segment sizes and revenue.
9 seller_pareto — cumulative revenue share by seller; share of sellers giving 80%.
10 rolling_orders — 7-day moving avg of orders, Black Friday 2017 peak.
11 payments — payment types, installments and AOV, multi-method orders.

A/B SQL on Criteo parquet: group sizes; group metrics (n, sums visit/conversion/exposure, visit×conversion cells); covariate balance (mean/sd f0–f11 by group); segment metrics by quartiles of a pre-chosen feature.

## A/B design
Unit = user. H1: ads increase visit share. Primary: visit. Secondary: conversion (~0.23%). Guardrail: conversion|visit — descriptive only (conditions on post-treatment). Delivery check: exposure in treatment.
α=0.05 two-sided. MDE at actual n and required n for 1/2/5% relative MDE — computed in nb02 BEFORE looking at group results. SRM: χ² vs 0.85, threshold p<0.001. Test: z-test for proportions (≈ Welch t on binary at this n); no Mann–Whitney (justify). Bootstrap CI, CUPED, Holm for secondary metrics and segments.

stats.py (pure functions, frozen dataclass results):
```python
srm_check(n_control, n_treatment, expected_treatment_share) -> SRMResult  # chi2, p_value, observed_share
proportion_test(x_c, n_c, x_t, n_t, alpha=0.05) -> TestResult  # abs_diff, rel_diff, ci_low, ci_high (unpooled SE), p_value (pooled SE)
mde_proportion(p_base, n_c, n_t, alpha=0.05, power=0.8) -> float  # absolute
sample_size_proportion(p_base, mde_rel, alpha=0.05, power=0.8, ratio=1.0) -> tuple[int, int]
bootstrap_cells(cells_c, cells_t, metric, n_boot=2000, seed=42, alpha=0.05) -> BootResult  # multinomial on cell counts
cuped(y, x) -> CupedResult  # y_adj, theta (pooled), variance_reduction
aa_false_positive_rate(y, n_iter=1000, sample_size=200_000, seed=42, alpha=0.05) -> float
holm(p_values) -> np.ndarray
cace(itt_abs, exposure_rate_t, exposure_rate_c=0.0) -> float
smd(mean_c, mean_t, sd_c, sd_t) -> float
```
Memory: load only needed columns via DuckDB (treatment/metrics int8, 1–2 covariates float32).

## Notebooks (goal → data → EDA → main → conclusions → sources; markdown before each code cell, takeaway after result; PEP 8 via ruff; SEED from config; labelled plots; runs top-to-bottom with nbconvert --execute; outputs SAVED in the committed notebooks)
- 01_olist_sql_analytics: ER diagram (mermaid), customer_id trap, files 01–11 each: question, SQL via run_sql, table/plot, 1–2 sentence takeaway. 5–7 business conclusions (correlation ≠ causation).
- 02_ab_design (pre-registration, no group results): context, why v2.1, pooled base rates, hypotheses, metrics, α, MDE/sample-size table, SRM plan, test choice, A/A FPR simulation on control (~0.05), CUPED covariate chosen by correlation in control, segments + Holm.
- 03_ab_analysis: SRM → balance (|SMD|<0.1) → exposure → primary z-test + CI + bootstrap CI → CUPED variance reduction + new CI → secondary + guardrail with Holm → CACE → segments (exploratory) → business: "+X visits, +Y conversions per 1M users"; ROI only as sensitivity table labelled assumption. Limitations: anonymised features; dataset may pool several tests (verify in Diemert 2018) → Simpson risk; 0.85 approximate; huge power → significance ≠ practical importance. Sources.

## Steps & acceptance
1 Skeleton; `pip install -r requirements-dev.txt` OK on 3.14; `ruff check .` clean.
2 data.py; criteo 13,979,592 rows, treatment share ≈0.85; olist 9 tables, PKs unique.
3 stats.py + tests: SRM 50/50 p=1, strong skew p<1e-6; proportion_test z² == scipy chi2_contingency(correction=False); round-trip mde(n=sample_size(mde))≈mde rtol 1e-2; Holm hand example; bootstrap same seed same CI and covers true diff on synthetic; CUPED unbiased mean, reduction ≈ρ² ±0.02; A/A FPR in [0.03,0.07]; CACE = ITT/exposure.
4 Olist SQL + db.py + hand-made olist_mini fixture (one customer_unique_id with two customer_ids in different months → M2 retention = 1; one late delivery; one canceled) with exact expected numbers per file; sqlglot parses all files read="postgres".
5 A/B SQL on synthetic criteo-mini (2000 rows, seed 42, generated in conftest, not committed); sums match pandas.
6–8 Notebooks executed on full data, 3–4 PNGs, conclusions cite concrete numbers from outputs.
9 CI: ubuntu, matrix 3.13/3.14, checkout@v4, setup-python@v5, pip install -r requirements-dev.txt, ruff check ., pytest -q. No data download in CI.
10 README EN/RU: task, data + licences, 4–6 key numbers each traceable to a notebook cell, figures, how to run, limitations, "SQL skills: which construct where", note that sqlglot checks syntax only.

## Risks
kagglehub may need token; Criteo URL may redirect/change (check size and rows); SRM may fire due to rounded 0.85 — report observed share honestly; huge power; pooled tests/Simpson; biased guardrail; customer_id trap; near-empty retention matrix is a finding; edge months; date semantic differences; memory; wheels for 3.14; NC-SA — never commit data.
