# Architecture

This document is for buyers/engineers evaluating the design. It walks
through the four interesting decisions in the system: late chunking,
hybrid retrieval, citation enforcement, and the eval gate.

## 1. Late chunking with Jina v3

**Problem:** Standard chunk-then-embed loses cross-chunk context. A
sentence that says "this metric" in chunk 7 has no idea what "this"
refers to once chunk 7 is embedded in isolation.

**Approach:** Send the whole document to Jina v3 with
`late_chunking=true` and `chunk_spans=[...]`. Jina runs one forward
pass over the full text, then pools token embeddings per span. Each
chunk's vector reflects the *whole* document's context up to that
point.

**Why not bge-large-en-v1.5?** bge has a 512-token window, far too
short for late chunking on real documents. We chose Jina v3 (8K
context) for true late chunking. See
[backend/docs_rag/providers/jina.py](backend/docs_rag/providers/jina.py).

**Span planner:** The chunk planner
([backend/docs_rag/ingest/chunk.py](backend/docs_rag/ingest/chunk.py))
respects paragraph boundaries with sentence-level fallback for
paragraphs >400 tokens. Adjacent chunks share ~80 tokens of overlap to
keep recall high near boundaries.

## 2. Hybrid retrieval: BM25 + dense + RRF + Cohere

```
       BM25 (sparse, scrolled across the whole collection)
                 \
                  >--->  RRF (k=60)  --->  Cohere Rerank 3.5  --->  top-8
                 /
       Dense (Qdrant cosine, top-50)
```

- **BM25** catches exact-token queries (acronyms, proper nouns, IDs)
  that dense embeddings smear out. We page the full collection via
  Qdrant's `scroll` API so BM25 sees every chunk, not just the dense
  top-K (which would defeat the purpose of hybrid retrieval).
- **Dense** catches paraphrase / semantic queries.
- **RRF** is parameter-light and well-behaved across heterogeneous
  score scales (BM25 raw vs, cosine sim).
- **Cohere Rerank 3.5** is the final precision filter. Costs <1¢ per
  call and meaningfully boosts top-1 accuracy.

The candidate pool size before rerank is `4 × rerank_top_k` to give
the reranker room to reorder while keeping per-call Cohere spend
bounded. Configurable via `RERANK_TOP_K` and `CANDIDATE_POOL_SIZE`.

## 3. Citation enforcement (the moat)

The synthesis prompt
([backend/prompts/synthesis.v1.md](backend/prompts/synthesis.v1.md))
forces Claude to emit a JSON object with a `claims` array, where each
claim has an explicit `chunk_ids: [...]`. The enforcer
([backend/docs_rag/synthesis/citation_enforcer.py](backend/docs_rag/synthesis/citation_enforcer.py))
runs three checks:

1. **JSON validity**, pydantic strict; reject on any extra field or
   schema mismatch.
2. **Citation grounding**, every `chunk_id` cited must exist in the
   retrieval context we sent.
3. **Faithfulness proxy**, token-overlap between each claim and its
   cited chunk(s); shown live in the UI.

On (2) violation, one repair attempt with a corrective prompt
([backend/prompts/repair.v1.md](backend/prompts/repair.v1.md))
including the validator error and the set of valid ids. On
second-failure we **refuse** (`refused: true`) rather than render an
unfounded answer.

This is what separates "RAG demo" from "RAG you'd ship to a customer."

## 4. Eval gate

The eval harness ([evals/run.py](evals/run.py)) executes the full
retrieve→synthesize pipeline on each of the 50 golden questions and
emits a JSON scorecard. The gate
([.github/workflows/eval.yml](.github/workflows/eval.yml)) compares
against the prior `main` scorecard via
[evals/diff.py](evals/diff.py); if `faithfulness` or
`citation_accuracy` drops by more than **3 percentage points**, the
job exits non-zero and the PR is blocked.

The first time the gate blocks a real PR, the workflow comment is
captured and committed at `docs/evidence.png` (that image is the
deliverable that shows up in proposals). Until that PR exists, the
gate logic is exercised by the unit tests in
[evals/tests/test_diff.py](evals/tests/test_diff.py).

### Why a custom `citation_accuracy` metric?

Generic faithfulness scoring only measures whether claims are grounded
in *some* chunk. We also need: did the *cited* chunk_id actually
contain the claim? That's `citation_accuracy` in
[evals/metrics/citation_accuracy.py](evals/metrics/citation_accuracy.py).
A cited chunk that doesn't contain the cited claim is worse than no
citation at all, it lies twice.

### Why an LLM-as-judge with calibration?

The judge ([evals/judge.py](evals/judge.py)) classifies each answer as
`supported | partial | unsupported`. Cohen's kappa
([evals/metrics/calibration.py](evals/metrics/calibration.py))
compares the judge's verdicts to a small set of human labels in
`evals/human_labels.jsonl`. If kappa drops below 0.6, the run is
flagged for human review, we don't trust an uncalibrated judge.

## Cost & latency budget

Per `/query`, with realistic 50-page-doc retrieval:

| Stage              | Latency p50 | Cost p50          |
|--------------------|------------:|-------------------|
| Embed query (Jina) |       80 ms | $0.00002          |
| Dense (Qdrant)     |       40 ms |.                 |
| BM25 (in-process)  |       30 ms |.                 |
| Rerank (Cohere)    |      250 ms | $0.002            |
| Synthesize (Claude)|     1500 ms | $0.005            |
| **Total**          | **~1.9 s**  | **~$0.007**       |

Repeat queries hit the Redis cache (TTL 1h) and return in ~30 ms at
$0. Cost numbers are surfaced live in the response trace.

## Trade-offs we explicitly took

- **Per-query BM25** instead of persistent: simpler, correct, fine
  for "single-doc Q&A" scope. Swap in `tantivy` when corpora grow.
- **One repair attempt** instead of N: bounded latency. The refusal
  path is safer than retrying forever.
- **Anchor-substring citation_accuracy** instead of exact chunk_id
  match: stable across chunker tuning. Maintainer pass on
  `golden_set.jsonl` is what guards against generic anchors.
- **Per-call cost tracking** in `traced(...)` instead of post-hoc
  parsing: zero risk of forgetting to record a call.

## Where to extend

- **Persistent BM25** (`tantivy`) for multi-doc corpora.
- **Streaming `/query`**. Claude's stream API is supported by the
  SDK; we'd need to validate citations against the streamed JSON
  buffer before flushing the final claim.
- **Multi-tenant document isolation**, currently a single shared
  qdrant collection; one collection per tenant + Qdrant tenants.
- **PII redaction** in ingest, recommended before any actual prod
  customer ships their data.
