# Data licences

The code in this repository is MIT-licensed (see `LICENSE`). The data is **not**
part of the repository and is **not** covered by the MIT licence. Both datasets
are published under **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-
ShareAlike 4.0 International, https://creativecommons.org/licenses/by-nc-sa/4.0/).
Licences checked on 2026-10-15.

Do not commit raw or processed data (`data/` is in `.gitignore`). Use is limited to
non-commercial purposes; derived material must carry the same licence and credit.

## Olist Brazilian E-Commerce Public Dataset

- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- Publisher: Olist (and Andre Sionek, who uploaded it to Kaggle).
- Content: about 100k orders from 2016 to 2018 in 9 tables.
- Download: `python -m pa.data download --only olist` (or manually from Kaggle into
  `data/raw/olist/`).

## Criteo Uplift Prediction Dataset v2.1

- Source: https://ailab.criteo.com/criteo-uplift-prediction-dataset/
- File: https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz (official Criteo organisation on Hugging Face, same licence; the original go.criteo.net link stopped working in October 2026)
- Terms: the dataset page states the data terms of use are the CC BY-NC-SA 4.0
  public licence.
- Version 2.1 is the corrected version (the first release had a leak, see the
  erratum on the dataset page).
- Required citation: Diemert, E., Betlei, A., Renaudin, C., Amini, M.-R.
  *A Large Scale Benchmark for Uplift Modeling*. Proceedings of the AdKDD and
  TargetAd Workshop, KDD, London, August 2018.

## Figures

Pictures in `reports/figures/` are computed from these datasets, so they are shared
under CC BY-NC-SA 4.0 with attribution to Olist (Olist dataset) and Criteo AI Lab
(Criteo dataset). Author of the analysis: Anastasia Kalugina.
