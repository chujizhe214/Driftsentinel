"""Reproducible public demo preparation; not a runtime backend.
Dataset: UCI Bank Marketing, CC BY 4.0, doi:10.24432/C5K306.
Reference is a held-out 30% split. Dependencies: pandas, numpy, scikit-learn.
"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import json
import urllib.request
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, recall_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'public' / 'demo'
target.mkdir(parents=True, exist_ok=True)
archive = urllib.request.urlopen('https://archive.ics.uci.edu/static/public/222/bank+marketing.zip', timeout=60).read()
outer = ZipFile(BytesIO(archive))
bank = ZipFile(BytesIO(outer.read('bank.zip')))
frame = pd.read_csv(BytesIO(bank.read('bank.csv')), sep=';')
train, reference = train_test_split(frame, test_size=.30, random_state=42, stratify=frame.y)
numeric = [c for c in frame.columns if c != 'y' and pd.api.types.is_numeric_dtype(frame[c])]
categorical = [c for c in frame.columns if c not in numeric and c != 'y']
preprocessor = ColumnTransformer([
    ('numeric', make_pipeline(SimpleImputer(strategy='median'), StandardScaler()), numeric),
    ('categorical', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical),
])
model = make_pipeline(preprocessor, LogisticRegression(class_weight='balanced', max_iter=2000, random_state=42))
model.fit(train.drop(columns='y'), train.y)
scaler = preprocessor.named_transformers_['numeric'].named_steps['standardscaler']
imputer = preprocessor.named_transformers_['numeric'].named_steps['simpleimputer']
encoder = preprocessor.named_transformers_['categorical']
classifier = model.named_steps['logisticregression']
probabilities = model.predict_proba(reference.drop(columns='y'))[:, 1]
y = (reference.y == 'yes').astype(int)
export = {
    'id': 'bank-logistic-v1', 'name': 'Bank Marketing Classifier', 'version': '1.0.0',
    'algorithm': 'Logistic Regression', 'seed': 42, 'label': 'y',
    'positiveClass': 'yes', 'negativeClass': 'no',
    'numeric': [{'name': c, 'mean': float(scaler.mean_[i]), 'scale': float(scaler.scale_[i]), 'median': float(imputer.statistics_[i])} for i, c in enumerate(numeric)],
    'categorical': [{'name': c, 'categories': list(encoder.categories_[i])} for i, c in enumerate(categorical)],
    'coefficients': classifier.coef_[0].tolist(), 'intercept': float(classifier.intercept_[0]),
    'referenceMetrics': {'f1': f1_score(y, probabilities >= .5), 'recall': recall_score(y, probabilities >= .5), 'auc': roc_auc_score(y, probabilities)},
    'trainRows': len(train), 'referenceRows': len(reference),
    'parityRows': [{'row': {k: (int(v) if isinstance(v, np.integer) else float(v) if isinstance(v, np.floating) else v) for k,v in row.items()}, 'probability': float(probabilities[i])} for i, row in enumerate(reference.drop(columns='y').head(8).to_dict('records'))]
}
reference.to_csv(target / 'bank_reference.csv', index=False)
(target / 'model.json').write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'rows': len(reference), 'metrics': export['referenceMetrics']}, indent=2))
