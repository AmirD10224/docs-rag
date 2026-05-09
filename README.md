# docs-rag

[![CI](https://github.com/AmirD10224/docs-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/AmirD10224/docs-rag/actions/workflows/ci.yml)
[![Eval Gate](https://github.com/AmirD10224/docs-rag/actions/workflows/eval.yml/badge.svg)](https://github.com/AmirD10224/docs-rag/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](./pyproject.toml)

RAG over a PDF or a URL. You upload a document, ask a question, and get a Markdown answer where every claim has to cite a `chunk_id` that we actually sent to the model. The right panel renders the source span when you click the citation. There's also a `/eval` page with the latest scores against a 50-question golden set, and the GitHub Actions eval gate blocks merges if faithfulness or citation accuracy regresses by more than 3 points.

## What it does

You upload a PDF or paste a URL. Ask a question. The pipeline:

1. Parses the document with pdfplumber + unstructured.
2. Chunks it with late-chunking spans (Jina v3, 8K context, embeddings are computed on the full doc, then pooled per span, so a chunk in section 7 still carries context from sections 1–6).
3. Indexes into Qdrant.
4. At query time, runs dense (Qdrant cosine) + BM25 sparse over the corpus, fuses with RRF, then reranks with Cohere Rerank 3.5.
5. Sends the top chunks plus a strict JSON schema to Sonnet 4.6.
6. Validates the output: every `chunk_ids` value in `claims[]` must match a chunk we actually retrieved. If not, one repair retry. If that still fails, the response is `refused: true` rather than an unfounded answer.

The "refuse rather than fabricate" path is exercised end-to-end in [`backend/tests/unit/test_synthesizer.py`](backend/tests/unit/test_synthesizer.py) (the "always-bad provider" test).

## Architecture

```mermaid
flowchart LR
    U([User]) -->|PDF / URL| I[/ingest]
    U -->|Question| Q[/query]
    U -->|chunk_id| C[/citation/:id]

    I --> P[Parse pdfplumber + unstructured]
    P --> CH[Chunk planner late spans]
    CH --> EMB[Jina v3 late embed]
    EMB --> QD[(Qdrant)]

    Q --> EQ[Embed query]
    EQ --> DENSE[Qdrant dense search]
    Q --> BM[BM25 sparse - corpus-wide scroll]
    DENSE --> RRF[RRF fusion]
    BM --> RRF
    RRF --> RR[Cohere Rerank 3.5]
    RR --> SYN[Claude Sonnet 4.6 strict JSON]
    SYN --> CE[Citation enforcer + repair]
    CE --> RES[QueryResponse + faithfulness]

    C --> QD

    EV[evals/run.py] -->|live providers| Q
    EV --> RPT[(reports/*.json)]
    GH[GH Actions eval gate] --> EV
    GH -->|diff vs main| PR[PR comment]
    GH -->|>3pt regression| BLK[Block merge]
```

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Synthesis | Claude Sonnet 4.6 | Strict JSON via Anthropic tool-use. |
| Reranker | Cohere Rerank 3.5 | |
| Embeddings | Jina Embeddings v3 | 8K context, used for late chunking. |
| Sparse retrieval | BM25 via `rank_bm25` | Per-query, full-corpus scroll from Qdrant. |
| Vector store | Qdrant Cloud | Free tier is enough for the demo corpus. |
| API | FastAPI + Pydantic v2 strict + slowapi | Per-IP rate limits. |
| Cache | Redis with 1h TTL on `/query` | Key normalises whitespace + case. Cuts demo cost. |
| Frontend | Next.js 15 + Tailwind v4 | App Router. |
| Deploy | Fly.io (backend) + Vercel (frontend) | Both free tier. |
| Eval | Custom faithfulness + LLM-judge calibration | Cohen's kappa vs human labels. |
| Quality | mypy strict, ruff, pytest ≥75% coverage | |

## Quickstart

```bash
# 1. Python deps
uv sync --all-extras

# 2. Offline demo (mock providers, no API keys)
MOCK_PROVIDERS=true uv run uvicorn docs_rag.main:app --reload

# 3. Frontend
cd frontend && npm install && npm run dev

# 4. With real providers
cp .env.example .env
# fill in ANTHROPIC_API_KEY, COHERE_API_KEY, JINA_API_KEY, QDRANT_*
docker compose up

# 5. Evals (mock)
PYTHONPATH=backend:, uv run python evals/run.py

# 6. Evals (live, spends credits)
PYTHONPATH=backend:, uv run python evals/run.py --live
```

## Citation enforcement

The synthesis prompt forces the model to emit a list of `claims`, each with the `chunk_ids` it's drawing from. The enforcer ([`backend/docs_rag/synthesis/citation_enforcer.py`](backend/docs_rag/synthesis/citation_enforcer.py)) checks every id against the chunks we actually retrieved. If any are wrong:

- We send one repair prompt that includes the validation error and the set of valid ids.
- If the repair still fails, we return `refused: true` and don't render the answer.

There is no third try, and no fallback that quietly drops the citation requirement. That's the whole point.

## Evals

50 hand-verified questions across three sample docs (Apple FY2024 10-K, GitLab MSA, "Attention Is All You Need"). Pull them with `make fetch-samples`.

Metrics:

- `faithfulness`, fraction of claims whose tokens overlap ≥40% with their cited chunks. Combined with the LLM-judge for live runs.
- `citation_accuracy`, fraction of claims whose `chunk_ids` were actually retrieved.
- `retrieval_precision`, fraction of retrieved chunks that contain a relevant anchor string.
- `judge_human_kappa`. Cohen's kappa between the LLM-judge and human labels. Currently calibrated on n=7, expanding to n≥30.

The PR gate is in [`.github/workflows/eval.yml`](.github/workflows/eval.yml). It posts the diff vs `main` as a comment and exits non-zero if any of the above regresses by more than 3 points.

## Security

- `/query`, `/ingest`, `/citation/{id}` are rate-limited (slowapi, per-IP, configurable).
- `/ingest` URL handler rejects RFC1918, link-local, loopback, and cloud-metadata IPs.
- File uploads stream-checked against `MAX_PDF_MB` before full buffering.
- Anthropic, Qdrant, Redis, and HTTP fetches all have explicit timeouts.
- Daily Anthropic spend cap trips a circuit breaker.

Threat model and full notes in [ARCHITECTURE.md](ARCHITECTURE.md).

## Layout

```
docs-rag/
├── backend/docs_rag/   FastAPI app, ingest, retrieval, synthesis
├── backend/prompts/    versioned synthesis + repair prompts
├── backend/tests/      unit + integration (respx-based)
├── frontend/           Next.js 15 demo + /eval scorecard
├── evals/              golden_set.jsonl, run.py, judge.py, diff.py
├── data/samples/       three pre-loaded sample documents
├── .github/workflows/  ci · eval-gate · deploy
└── docs/               architecture + eval evidence
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the retrieval design notes and the cost/latency budget.

## License

MIT. [LICENSE](LICENSE).
