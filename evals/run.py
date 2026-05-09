"""Eval runner.

Reads `golden_set.jsonl`, runs each question through the actual
DocsRAG container, and emits a JSON scorecard with:

  - `faithfulness`         (LLM-as-judge: ratio of "supported" verdicts)
  - `citation_accuracy`    (custom: do citations actually contain the
                             expected anchor strings?, see
                             evals/metrics/citation_accuracy.py)
  - `retrieval_precision`  (mean Cohere rerank score ≥ 0.5)
  - `judge_human_kappa`    (Cohen's kappa between the LLM-judge and
                             human labels in human_labels.jsonl)

Outputs `reports/<run_id>.json` plus a `reports/latest.json` pointer
(committed on `main` so the eval gate has a baseline to diff against).

Modes:
  - default: MOCK_PROVIDERS=true (cheap, exercises the harness only)
  - --live:  forces MOCK_PROVIDERS=false (real Anthropic/Cohere/Jina spend)

Cost tracking:
  Each run wraps the per-question execution in a `request_scope()` so the
  per-call cost recorded by `traced(...)` rolls up to the request total;
  we then sum across rows. The previous version stubbed this out at
  `0.0`, which made the cost dashboard a lie.

CI runs `--live` (gated to maintainer-approved PRs only). The eval gate
compares against `reports/latest.json` and fails on >3-point regression
on `faithfulness` or `citation_accuracy`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evals" / "reports"
GOLDEN = ROOT / "evals" / "golden_set.jsonl"
HUMAN_LABELS = ROOT / "evals" / "human_labels.jsonl"

# Bound concurrent in-flight calls to keep below provider rate limits.
# (Anthropic Tier-1 is ~50 RPM; we stay well under that.)
CONCURRENCY = 8


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


async def _run_one(container: Any, row: dict[str, Any], sem: asyncio.Semaphore) -> dict[str, Any]:
    """Execute one golden-set question end-to-end and capture results.

    Wraps the call in `request_scope()` so we get a per-row cost figure
    (sum of every traced() call inside retrieval + synthesis).
    """
    from docs_rag.observability.tracing import current_trace, request_scope

    async with sem:
        started = time.perf_counter()
        with request_scope() as _trace:
            retrieval = await container.retriever.retrieve(row["question"], document_ids=None)
            response = await container.synthesizer.answer(
                question=row["question"],
                ranked_chunks=retrieval.chunks,
                retrieval_ms=retrieval.retrieval_ms,
                rerank_ms=retrieval.rerank_ms,
                retrieval_precision=retrieval.retrieval_precision,
                cache_hit=False,
            )
            cited_texts: list[str] = []
            for citation in response.citations:
                chunk = await container.vector_store.get_chunk(citation.chunk_id)
                if chunk is not None:
                    cited_texts.append(chunk.text)
            trace = current_trace()
            row_cost = trace.total_cost_usd if trace is not None else 0.0
        duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "id": row["id"],
        "question": row["question"],
        "expected_answer": row.get("expected_answer", ""),
        "answer": response.answer_markdown,
        "cited_texts": cited_texts,
        "anchors": row.get("relevant_anchors", []),
        "human_label": row.get("faithfulness_label"),
        "difficulty": row.get("difficulty", "medium"),
        "faithfulness_score": response.faithfulness_score,
        "retrieval_precision": response.retrieval_precision,
        "duration_ms": duration_ms,
        "cost_usd": round(row_cost, 6),
    }


async def _run_async(args: argparse.Namespace) -> Path:
    if args.live:
        os.environ["MOCK_PROVIDERS"] = "false"
    else:
        os.environ.setdefault("MOCK_PROVIDERS", "true")

    from docs_rag.config import Settings
    from docs_rag.deps import build_container
    from docs_rag.synthesis.prompts import PROMPT_VERSION
    from evals.judge import JudgeClient
    from evals.metrics.calibration import cohens_kappa
    from evals.metrics.citation_accuracy import aggregate, score_citation_accuracy

    settings = Settings()
    container = build_container(settings)

    rows = _load_jsonl(GOLDEN)
    if not rows:
        raise SystemExit("golden_set.jsonl is empty")

    if args.limit:
        rows = rows[: args.limit]

    sem = asyncio.Semaphore(CONCURRENCY)
    started = time.perf_counter()
    results = await asyncio.gather(*(_run_one(container, r, sem) for r in rows))

    judge_verdicts: list[str] = []
    if args.live and not settings.mock_providers:
        judge = JudgeClient(settings)
        try:
            verdicts = await judge.judge_many(
                [(r["question"], r["answer"], r["cited_texts"]) for r in results]
            )
            judge_verdicts = [v.label for v in verdicts]
        finally:
            await judge.aclose()
    else:
        judge_verdicts = [
            "supported" if r["faithfulness_score"] >= 0.5 else "unsupported" for r in results
        ]

    citation_correct = [score_citation_accuracy(r["cited_texts"], r["anchors"]) for r in results]
    citation_score = aggregate(citation_correct).value
    faithfulness = sum(1 for v in judge_verdicts if v == "supported") / len(judge_verdicts)
    retrieval_precision = sum(r["retrieval_precision"] for r in results) / len(results)

    human_rows = _load_jsonl(HUMAN_LABELS)
    human_by_id: dict[str, str] = {r["id"]: r["faithfulness_label"] for r in human_rows}
    paired_human: list[str] = []
    paired_judge: list[str] = []
    for verdict, row in zip(judge_verdicts, results, strict=True):
        if row["id"] in human_by_id:
            paired_human.append(human_by_id[row["id"]])
            paired_judge.append(verdict)
    kappa = cohens_kappa(paired_human, paired_judge) if paired_human else 0.0

    duration = time.perf_counter() - started
    cost_usd = sum(float(r["cost_usd"]) for r in results)

    report: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "git_sha": _git_sha(),
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "synthesis_model": settings.synthesis_model,
        "judge_model": settings.judge_model,
        "mock_providers": settings.mock_providers,
        "scores": [
            {"metric": "faithfulness", "value": round(faithfulness, 4), "n": len(results)},
            {
                "metric": "citation_accuracy",
                "value": round(citation_score, 4),
                "n": len(results),
            },
            {
                "metric": "retrieval_precision",
                "value": round(retrieval_precision, 4),
                "n": len(results),
            },
            {
                "metric": "judge_human_kappa",
                "value": round(max(kappa, 0.0), 4),
                "n": len(paired_human),
            },
        ],
        "by_difficulty": _slice_summary(results),
        "golden_set_size": len(results),
        "duration_seconds": round(duration, 3),
        "cost_usd": round(cost_usd, 6),
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / f"run_{report['run_id']}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_latest_pointer(report, REPORTS / "latest.json")
    await container.aclose()
    return out_path


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _write_latest_pointer(report: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _slice_summary(results: Sequence[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Group per-row faithfulness by difficulty bucket. Surfaces the
    "easy=high, hard=low" split that aggregate scores hide."""
    from collections import defaultdict

    buckets: dict[str, list[float]] = defaultdict(list)
    for r in results:
        buckets[r["difficulty"]].append(float(r["faithfulness_score"]))
    return {
        difficulty: {
            "mean_faithfulness": round(sum(values) / len(values), 4),
            "n": len(values),
        }
        for difficulty, values in buckets.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DocsRAG eval runner")
    parser.add_argument("--live", action="store_true", help="hit real providers")
    parser.add_argument("--limit", type=int, default=None, help="limit golden set rows")
    args = parser.parse_args()
    out = asyncio.run(_run_async(args))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
