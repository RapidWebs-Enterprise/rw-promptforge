---
name: ml-embedding-integration
description: Add OpenAI-compatible embedding and reranking support via rw_inferenceEngine
status: proposed
created: 2026-09-14
author: lucien@rapidwebs
related-adrs: [adr-005-embedding-integration, adr-006-failure-classification, adr-007-cross-encoder-reranking]
---

# Spec: ML-Enhanced Prompt Optimization

## Context

rw-promptforge currently uses token-level similarity metrics (Jaccard, SequenceMatcher)
for convergence detection, stagnation checks, and failure trace comparison. This creates
blind spots:

- **Paraphrased stagnation**: Two versions saying the same thing differently score as
  "different" even when semantically identical
- **Missed semantic drift**: Subtle rewordings that preserve meaning but shift intent
  go undetected
- **Flat failure analysis**: All traces treated equally regardless of systemic vs. one-off
  nature

Research into prompt optimization literature (CASPER, C-MOP, ETGPO) confirms that
embedding-based semantic analysis is the foundation for advanced optimization patterns:
- Cluster-aware sampling (C-MOP)
- Error taxonomy generation (ETGPO)
- Feedback-guided gradient descent (CASPER)

## Requirements

### R1: Embedding Provider

The system SHALL provide an OpenAI-compatible embedding interface that can be configured
to point at any deployment (local sentence-transformers, rw_inferenceEngine, or external
APIs).

#### Scenario: Local fallback
- **GIVEN** rw_inferenceEngine is unavailable
- **WHEN** embedding is requested
- **THEN** system falls back to local sentence-transformers model (all-MiniLM-L6-v2)

#### Scenario: Primary endpoint
- **GIVEN** `RW_PROMPTFORGE_EMBEDDING_ENDPOINT` is set to http://srv1:8300/v1
- **WHEN** embeddings are requested
- **THEN** system calls OpenAI-compatible `/embeddings` endpoint

### R2: Semantic Similarity Interface

The system SHALL provide semantic similarity functions that replace or augment
token-level metrics in convergence detection and stagnation checks.

#### Scenario: Convergence with embeddings
- **GIVEN** two artifact versions that are paraphrases of each other
- **WHEN** `semantic_similarity()` is called
- **THEN** returns cosine similarity in [0.0, 1.0] (higher = more similar)

#### Scenario: Stagnation detection
- **GIVEN** recent optimization history with 3+ entries
- **WHEN** `is_stagnant()` is called
- **THEN** uses embedding similarity to detect semantic repetition

### R3: Failure Trace Clustering

The system SHALL cluster failure traces using HDBSCAN on embedding space to identify
systemic vs. one-off failures.

#### Scenario: Cluster systemic failures
- **GIVEN** 50 failure traces from session_db
- **WHEN** `cluster_traces()` is called
- **THEN** returns clusters with labels: "systemic", "recurring", "one_off", "new_pattern"

#### Scenario: Prioritize optimization
- **GIVEN** clustered failure traces
- **WHEN** `select_trace_batch()` is called
- **THEN** returns traces weighted toward systemic patterns

### R4: Gradient Boosting Failure Classifier

The system SHALL train a HistogramGradientBoostingClassifier to predict failure
pattern types from trace features.

#### Scenario: Classify new trace
- **GIVEN** labeled training data (trace → pattern_type)
- **WHEN** `predict_pattern(trace)` is called
- **THEN** returns (pattern_type, confidence) tuple

#### Scenario: Feature importance
- **GIVEN** trained classifier
- **WHEN** `get_feature_importance()` is called
- **THEN** returns sorted list of (feature_name, importance_score)

### R5: Cross-Encoder Reranking

The system SHALL use a CrossEncoder to rerank retrieved failure traces by relevance
to the current optimization query.

#### Scenario: Two-stage retrieval
- **GIVEN** 100 candidate traces, query = "protocol violation detection"
- **WHEN** `rerank_traces(query, traces, top_k=5)` is called
- **THEN** returns top-5 traces ranked by cross-encoder score

### R6: Optional Dependencies

ML dependencies SHALL be optional extras, not required for core functionality.

#### Scenario: Install with ML support
- **GIVEN** user runs `pip install rw-promptforge[ml]`
- **WHEN** package is installed
- **THEN** numpy, scikit-learn, httpx are available; sentence-transformers is optional

#### Scenario: Core without ML
- **GIVEN** user runs `pip install rw-promptforge`
- **WHEN** package is installed
- **THEN** Jaccard/SequenceMatcher fallback is used automatically

## Design Notes

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Optimizer (existing)                  │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Auditor   │  │ Reflector   │  │ Convergence      │  │
│  │ (Jaccard) │  │ (LLM call)  │  │ (Multi-signal)   │  │
│  └────┬──────┘  └──────┬──────┘  └────────┬─────────┘  │
│       │                │                  │             │
│       └────────────────┴──────────────────┘             │
│                        ↓                                │
│              ┌─────────────────────┐                    │
│              │  EmbeddingProvider   │                    │
│              │  (OpenAI-compatible) │                    │
│              └──────────┬──────────┘                    │
│                         │                               │
│        ┌────────────────┼────────────────┐              │
│        ↓                ↓                ↓              │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────┐    │
│  │ rw_ie     │  │ local ST    │  │ external API │    │
│  │ (primary) │  │ (fallback)  │  │ (optional)   │    │
│  └───────────┘  └─────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│              ML Analysis Layer (new)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │TraceCluster │  │FailureClassif  │  │CrossEncoderR │  │
│  │(HDBSCAN)    │  │(HistGBClassifier)│ │ (reranker)  │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Model

```python
@dataclass
class TraceEmbedding:
    trace_id: str
    embedding: list[float]  # n-dim vector
    cluster_id: int | None  # assigned by HDBSCAN
    pattern_type: str | None  # systemic / one_off / recurring / new

@dataclass
class RerankedTrace:
    original_index: int
    relevance_score: float  # cross-encoder output
    is_relevant: bool  # thresholded

FEATURE_COLUMNS = [
    "severity_level",      # numeric: 1-3
    "tool_call_count",     # int
    "skill_conflict",      # bool → 0/1
    "text_length",         # int
    "embedding_cluster_id",# int (from clustering)
    "repetition_score",    # float [0,1]
    "time_delta_hours",    # float
    "similar_trace_count", # int
]
```

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| rw_inferenceEngine unavailable | Medium | High | Local sentence-transformers fallback |
| Embedding dimension mismatch | Low | Medium | Configurable dimension detection |
| HDBSCAN parameter sensitivity | Medium | Low | Sensible defaults, grid search optional |
| Cross-encoder memory overhead | Medium | Low | Batch processing, configurable batch_size |
| Gradient boosting overfitting | Low | Medium | Early stopping, cross-validation built-in |

## Implementation Phases

| Phase | Feature | Effort | Blocker |
|-------|---------|--------|---------|
| 1 | EmbeddingProvider + semantic similarity | 150 LOC | None |
| 2 | Trace clustering (HDBSCAN) | 100 LOC | Phase 1 |
| 3 | Failure classifier (HistGB) | 150 LOC | Phase 1 |
| 4 | Cross-encoder reranker | 100 LOC | Phase 1 |
| 5 | Integration with optimizer loop | 100 LOC | Phases 1-4 |

## Open Questions

- What embedding model should rw_inferenceEngine serve? (nomic-embed-text, all-MiniLM?)
- Should we persist embeddings to avoid recomputation?
- What's the optimal HDBSCAN min_cluster_size for our trace volume?
- How do we handle concept drift in failure patterns over time?

## References

- CASPER: Bridging Discrete and Continuous Prompt Optimization (ACL 2026)
- C-MOP: Cluster-based Momentum Optimized Prompting (arXiv 2025)
- ETGPO: Error Taxonomy-Guided Prompt Optimization (alphaXiv 2025)
- faultmap: Diagnostic layer for LLM failures (GitHub)
- Scikit-learn HGBT docs: https://scikit-learn.org/stable/modules/ensemble.html#histogram-based-gradient-boosting
