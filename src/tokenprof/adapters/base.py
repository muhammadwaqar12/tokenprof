"""Adapter contract.

An adapter turns one provider's request payload into a list of Segments.
That is the whole interface. Keeping it this narrow is what makes a new
adapter an afternoon of work instead of a refactor, and it is why the core
has no dependency on any framework.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from tokenprof.tokenizer import Tokenizer
from tokenprof.types import Segment


class Adapter(Protocol):
    #: Short identifier used by --provider and in reports.
    name: str

    def matches(self, request: dict[str, Any]) -> bool:
        """True if this adapter understands the payload shape."""
        ...

    def model_of(self, request: dict[str, Any]) -> str: ...

    def segments(self, request: dict[str, Any], tok: Tokenizer) -> list[Segment]: ...


def measure(text: str, tok: Tokenizer) -> tuple[int, int]:
    """Return (tokens, chars) for a string."""
    return tok.count(text), len(text)


def stringify(value: Any) -> str:
    """Flatten a value the way a provider serializes it into the prompt.

    Tool schemas and structured content reach the model as JSON, so counting
    the JSON is closer to the truth than counting a Python repr. Not exact,
    since providers wrap this in their own formatting, and the wrapper is
    small relative to the payload.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
