# Eval Suite

This directory holds DocsRAG's reproducible evaluation harness. The
harness is what differentiates a portfolio toy from a production RAG
system: it produces a numeric scorecard that the GitHub Actions gate
uses to **block merges** on regression.

## Files

| File                            | Purpose                                                                              |
|---------------------------------|--------------------------------------------------------------------------------------|
| `golden_set.jsonl`              | 50 hand-verified questions across the 3 sample docs.                                 |
| `run.py`                        | Runs the system against the golden set and emits `reports/<run_id>.json`.            |
| `judge.py`                      | LLM-as-judge for faithfulness and answer relevancy, calibrated against human labels. |
| `metrics/citation_accuracy.py`  | Custom metric: do the cited chunks actually contain the cited claim?                 |
| `metrics/calibration.py`        | Computes judge↔human agreement (Cohen's κ) so we know the judge is trustworthy.      |
| `human_labels.jsonl`            | Sample of golden_set rows where a human labelled answer + faithfulness.              |
| `reports/`                      | Per-run JSON scorecards, one per CI run. Used by `GET /evals`.                       |

## Schema. `golden_set.jsonl`

Each line:

```json
{
  "id": "q-001",
  "document": "apple_10k_fy2024.pdf",
  "question": "What was Apple's total net sales for FY2024?",
  "expected_answer": "Total net sales were $391.0 billion in FY2024.",
  "relevant_anchors": ["391.0", "net sales"],
  "faithfulness_label": "supported",
  "difficulty": "easy"
}
```

- `relevant_anchors` are case-insensitive substrings; **at least one must
  appear in at least one cited chunk** for the answer to count as
  citation-accurate. This avoids brittle chunk-id comparisons that
  break when the chunker is tuned.
- `faithfulness_label` ∈ {`supported`, `partial`, `unsupported`}, the
  human ground truth. The LLM judge's classification is compared
  against this set in `metrics/calibration.py`.
- `difficulty` ∈ {`easy`, `medium`, `hard`}, used to slice the
  scorecard. We expect lower scores on `hard` and that's fine; we
  block merges only on the **aggregate**.

## Methodology

The 50-question set was authored hybrid (per Q5 of the project spec):
Claude proposed candidates against each document; each was reviewed
and edited by the maintainer to ensure (a) the expected answer is
factually present in the document, (b) the relevant anchors are
discriminative (not common boilerplate), and (c) difficulty is honest.

Re-running the maintainer pass takes ~30 minutes per 50 questions and
should be repeated whenever the sample-document set changes.

## Running locally

```bash
uv run python evals/run.py            # mocks; just exercises the harness
APP_ENV=staging \
  ANTHROPIC_API_KEY=... COHERE_API_KEY=... JINA_API_KEY=... \
  QDRANT_URL=... QDRANT_API_KEY=... \
  uv run python evals/run.py --live   # real providers
```

The CI gate (`.github/workflows/eval.yml`) runs `--live` and posts the
scorecard diff as a PR comment. Merge is blocked if `faithfulness` or
`citation_accuracy` regress by **more than 3 points**.
