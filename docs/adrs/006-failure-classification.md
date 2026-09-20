# ADR-006: Failure Pattern Classification via Gradient Boosting

**Date:** 2026-09-14  
**Status:** Proposed

## Context

rw-promptforge collects failure traces from Hermes session history. Currently, all traces
are treated equally when constructing optimization feedback. However, failure patterns
vary in severity and recurrence:

- **Systemic**: Agent repeatedly violates same protocol despite fixes
- **Recurring**: Pattern appears in multiple sessions but not constant
- **One-off**: Single incident, likely noise
- **New pattern**: Novel failure mode requiring investigation

Without classification, optimization rounds may focus on one-off incidents or miss
systemic issues that need architectural changes.

## Decision

**Use HistogramGradientBoostingClassifier for failure pattern prediction.**

Features:
- `severity_level`: Trace severity (1-3)
- `tool_call_count`: Number of tool interactions
- `skill_conflict`: Boolean — does trace contradict loaded skill?
- `text_length`: Trace description length
- `embedding_cluster_id`: From HDBSCAN clustering (ADR-005)
- `repetition_score`: Similarity to recent traces
- `time_delta_hours`: Hours since last similar failure
- `similar_trace_count`: Cluster membership size

## Rationale

### Why Histogram Gradient Boosting over Random Forest?

Scikit-learn documentation and benchmarking studies show HGBT uniformly dominates RF on
the test-score vs training speed tradeoff:

1. **Histogram binning**: Bins feature values into ~256 bins, enabling faster splits
2. **Early stopping**: Built-in validation-based stopping prevents overfitting
3. **Memory efficient**: Histogram storage vs. node storage in RF
4. **Feature importance**: Native `feature_importances_` attribute

From scikit-learn docs:
> "One should often observe that the Histogram-based gradient boosting models uniformly 
> dominate the Random Forest models in the 'test score vs training speed trade-off'."

### Why not LightGBM/XGBoost?

- Adds external dependency (lightgbm, xgboost)
- HGBT is in scikit-learn (already a dev dependency)
- Performance difference is marginal for our use case (~82% vs ~80% on benchmark)
- HGBT has early-stopping built-in; LightGBM requires extra config

### Why not neural networks?

- Overkill for structured tabular data
- More complex to tune
- No early stopping without callbacks
- Harder to interpret feature importance

## Consequences

### Positive
- Learns which traces are worth prioritizing
- Feature importance reveals what signals matter most
- Fast inference after training
- Handles imbalanced classes via class_weight

### Negative
- Requires labeled training data (can bootstrap from heuristics)
- Retraining needed as failure patterns evolve
- Added complexity in ML pipeline

## Implementation

```python
# src/rw_promptforge/patterns.py
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
import numpy as np

class FailureClassifier:
    FEATURE_COLUMNS = [...]  # See spec
    
    def __init__(self, max_iter=100, early_stopping=True):
        self clf = HistGradientBoostingClassifier(
            max_iter=max_iter,
            early_stopping=early_stopping,
            class_weight="balanced",
            random_state=42,
        )
        self.label_encoder = LabelEncoder()
        self.is_fitted = False
    
    def extract_features(self, trace: FailureTrace) -> np.ndarray:
        # Convert trace to feature vector
        
    def fit(self, traces: list[FailureTrace], labels: list[str]):
        X = np.array([self.extract_features(t) for t in traces])
        y = self.label_encoder.fit_transform(labels)
        self.clf.fit(X, y)
        self.is_fitted = True
    
    def predict(self, trace: FailureTrace) -> tuple[str, float]:
        # Returns (pattern_type, confidence)
    
    def get_feature_importance(self) -> list[tuple[str, float]]:
        # Sorted by importance
```

## Related

- ADR-005: Embedding Integration (required for feature extraction)
- Spec: spec-ml-integration.md, Section R4
