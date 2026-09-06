"""Compare two turns.

Growth between turns is the thing you actually want to catch. A single turn
tells you where the tokens are; a diff tells you what is accumulating, which
is what turns into a cost problem three hundred turns later.
"""

from __future__ import annotations

from dataclasses import dataclass

from ctxprof.types import Category, Turn


@dataclass(frozen=True)
class Delta:
    key: str
    before: int
    after: int

    @property
    def change(self) -> int:
        return self.after - self.before

    @property
    def pct(self) -> float | None:
        if self.before == 0:
            return None
        return (self.after - self.before) / self.before * 100.0


@dataclass
class TurnDiff:
    before_index: int
    after_index: int
    total: Delta
    categories: list[Delta]
    tools: list[Delta]

    @property
    def grew(self) -> bool:
        return self.total.change > 0


def diff_turns(before: Turn, after: Turn) -> TurnDiff:
    cats_b, cats_a = before.by_category(), after.by_category()
    cat_deltas = [
        Delta(c.label, cats_b.get(c, 0), cats_a.get(c, 0))
        for c in Category
        if cats_b.get(c, 0) or cats_a.get(c, 0)
    ]
    cat_deltas.sort(key=lambda d: abs(d.change), reverse=True)

    tools_b = before.by_name(Category.TOOL_SCHEMA)
    tools_a = after.by_name(Category.TOOL_SCHEMA)
    tool_deltas = [
        Delta(name, tools_b.get(name, 0), tools_a.get(name, 0))
        for name in sorted(set(tools_b) | set(tools_a))
        if tools_b.get(name, 0) != tools_a.get(name, 0)
    ]
    tool_deltas.sort(key=lambda d: abs(d.change), reverse=True)

    return TurnDiff(
        before_index=before.index,
        after_index=after.index,
        total=Delta("total", before.total_tokens, after.total_tokens),
        categories=cat_deltas,
        tools=tool_deltas,
    )
