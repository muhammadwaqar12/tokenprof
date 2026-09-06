"""JSON output, for piping into something else."""

from __future__ import annotations

from typing import Any

from ctxprof.diff import TurnDiff
from ctxprof.types import Category, Profile, Turn


def turn_to_dict(turn: Turn) -> dict[str, Any]:
    return {
        "index": turn.index,
        "model": turn.model,
        "provider": turn.provider,
        "tokenizer": turn.tokenizer,
        "total_tokens": turn.total_tokens,
        "total_chars": turn.total_chars,
        "fixed_overhead_tokens": turn.fixed_overhead_tokens(),
        "by_category": {c.value: n for c, n in turn.by_category().items()},
        "tool_schemas": turn.by_name(Category.TOOL_SCHEMA),
        "segments": [
            {
                "category": s.category.value,
                "name": s.name,
                "index": s.index,
                "tokens": s.tokens,
                "chars": s.chars,
            }
            for s in turn.segments
        ],
    }


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    return {
        "turns": [turn_to_dict(t) for t in profile.turns],
        "summary": {
            "turn_count": len(profile.turns),
            "total_tokens": profile.total_tokens,
            "fixed_overhead_tokens": profile.fixed_overhead_tokens(),
        },
    }


def diff_to_dict(d: TurnDiff) -> dict[str, Any]:
    def delta(x: Any) -> dict[str, Any]:
        return {"key": x.key, "before": x.before, "after": x.after, "change": x.change}

    return {
        "before_index": d.before_index,
        "after_index": d.after_index,
        "total": delta(d.total),
        "categories": [delta(x) for x in d.categories],
        "tool_schemas": [delta(x) for x in d.tools],
    }
