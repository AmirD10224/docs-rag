"""LLM-as-judge for answer relevancy and faithfulness.

The judge takes (question, answer_markdown, cited_chunk_texts) and
emits one of {supported, partial, unsupported}. We use Claude with a
deterministic temperature so eval runs are reproducible (modulo the
model's stochasticity, which is bounded by temperature=0).

Calibration: human labels live in `evals/human_labels.jsonl`. The
calibration step (see metrics/calibration.py) computes Cohen's kappa
on the rows where both a human and the judge produced a label and
flags the run if the agreement is too low.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Literal

from anthropic import AsyncAnthropic

from docs_rag.config import Settings

JUDGE_PROMPT_VERSION = "judge.v1"
LABELS = ("supported", "partial", "unsupported")
Label = Literal["supported", "partial", "unsupported"]

_JUDGE_SYSTEM = """\
You are an evaluator. Given a question, a candidate answer, and the
source chunks the answer was generated from, classify the answer:

- "supported": every factual claim is grounded in the chunks.
- "partial": some claims are grounded, others are not.
- "unsupported": claims contradict or go beyond the chunks.

Reply with ONE JSON object: {"label": "supported"|"partial"|"unsupported", "reason": "<= 25 words"}.
No prose outside JSON.
"""


@dataclass(slots=True)
class JudgeVerdict:
    label: Label
    reason: str
    raw: str


class JudgeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    async def aclose(self) -> None:
        await self._anthropic.close()

    async def judge(self, question: str, answer: str, sources: list[str]) -> JudgeVerdict:
        user = json.dumps(
            {
                "question": question,
                "answer": answer,
                "sources": sources,
            },
            ensure_ascii=False,
        )
        message = await self._anthropic.messages.create(
            model=self._settings.judge_model,
            max_tokens=200,
            temperature=0.0,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = _first_text(message)
        return _parse(text)

    async def judge_many(
        self, items: list[tuple[str, str, list[str]]], *, concurrency: int = 4
    ) -> list[JudgeVerdict]:
        sem = asyncio.Semaphore(concurrency)

        async def one(q: str, a: str, srcs: list[str]) -> JudgeVerdict:
            async with sem:
                return await self.judge(q, a, srcs)

        return await asyncio.gather(*(one(q, a, s) for q, a, s in items))


def _first_text(message: object) -> str:
    content = getattr(message, "content", [])
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
    return ""


def _parse(text: str) -> JudgeVerdict:
    raw = text.strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match is None:
        return JudgeVerdict(label="unsupported", reason="judge returned no JSON", raw=raw)
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return JudgeVerdict(label="unsupported", reason="judge JSON malformed", raw=raw)
    label_raw = str(payload.get("label", "")).lower().strip()
    label: Label = label_raw if label_raw in LABELS else "unsupported"  # type: ignore[assignment]
    reason = str(payload.get("reason", ""))[:200]
    return JudgeVerdict(label=label, reason=reason, raw=raw)
