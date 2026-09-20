# ADR-010: Embedding Model Selection

**Date:** 2026-09-14  
**Status:** Accepted  
**Context:** Need to choose embedding model for ML enhancement features

## Decision

Use `bge-small-en-v1.5` served by RW_InferenceEngine as the default embedding model, with OpenAI-compatible endpoint as configurable fallback.

## Rationale

1. **Zero marginal cost:** Already deployed at `http://srv1:8300/v1/embeddings`, no additional API bills
2. **Sufficient performance:** 384-dim BGE model achieves ~71% MTEB score, competitive with nomic-embed-text
3. **Local inference:** Runs on existing RW_InferenceEngine container, no network dependency beyond Tailscale
4. **Configurable:** CLI flags allow override for users who want different models/endpoints
5. **Fast:** ONNX runtime provides sub-10ms latency per batch

## Alternatives Considered

| Model | Dimensions | Context | MTEB Score | Cost | Latency |
|-------|------------|---------|------------|------|---------|
| bge-small-en-v1.5 | 384 | 512 | 71.0% | Free | ~5ms/batch |
| nomic-embed-text-v1.5 | 768 | 8192 | 71.5% | Free (local) | ~15ms/batch |
| text-embedding-3-small | 1536 | 8192 | 75.8% | $0.02/1M tokens | ~10ms/batch |
| text-embedding-3-large | 3072 | 8192 | 80.5% | $0.13/1M tokens | ~20ms/batch |

**Rejected alternatives:**
- **nomic-embed-text:** Better context length but larger model, not currently deployed
- **OpenAI models:** API costs scale with usage, not necessary for failure trace analysis

## Consequences

- **Positive:** No new infrastructure required
- **Positive:** Easy to upgrade later by swapping model path in RW_InferenceEngine
- **Negative:** Limited to 512-token context (sufficient for failure traces)
- **Negative:** Requires RW_InferenceEngine running (check health endpoint)

## Configuration

```bash
# Default (uses RW_InferenceEngine)
rw-promptforge optimize --ml-mode

# Override endpoint
rw-promptforge optimize --ml-mode --embedding-endpoint http://custom:8300

# Override model name
rw-promptforge optimize --ml-mode --embedding-model nomic-embed-text-v1.5
```

## References

- [RW_InferenceEngine docs](../RW_InferenceEngine/README.md)
- [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [MTEB benchmark results](https://huggingface.co/spaces/mteb/leaderboard)
