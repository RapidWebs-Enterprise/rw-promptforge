---
name: Phase 2 - Failure Trace Clustering
description: HDBSCAN clustering on embedding space to identify systemic vs one-off failures
status: proposed
created: 2026-09-14
related_spec: spec-ml-integration.md
related_adrs: [005, 006]
---

# Plan: Phase 2 — Failure Trace Clustering

## Goal
Cluster failure traces using HDBSCAN on embedding space to identify systemic patterns vs noise. Return cluster labels: "systemic", "recurring", "one_off", "new_pattern".

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/clustering.py` | CREATE | ~120 | TraceClustering class |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +20 | Add TraceEmbedding, ClusterLabel |
| `src/rw_promptforge/datastore/session_db.py` | MODIFY | +30 | Add cluster-aware query methods |
| `tests/test_clustering.py` | CREATE | ~60 | Unit tests |

## Step-by-Step Plan

### Step 1: Create clustering.py
```python
class TraceClustering:
    def __init__(self, embedding_provider, min_cluster_size=3):
        self.embedder = embedding_provider
        self.min_cluster_size = min_cluster_size
    
    def cluster(self, traces: list[FailureTrace]) -> dict[int, list[FailureTrace]]:
        # 1. Embed all traces
        # 2. Run HDBSCAN
        # 3. Label clusters by error rate
        # 4. Return {cluster_id: [traces]}
        pass
    
    def get_cluster_label(self, cluster_id: int, traces: list[FailureTrace]) -> str:
        # Label based on: error_rate, size, pattern_diversity
        pass
```

### Step 2: Update models.py
- Add `TraceEmbedding` dataclass
- Add `ClusterLabel` enum (SYSTEMIC, RECURRING, ONE_OFF, NEW_PATTERN)

### Step 3: Update session_db.py
- Add `get_traces_with_clusters()` method
- Store cluster metadata in LearningLogEntry

### Step 4: Add tests
- Test empty traces
- Test single trace
- Test clustered traces
- Test label assignment

## Test Plan
```
test_cluster_empty_traces()
test_cluster_single_trace()
test_cluster_identifies_systemic_patterns()
test_cluster_labels_assigned_correctly()
test_get_cluster_label_heavy_vs_light()
```

## Risks
| Risk | Mitigation |
|------|------------|
| HDBSCAN parameter sensitivity | Sensible defaults, document tuning |
| Small cluster count | min_cluster_size=3 configurable |
| Memory for large trace sets | Lazy embedding, batch processing |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_clustering.py -v
```
