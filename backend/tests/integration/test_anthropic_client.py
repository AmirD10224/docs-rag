"""Integration tests for the AnthropicClient using a fake AsyncAnthropic.

We don't hit the real network. Instead, we hand the client a stand-in
that records calls and returns canned messages. This exercises:
  - Successful synthesize → SynthesisOutput parse path
  - JSON parse failure → AnthropicError
  - Missing TextBlock → AnthropicError
  - aclose() round-trip
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import SecretStr

from docs_rag.config import Settings
from docs_rag.providers.anthropic import AnthropicClient, AnthropicError
from docs_rag.synthesis.schema import Claim, SynthesisOutput


@dataclass(slots=True)
class _Usage:
    input_tokens: int
    output_tokens: int


class _FakeMessage:
    def __init__(self, content: list[Any], usage: _Usage) -> None:
        self.content = content
        self.usage = usage


class _FakeMessages:
    def __init__(self, message: _FakeMessage) -> None:
        self._message = message
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return self._message


class _FakeAsyncAnthropic:
    def __init__(self, message: _FakeMessage) -> None:
        self.messages = _FakeMessages(message)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _make_settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("test"),
        synthesis_model="claude-sonnet-4-6",
        judge_model="claude-sonnet-4-6",
    )


def _well_formed_payload() -> str:
    return json.dumps(
        SynthesisOutput(
            answer_markdown="The doc supports the claim.",
            claims=[Claim(text="The doc supports the claim.", chunk_ids=["c1"])],
            refused=False,
            refusal_reason=None,
        ).model_dump()
    )


def _text_block(text: str) -> Any:
    """Minimal TextBlock-shaped object that passes isinstance checks.

    We import the real TextBlock so the production isinstance branch fires.
    """
    from anthropic.types import TextBlock

    return TextBlock(type="text", text=text, citations=None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synthesize_parses_well_formed_json() -> None:
    fake = _FakeAsyncAnthropic(
        _FakeMessage(
            content=[_text_block(_well_formed_payload())],
            usage=_Usage(input_tokens=120, output_tokens=40),
        )
    )
    client = AnthropicClient(_make_settings(), client=fake)  # type: ignore[arg-type]
    output, in_tok, out_tok = await client.synthesize("system", "user")
    assert isinstance(output, SynthesisOutput)
    assert output.claims[0].chunk_ids == ["c1"]
    assert (in_tok, out_tok) == (120, 40)
    assert fake.messages.calls[0]["model"] == "claude-sonnet-4-6"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synthesize_raises_on_invalid_json() -> None:
    fake = _FakeAsyncAnthropic(
        _FakeMessage(
            content=[_text_block("this is not json")],
            usage=_Usage(input_tokens=10, output_tokens=10),
        )
    )
    client = AnthropicClient(_make_settings(), client=fake)  # type: ignore[arg-type]
    with pytest.raises(AnthropicError):
        await client.synthesize("system", "user")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synthesize_raises_when_no_text_block() -> None:
    fake = _FakeAsyncAnthropic(
        _FakeMessage(
            content=[],  # no text block at all
            usage=_Usage(input_tokens=1, output_tokens=1),
        )
    )
    client = AnthropicClient(_make_settings(), client=fake)  # type: ignore[arg-type]
    with pytest.raises(AnthropicError):
        await client.synthesize("system", "user")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raw_text_returns_first_text_block() -> None:
    fake = _FakeAsyncAnthropic(
        _FakeMessage(
            content=[_text_block("plain answer")],
            usage=_Usage(input_tokens=5, output_tokens=2),
        )
    )
    client = AnthropicClient(_make_settings(), client=fake)  # type: ignore[arg-type]
    text, in_tok, out_tok = await client.raw_text("system", "user")
    assert text == "plain answer"
    assert (in_tok, out_tok) == (5, 2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aclose_calls_underlying_client() -> None:
    fake = _FakeAsyncAnthropic(
        _FakeMessage(content=[], usage=_Usage(input_tokens=0, output_tokens=0))
    )
    client = AnthropicClient(_make_settings(), client=fake)  # type: ignore[arg-type]
    await client.aclose()
    assert fake.closed is True
