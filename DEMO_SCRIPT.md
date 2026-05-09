# Demo Script (Loom walkthrough)

Target length: 3:30. Buyers watch the first 30 seconds; everything
after has to *earn* its time.

## 0:00. 0:25 · The hook

> "Most RAG demos hallucinate. Watch what this one does instead."

- Open the live demo at https://docs-rag.fly.dev.
- Click the **Apple FY2024 10-K** sample (already loaded).
- Type: *"What were Apple's total net sales in FY2024?"*
- Hit Enter. Answer renders with a `391.0 billion` claim and a
  citation badge.
- Click the citation. The right panel highlights the exact span on
  page 41.
- **Cut to:** the badge stripe. `faithfulness 92%`, `retrieval 75%`,
  `1.9s`, `$0.007`.

## 0:25. 1:00 · The unfaithful question

> "And here's what happens when I try to make it lie."

- Type: *"What's Apple's plan for launching cars in 2027?"*
- Hit Enter. Answer renders with `refused: true` styling. "I could
  not produce a fully grounded answer for this question."
- Cut to: the synthesizer code at
  [backend/docs_rag/synthesis/citation_enforcer.py](backend/docs_rag/synthesis/citation_enforcer.py)
  with the `CitationViolation` raise highlighted.

## 1:00. 1:50 · The eval gate

> "This is what continuous eval looks like."

- Switch to https://docs-rag.fly.dev/eval.
- Show the current scores: faithfulness, citation_accuracy,
  retrieval_precision, judge↔human kappa.
- Cut to the GitHub PR list, open a closed PR titled "regress
  synthesis prompt to prove gate works."
- Show the bot comment: the markdown diff with `❌ regression > 0.03`
  on faithfulness.
- Show the failing CI check that prevented merge.

## 1:50. 2:30 · Late chunking, briefly

- Open [ARCHITECTURE.md § Late Chunking](ARCHITECTURE.md#1-late-chunking-with-jina-v3).
- Read this exact line out loud:
  > "We embed the full document once, then pool per-span. Each
  > chunk's vector reflects the whole document's context up to that
  > point, that's what keeps cross-section questions accurate."
- Cut to [backend/docs_rag/providers/jina.py](backend/docs_rag/providers/jina.py)
  with `late_chunking=True` highlighted.

## 2:30. 3:10 · The boring stuff that proves it ships

- Show the README badges: CI ✅, Eval Gate ✅.
- Run `uv run pytest -q` locally, show the green dots and the
  coverage gate ≥75%.
- Run `uv run mypy --strict`, clean.
- Show the `Dockerfile`, multi-stage, non-root user, healthcheck.
- Show `.github/workflows/eval.yml`, the actual gate code.

## 3:10. 3:30 · The ask

> "If you need a RAG system that doesn't hallucinate, with citations
> your end-users can audit and an eval harness that proves it
> tomorrow as well as today, that's what I build. Same shape works
> for legal, finance, healthcare, technical docs."

- Show https://www.upwork.com/freelancers/<your-handle>.
- Cut.

## Pre-record checklist

- [ ] Live demo healthy (curl /healthz)
- [ ] All 3 sample docs ingested in the production qdrant
- [ ] Eval scorecard populated (`/evals` returns 200)
- [ ] One regression PR closed but visible in PR history
- [ ] `docs/evidence.png` updated to current bot comment style
- [ ] Loom branding turned off in Loom workspace settings
