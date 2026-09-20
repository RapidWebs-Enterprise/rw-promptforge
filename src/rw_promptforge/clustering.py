"""Failure-trace clustering via HDBSCAN over embedding space.

Groups failure traces into semantic clusters so the optimizer can treat
systemic patterns (many similar failures) differently from one-off noise.

ML-mode only — requires numpy + hdbscan from the [ml] extra.
"""

from __future__ import annotations

from enum import Enum

import numpy as np

try:
    import hdbscan  # type: ignore[import-not-found]
    _HAS_HDBSCAN = True
except ImportError:  # pragma: no cover
    hdbscan = None  # type: ignore[assignment]
    _HAS_HDBSCAN = False


class ClusterLabel(str, Enum):
    SYSTEMIC = "systemic"      # large cluster, high error rate
    RECURRING = "recurring"    # large cluster, moderate error rate
    ONE_OFF = "one_off"        # noise points or tiny clusters
    NEW_PATTERN = "new_pattern"  # small coherent cluster


class TraceClusterer:
    """Cluster failure traces by embedding similarity.

    Labels each cluster by (size, mean composite_score):
      - size >= systemic_min_size AND mean_score >= heavy_threshold → SYSTEMIC
      - size >= systemic_min_size (lower score)                   → RECURRING
      - noise points (label == -1)                              → ONE_OFF
      - everything else                                         → NEW_PATTERN
    """

    def __init__(
        self,
        min_cluster_size: int = 3,
        systemic_min_size: int = 5,
        heavy_threshold: float = 5.0,
        random_state: int = 42,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.systemic_min_size = systemic_min_size
        self.heavy_threshold = heavy_threshold
        self.random_state = random_state

    def cluster(self, embeddings: np.ndarray) -> tuple[np.ndarray, dict[int, ClusterLabel]]:
        """Cluster embedding matrix. Returns (labels, {cluster_id: ClusterLabel}).

        labels[i] is the cluster id for embedding i; -1 means noise.
        """
        n = len(embeddings)
        if n < self.min_cluster_size:
            # Too few points to cluster — everything is noise
            return np.full(n, -1, dtype=int), {}
        if not _HAS_HDBSCAN:
            raise ImportError(
                "hdbscan is required for trace clustering. "
                "Install with: pip install 'rw-promptforge[ml]'"
            )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            gen_min_span_tree=False,
        )
        labels = clusterer.fit_predict(embeddings.astype(np.float64))

        return labels, {}

    def label_clusters(
        self,
        labels: np.ndarray,
        scores: list[float],
    ) -> dict[int, ClusterLabel]:
        """Assign a semantic label to each cluster id based on size + severity."""
        out: dict[int, ClusterLabel] = {}
        unique = [c for c in set(labels.tolist()) if c != -1]
        for cid in unique:
            idx = [i for i, c in enumerate(labels) if c == cid]
            size = len(idx)
            mean_score = float(np.mean([scores[i] for i in idx])) if scores else 0.0
            if size >= self.systemic_min_size and mean_score >= self.heavy_threshold:
                out[cid] = ClusterLabel.SYSTEMIC
            elif size >= self.systemic_min_size:
                out[cid] = ClusterLabel.RECURRING
            elif size >= self.min_cluster_size:
                out[cid] = ClusterLabel.NEW_PATTERN
            else:
                out[cid] = ClusterLabel.ONE_OFF
        return out

    @staticmethod
    def label_for_trace(label: int, cluster_labels: dict[int, ClusterLabel]) -> ClusterLabel:
        """Map a raw cluster id (incl. -1 noise) to a ClusterLabel."""
        if label == -1:
            return ClusterLabel.ONE_OFF
        return cluster_labels.get(label, ClusterLabel.NEW_PATTERN)
