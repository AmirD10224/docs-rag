"""Compare two eval reports and emit a markdown diff for the PR comment.

Used by `.github/workflows/eval.yml`. Exits non-zero if any blocking
metric (faithfulness, citation_accuracy) regresses by more than the
threshold defined here. That non-zero exit is what blocks the merge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BLOCKING_METRICS: dict[str, float] = {
    "faithfulness": 0.03,
    "citation_accuracy": 0.03,
}


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object, got {type(data).__name__}")
    return data


def _scores(report: dict[str, Any]) -> dict[str, float]:
    return {item["metric"]: float(item["value"]) for item in report.get("scores", [])}


def render(base: dict[str, Any], head: dict[str, Any]) -> tuple[str, bool]:
    base_scores = _scores(base)
    head_scores = _scores(head)
    keys = sorted(set(base_scores) | set(head_scores))

    lines: list[str] = [
        "### DocsRAG Eval Diff",
        "",
        f"- **base** `{base.get('git_sha', '?')}` ({base.get('created_at', '?')})",
        f"- **head** `{head.get('git_sha', '?')}` ({head.get('created_at', '?')})",
        "",
        "| metric | base | head | delta | gate |",
        "|---|---:|---:|---:|---|",
    ]
    blocked = False
    for key in keys:
        b = base_scores.get(key, 0.0)
        h = head_scores.get(key, 0.0)
        delta = h - b
        gate_status = "-"
        threshold = BLOCKING_METRICS.get(key)
        if threshold is not None:
            if delta < -threshold:
                gate_status = f"❌ regression > {threshold:+.02f}"
                blocked = True
            else:
                gate_status = "✅"
        sign = "+" if delta >= 0 else ""
        lines.append(f"| `{key}` | {b:.4f} | {h:.4f} | {sign}{delta:.4f} | {gate_status} |")

    lines.extend(
        [
            "",
            f"_golden_set_size: {head.get('golden_set_size', '?')} · "
            f"duration: {head.get('duration_seconds', '?')}s · "
            f"cost: ${head.get('cost_usd', 0):.4f}_",
        ]
    )
    return "\n".join(lines), blocked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path, help="prior report (e.g., main)")
    parser.add_argument("head", type=Path, help="new report (this PR)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    base = _load(args.base)
    head = _load(args.head)
    body, blocked = render(base, head)

    if args.out:
        args.out.write_text(body, encoding="utf-8")
    print(body)
    sys.exit(1 if blocked else 0)


if __name__ == "__main__":
    main()
