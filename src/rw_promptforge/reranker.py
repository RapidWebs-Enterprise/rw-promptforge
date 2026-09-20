"""Two-stage failure-trace reranking: embedding recall then cross-encoder refine.

Stage 1 (recall): embed query + traces via Provider.embed(), pick top recall_k
by cosine similarity. Cheap, effective at high-recall candidate selection.

Stage 2 (precision): Provider.rerank() scores each candidate pair exactly,
returning top_k by score. Expensive per-call so kept to a small candidate set.

Both endpoints are served by RW_InferenceEngine — see ADR-012.
If either stage fails (network/HTTP), falls back to returning the first
`top_k` traces unchanged (no exception escaping to the optimizer).
"""

from __future__ import annotations

import httpx
import numpy as np

from rw_promptforge.datastore.models import semantic_similarity


class TraceReranker:
    def __init__(self, provider, top_k: int = 5, recall_k: int = 20) -> None:
        self.provider = provider
        self.top_k = top_k
        self.recall_k = recall_k

    def rerank(self, query: str, traces: list) -> list:
        """Return traces ordered by relevance. Falls back to input order on error."""
        if not traces:
            return []
        if len(traces) <= self.top_k:
            return list(traces)

        candidates = self._recall(query, traces)
        return self._refine(query, candidates)

    # ------------------------------------------------------------------

    def _recall(self, query: str, traces: list) -> list:
        try:
            texts = [self._trace_text(t) for t in traces]
            vecs = self.provider.embed([query, *texts])
            q, doc_vecs = vecs[0], vecs[1:]
            sims = [semantic_similarity(q, v) for v in doc_vecs]
            order = np.argsort(np.array(sims))[::-1][: self.recall_k]
            return [traces[i] for i in order]
        except (httpx.HTTPError, ValueError, KeyError):
            # Embedding failure → no recall filtering; rerank the full head.
            return list(traces[: self.recall_k])

    def _refine(self, query: str, candidates: list) -> list:
        try:
            docs = [self._trace_text(c) for c in candidates]
            scores = self.provider.rerank(query, docs)
            order = np.argsort(np.array(scores))[::-1][: self.top_k]
            return [candidates[i] for i in order]
        except (httpx.HTTPError, ValueError, KeyError):
            return candidates[: self.top_k]

    @staticmethod
    def _trace_text(trace) -> str:
        """Concatenate the salient text fields of a FailureTrace."""
        parts = [
            getattr(trace, "what_happened", "") or "",
            getattr(trace, "user_correction", "") or "",
        ]
        return "\n".join(p for p in parts if p)
