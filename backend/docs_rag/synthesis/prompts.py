"""Prompt loader and lightweight templating.

We deliberately don't pull in jinja for two reasons: (1) the templates
are trivial (`{{var}}` substitution) so the dependency adds no value,
and (2) eval reproducibility is easier when the rendering function is
30 lines of stdlib.

Each prompt has a stable PROMPT_VERSION constant referenced in eval
reports so a regression can be attributed to the prompt edit that
caused it.

Security: variable values are substituted in a single pass via
`re.sub` so a value that itself contains `{{x}}` syntax cannot trigger
re-substitution (the classic prompt-template injection bug). User-
controlled chunk content is also escaped on the way in, see
`escape_for_prompt`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PROMPT_VERSION = "synthesis.v1"
REPAIR_PROMPT_VERSION = "repair.v1"

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


@lru_cache(maxsize=8)
def _load(name: str) -> str:
    path = Path(__file__).resolve().parents[2] / "prompts" / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL)


def escape_for_prompt(text: str) -> str:
    """Neutralize prompt-template metacharacters in untrusted input.

    Replaces `{{...}}` so a malicious chunk cannot smuggle in template
    placeholders that would consume our `{{question}}` slot or look like
    instructions to the model. Also strips ANSI/control bytes that show
    up in scraped HTML.
    """
    no_placeholder = text.replace("{{", "{ {").replace("}}", "} }")
    return "".join(ch for ch in no_placeholder if ch in {"\n", "\t"} or ch >= " ")


def render(name: str, **vars_: str) -> tuple[str, str]:
    """Return (system, user) split on the `# User` delimiter.

    Substitution is single-pass: a value that contains `{{x}}` is NOT
    re-expanded, defeating the most obvious prompt-template injection.
    """
    template = _load(name)

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in vars_:
            raise ValueError(f"unfilled prompt var {key!r} in {name}")
        return vars_[key]

    rendered = _PLACEHOLDER_RE.sub(_replace, template)
    parts = re.split(r"^# User\s*$", rendered, maxsplit=1, flags=re.MULTILINE)
    if len(parts) != 2:
        raise ValueError(f"prompt {name} missing '# User' delimiter")
    system, user = parts
    system = re.sub(r"^# System\s*$", "", system, count=1, flags=re.MULTILINE)
    return system.strip(), user.strip()
