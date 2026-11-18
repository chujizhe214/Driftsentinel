# Public demo data and model

- Dataset: **Bank Marketing**, UCI Machine Learning Repository.
- Creators: Sérgio Moro, Paulo Cortez, Paulo Rita.
- Source: https://archive.ics.uci.edu/dataset/222/bank+marketing
- DOI: https://doi.org/10.24432/C5K306
- License: Creative Commons Attribution 4.0 International (CC BY 4.0).
- License text: https://creativecommons.org/licenses/by/4.0/
- Original archive: https://archive.ics.uci.edu/static/public/222/bank+marketing.zip

`bank_reference.csv` contains the 1,357-row stratified 30% test partition of
the public 4,521-row `bank.csv` dataset. The remaining 3,164 rows train a
balanced logistic regression (seed 42). `y=yes` is the positive class.

`model.json` contains numeric median imputation and standardization,
categorical one-hot encoding, logistic regression weights, and parity
examples. Unknown categories use all-zero one-hot encodings. There is no
runtime retraining and the reference rows are not used for training.

Recreate both artifacts: `python scripts/prepare_demo.py`.
Original generation environment: Python 3.12, scikit-learn 1.4.2,
pandas 2.1.4, numpy 1.26.4, scipy 1.11.4.

The front end and backend do not download any data during ordinary use.
This dataset describes bank marketing, not customer churn. The UI uses
bank marketing labels and terminology accordingly.
