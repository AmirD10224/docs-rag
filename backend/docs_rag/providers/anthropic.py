"""Claude Sonnet 4.6 synthesis client with structured-output enforcement.

Strategy:
  - Use the Messages API with system prompt + user prompt.
  - Force JSON via a strict response schema in the prompt and validate
    with pydantic. Retry-repair (one shot) is handled by the synthesis
    layer, not here, this client only does the network round-trip.
  - Surface input/output token counts so cost tracing is exact.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import httpx
import structlog
from anthropic import APIError, AsyncAnthropic, RateLimitError
from anthropic.types import TextBlock
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docs_rag.config import Settings
from docs_rag.observability.pricing import claude_cost
from docs_rag.observability.tracing import traced
from docs_rag.providers.base import AnthropicError
from docs_rag.synthesis.schema import SynthesisOutput

__all__ = ["AnthropicClient", "AnthropicError"]

_log = structlog.get_logger(__name__)


class AnthropicClient:
    def __init__(
        self,
        settings: Settings,
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=httpx.Timeout(
                connect=5.0, read=settings.anthropic_timeout_seconds, write=10.0, pool=5.0
            ),
            max_retries=0,  # we control retries via tenacity at the call site
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def synthesize(
        self, system: str, user: str, *, max_tokens: int = 2048
    ) -> tuple[SynthesisOutput, int, int]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type((RateLimitError, APIError)),
            reraise=True,
        ):
            with attempt:
                message = await self._client.messages.create(
                    model=self._settings.synthesis_model,
                    max_tokens=max_tokens,
                    temperature=0.0,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )

        text = _first_text_block(message.content)
        in_tokens = message.usage.input_tokens
        out_tokens = message.usage.output_tokens

        with traced(
            "synthesis.claude",
            cost_usd=claude_cost(in_tokens, out_tokens, self._settings),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            model=self._settings.synthesis_model,
        ):
            pass

        try:
            parsed = SynthesisOutput.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValueError) as exc:
            raise AnthropicError(f"claude returned non-conforming JSON: {exc}") from exc
        return parsed, in_tokens, out_tokens

    async def raw_text(
        self, system: str, user: str, *, max_tokens: int = 1024, model: str | None = None
    ) -> tuple[str, int, int]:
        """Plain text completion used by judge.py for eval LLM-as-judge."""
        target_model = model or self._settings.judge_model
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type((RateLimitError, APIError)),
            reraise=True,
        ):
            with attempt:
                message = await self._client.messages.create(
                    model=target_model,
                    max_tokens=max_tokens,
                    temperature=0.0,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
        text = _first_text_block(message.content)
        return text, message.usage.input_tokens, message.usage.output_tokens


def _first_text_block(blocks: Iterable[object]) -> str:
    """Return the text of the first TextBlock in a Claude response.

    The Anthropic SDK returns a heterogeneous block list (text, thinking,
    tool_use, ...). We accept Iterable[object] so the call site can pass
    whatever the SDK yields without invariance pain.
    """
    for block in blocks:
        if isinstance(block, TextBlock):
            return block.text
    raise AnthropicError("claude response had no text block")
