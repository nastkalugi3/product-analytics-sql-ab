#!/usr/bin/env bash
# Download data (skipped if present), build the database and parquet file,
# execute the notebooks, build the dashboard. Run from anywhere: ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi
export PYTHONPATH=src

python -m pa.data download   # each dataset is skipped if already downloaded
python -m pa.data build

# 02 must run before 03: it writes docs/preregistration.json
for nb in notebooks/01_olist_sql_analytics.ipynb \
          notebooks/02_ab_design.ipynb \
          notebooks/03_ab_analysis.ipynb; do
    jupyter nbconvert --to notebook --execute --inplace "$nb"
done
python -m pa.dashboard       # reports/dashboard/olist_dashboard.html + preview PNG
echo "done: notebooks executed, figures in reports/figures/, dashboard in reports/dashboard/"
