"""Failure pattern classification via HistGradientBoosting.

Predicts ClusterLabel (systemic/recurring/one_off/new_pattern) from cheap
trace features so the optimizer can prioritize systemic failures without
running clustering on every round. Model persists to ~/.cache/rw-promptforge/.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from rw_promptforge.cache import CACHE_DIR
from rw_promptforge.clustering import ClusterLabel

MODEL_PATH = CACHE_DIR / "classifier.pkl"

# Feature vector layout — keep stable across retrains for compat.
FEATURES = [
    "severity",
    "text_length",
    "has_correction",
    "has_response",
    "has_context",
    "skill_known",
    "failure_type_general",
]

LABELS = [
    ClusterLabel.ONE_OFF,
    ClusterLabel.NEW_PATTERN,
    ClusterLabel.RECURRING,
    ClusterLabel.SYSTEMIC,
]


class FailureClassifier:
    """HistGB classifier over FailureTrace features.

    Label space is ClusterLabel; string form used for persistence so model
    files stay stable if the enum gains members.
    """

    def __init__(self) -> None:
        self.model = HistGradientBoostingClassifier(
            max_iter=200,
            early_stopping=False,
            min_samples_leaf=2,  # failure-trace datasets are small; default 20 starves splits
            random_state=42,
        )
        self.is_fitted = False
        self.trained_at: float | None = None

    @staticmethod
    def features(trace) -> list[float]:
        """Extract numeric features from a FailureTrace-like object."""
        text = getattr(trace, "what_happened", "") or ""
        return [
            float(getattr(trace, "severity", 0) or 0),
            float(len(text)),
            1.0 if getattr(trace, "user_correction", "") else 0.0,
            1.0 if getattr(trace, "agent_response", "") else 0.0,
            1.0 if getattr(trace, "context", "") else 0.0,
            1.0 if getattr(trace, "skill_name", "") else 0.0,
            1.0 if getattr(trace, "failure_type", "") == "general" else 0.0,
        ]

    def fit(self, traces, labels: list[ClusterLabel]) -> None:
        X = np.array([self.features(t) for t in traces], dtype=np.float64)
        y = np.array([label.value for label in labels])
        self.model.fit(X, y)
        self.is_fitted = True
        self.trained_at = time.time()

    def predict(self, trace) -> tuple[ClusterLabel, float]:
        """Return (label, confidence). Confidence = max class probability."""
        if not self.is_fitted:
            return ClusterLabel.NEW_PATTERN, 0.0
        X = np.array([self.features(trace)], dtype=np.float64)
        proba = self.model.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        classes = list(self.model.classes_)
        return ClusterLabel(classes[idx]), float(proba[idx])

    def save(self, path: Path | str | None = None) -> None:
        import joblib

        p = Path(path) if path is not None else MODEL_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "is_fitted": self.is_fitted,
                "trained_at": self.trained_at,
                "features": FEATURES,
            },
            p,
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "FailureClassifier":
        import joblib

        obj = cls()
        p = path or MODEL_PATH
        payload = joblib.load(p)
        obj.model = payload["model"]
        obj.is_fitted = payload["is_fitted"]
        obj.trained_at = payload.get("trained_at")
        return obj
