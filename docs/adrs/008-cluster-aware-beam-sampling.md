# ADR-008: Cluster-Aware Beam Sampling for Optimization

**Date:** 2026-09-14  
**Status:** Proposed

## Context

rw-promptforge's optimizer uses a "beam" of N candidate variants per round, each with
a different emphasis hint (structural coherence, failure coverage, conciseness, etc.).
Currently, beam candidates are generated independently and ranked by composite score.

Research (C-MOP, UNIPROMPT) shows that **cluster-aware sampling** improves optimization:
- Group similar failures together
- Sample proportionally to cluster error rate
- Ensure diverse coverage across failure modes

## Decision

**Extend optimizer beam to use cluster-aware sampling from failure trace groups.**

Implementation:
- Use HDBSCAN clusters from ADR-006 (FailureClassifier)
- Allocate beam slots proportional to cluster error rate
- Each beam candidate focuses on a different cluster
- Aggregate feedback across clusters

## Rationale

### Why cluster-aware vs. uniform random?

Uniform random sampling wastes beam capacity on:
- Low-error clusters (already well-handled)
- One-off noise (not representative)

Cluster-aware sampling concentrates on:
- High-error clusters (systemic issues)
- Diverse failure modes (better generalization)

From C-MOP research:
> "Cluster-aware quota allocation: We apply K-means clustering to partition the batch 
> into K clusters and allocate a sampling quota proportional to the error rate."

### Why not exhaustive search?

- Too many combinations (factorial in cluster count)
- C-MOP shows cluster-based search reduces complexity from O(N!) to O(N)
- Maintains comparable performance with 92-100% time savings

## Consequences

### Positive
- More efficient beam utilization
- Better coverage of diverse failure modes
- Reduces overfitting to common patterns
- Aligns with research best practices

### Negative
- Added complexity in beam construction
- Requires cluster labels from ADR-005/006
- May need tuning of allocation strategy

### Trade-offs
- **Simple**: Proportional to cluster size
- **Complex**: Proportional to error rate × cluster importance
- Start with simple, iterate based on results

## Implementation

```python
# src/rw_promptforge/optimizer.py (extended)
BEAM_HINTS = (
    "structural coherence and section ordering",
    "failure coverage and behavioral specificity",
    "conciseness and redundancy removal",
    "actionability and executable instructions",
)

class Optimizer:
    def __init__(self, ...):
        self.cluster_sampler = ClusterAwareSampler()
    
    def generate_beam_candidates(self, traces, num_beams=4):
        # 1. Cluster traces (if not already clustered)
        clusters = self.cluster_sampler.get_clusters(traces)
        
        # 2. Allocate beam slots proportional to cluster error rate
        allocations = self.cluster_sampler.allocate_slots(
            clusters, num_beams=num_beams
        )
        
        # 3. For each allocated cluster, select representative traces
        # 4. Generate beam candidate with cluster-specific hint
        candidates = []
        for cluster, count in allocations.items():
            cluster_traces = self.cluster_sampler.sample(cluster, k=count)
            hint = self._get_hint_for_cluster(cluster)
            candidates.append(self.reflector.generate(hint, cluster_traces))
        
        return candidates
```

## Related

- ADR-005: Embedding Integration (required for clustering)
- ADR-006: Failure Classification (provides cluster labels)
- Spec: spec-ml-integration.md, Section R6
- C-MOP paper: https://arxiv.org/abs/2602.10874
