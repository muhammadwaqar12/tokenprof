"""Core data types.

A Turn is one request as it was actually sent to a model. A Segment is a
contiguous piece of that request with a category and a token count. The whole
point of this package is that a token total tells you nothing, and a token
total broken down by where it came from tells you what to fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    """Where a chunk of context came from.

    Kept deliberately small. Every category here is one someone can act on:
    if you cannot do something different in response to a category, it does
    not earn a slot.
    """

    SYSTEM = "system"
    TOOL_SCHEMA = "tool_schema"
    TOOL_RESULT = "tool_result"
    HISTORY_USER = "history_user"
    HISTORY_ASSISTANT = "history_assistant"
    CURRENT_USER = "current_user"
    OTHER = "other"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


#: Categories that are fixed overhead paid on every single turn, whether or
#: not the model uses them. These are the ones worth attacking first.
FIXED_OVERHEAD = frozenset({Category.SYSTEM, Category.TOOL_SCHEMA})


@dataclass(frozen=True)
class Segment:
    """One attributable piece of a request."""

    category: Category
    tokens: int
    chars: int
    #: Human-readable name. For tool schemas this is the tool name, which is
    #: what makes the report actionable rather than merely informative.
    name: str = ""
    #: Position within the message list, when the segment came from one.
    index: int | None = None

    def __post_init__(self) -> None:
        if self.tokens < 0:
            raise ValueError("tokens cannot be negative")
        if self.chars < 0:
            raise ValueError("chars cannot be negative")


@dataclass
class Turn:
    """One request to a model, broken into segments."""

    segments: list[Segment] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    index: int = 0
    tokenizer: str = ""

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.segments)

    @property
    def total_chars(self) -> int:
        return sum(s.chars for s in self.segments)

    def by_category(self) -> dict[Category, int]:
        out: dict[Category, int] = {}
        for s in self.segments:
            out[s.category] = out.get(s.category, 0) + s.tokens
        return out

    def by_name(self, category: Category) -> dict[str, int]:
        """Token totals per named segment within one category.

        Used for the tool-schema breakdown, which is the view that usually
        surprises people.
        """
        out: dict[str, int] = {}
        for s in self.segments:
            if s.category is category:
                key = s.name or "(unnamed)"
                out[key] = out.get(key, 0) + s.tokens
        return out

    def fixed_overhead_tokens(self) -> int:
        return sum(s.tokens for s in self.segments if s.category in FIXED_OVERHEAD)

    def top(self, n: int = 10) -> list[Segment]:
        return sorted(self.segments, key=lambda s: s.tokens, reverse=True)[:n]


@dataclass
class Profile:
    """A sequence of turns from one session."""

    turns: list[Turn] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self.turns)

    def fixed_overhead_tokens(self) -> int:
        """Fixed overhead summed across every turn.

        This is the number that makes the case: a per-turn cost of a few
        thousand tokens is easy to wave away, and the same cost multiplied by
        every request in a session is not.
        """
        return sum(t.fixed_overhead_tokens() for t in self.turns)
