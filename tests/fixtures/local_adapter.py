"""Small trusted adapter for exercising the local model UI and output contract."""
import numpy as np


def predict_proba(X):
    values = np.asarray(X['duration'].fillna(0), dtype=float)
    positive = 1 / (1 + np.exp(-np.clip((values - 300) / 150, -100, 100)))
    return np.column_stack([1 - positive, positive])


def predict(X):
    return np.where(predict_proba(X)[:, 1] >= .5, 'yes', 'no')
