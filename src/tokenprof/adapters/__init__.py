"""Adapter registry.

Adding a framework means adding a module here and one line to ADAPTERS.
That is the intended contribution surface.
"""

from __future__ import annotations

from typing import Any

from tokenprof.adapters.anthropic_messages import AnthropicMessagesAdapter
from tokenprof.adapters.base import Adapter
from tokenprof.adapters.openai_chat import OpenAIChatAdapter

ADAPTERS: list[Adapter] = [
    AnthropicMessagesAdapter(),
    OpenAIChatAdapter(),
]


def get_adapter(name: str) -> Adapter:
    for a in ADAPTERS:
        if a.name == name:
            return a
    known = ", ".join(a.name for a in ADAPTERS)
    raise KeyError(f"unknown adapter {name!r}. known adapters: {known}")


def detect(request: dict[str, Any]) -> Adapter:
    """Pick an adapter by payload shape.

    Order matters: Anthropic is checked first because its signals are
    positive (top-level system, input_schema) while the OpenAI adapter
    accepts the general case.
    """
    for a in ADAPTERS:
        if a.matches(request):
            return a
    raise ValueError(
        "could not detect a provider from this payload. "
        "Pass --provider explicitly, or open an issue with a redacted sample."
    )


__all__ = ["ADAPTERS", "Adapter", "detect", "get_adapter"]
