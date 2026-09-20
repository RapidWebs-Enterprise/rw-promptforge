---
name: Phase 3 - Failure Pattern Classification
description: HistogramGradientBoostingClassifier for predicting failure pattern types
status: proposed
created: 2026-09-14
related_spec: spec-ml-integration.md
related_adrs: [006]
---

# Plan: Phase 3 — Failure Pattern Classification

## Goal
Train HistGB classifier to predict failure pattern type (systemic/recurring/one_off/new) from trace features. Use for prioritizing optimization rounds.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/classifier.py` | CREATE | ~180 | FailureClassifier class |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +15 | Add feature columns, pattern type |
| `src/rw_promptforge/datastore/session_db.py` | MODIFY | +20 | Add training data helpers |
| `tests/test_classifier.py` | CREATE | ~70 | Unit tests |

## Step-by-Step Plan

### Step 1: Create classifier.py
```python
class FailureClassifier:
    FEATURE_COLUMNS = [
        "severity_level", "tool_call_count", "skill_conflict",
        "text_length", "embedding_cluster_id", "repetition_score",
        "time_delta_hours", "similar_trace_count"
    ]
    
    def __init__(self, model="hist_gradient_boosting"):
        self.model = HistGradientBoostingClassifier(
            max_iter=100, early_stopping=True, class_weight="balanced"
        )
        self.is_fitted = False
    
    def extract_features(self, trace: FailureTrace) -> np.ndarray:
        # Convert trace to feature vector
        pass
    
    def fit(self, traces, labels):
        X = np.array([self.extract_features(t) for t in traces])
        y = np.array(labels)
        self.model.fit(X, y)
        self.is_fitted = True
    
    def predict(self, trace) -> tuple[str, float]:
        # Returns (pattern_type, confidence)
        pass
    
    def get_feature_importance(self) -> list[tuple[str, float]]:
        # Sorted by importance
        pass
```

### Step 2: Update models.py
- Add feature column constants
- Add predicted_pattern_type to LearningLogEntry

### Step 3: Update session_db.py
- Add `get_training_data()` for bootstrap labels
- Add `persist_classifier()` for model persistence

### Step 4: Add tests
- Test feature extraction
- Test training
- Test prediction
- Test feature importance

## Test Plan
```
test_extract_features_returns_vector()
test_classifier_trains_and_predicts()
test_feature_importance_returns_sorted()
test_predict_returns_confidence()
test_bootstrap_training_from_session_db()
```

## Risks
| Risk | Mitigation |
|------|------------|
| Imbalanced classes | class_weight="balanced" |
| Need labeled data | Bootstrap from heuristics |
| Concept drift | Periodic retraining |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_classifier.py -v
```
