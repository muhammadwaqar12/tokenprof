"""Prompt cache analysis.

Providers cache a *prefix*. If the first N tokens of a request are
byte-identical to the previous one, you pay a fraction for them. One volatile
value near the front (a timestamp, a session id, a re-ordered tool list) moves
the break point to zero and you quietly pay full price on every turn while
your dashboard still reports that caching is enabled.

This module finds that break point by walking two turns segment by segment
and comparing content digests.
"""

from __future__ import annotations

from dataclasses import dataclass

from tokenprof.types import Profile, Segment, Turn


@dataclass(frozen=True)
class PrefixBreak:
    """Where one turn stopped matching the previous one."""

    before_index: int
    after_index: int
    #: Segments that matched, counted from the start of the prompt.
    stable_segments: int
    stable_tokens: int
    total_tokens: int
    #: The first segment that differed, from the later turn. None when the
    #: whole earlier prompt is still a prefix of the later one, which is the
    #: healthy case for an append-only conversation.
    breaking: Segment | None = None

    @property
    def stable_share(self) -> float:
        return self.stable_tokens / self.total_tokens if self.total_tokens else 0.0

    @property
    def healthy(self) -> bool:
        """True when nothing in the shared region changed."""
        return self.breaking is None


def prefix_break(before: Turn, after: Turn) -> PrefixBreak:
    """Compare two turns and find where the cacheable prefix ends."""
    n = 0
    breaking: Segment | None = None
    for a, b in zip(before.segments, after.segments):
        if a.digest and a.digest == b.digest:
            n += 1
            continue
        breaking = b
        break

    stable = sum(s.tokens for s in after.segments[:n])
    return PrefixBreak(
        before_index=before.index,
        after_index=after.index,
        stable_segments=n,
        stable_tokens=stable,
        total_tokens=after.total_tokens,
        breaking=breaking,
    )


@dataclass
class CacheReport:
    breaks: list[PrefixBreak]
    #: Tokens the provider was explicitly told to cache, summed over turns.
    marked_tokens: int = 0
    #: Tokens that were re-sent unchanged and could have been cached.
    reusable_tokens: int = 0
    #: Tokens re-sent after the prefix broke, so full price every turn.
    rebuilt_tokens: int = 0

    @property
    def worst(self) -> PrefixBreak | None:
        unhealthy = [b for b in self.breaks if not b.healthy]
        if not unhealthy:
            return None
        return min(unhealthy, key=lambda b: b.stable_share)

    @property
    def thrashing(self) -> bool:
        """True when the prefix breaks early enough to lose most of the win."""
        return any(not b.healthy and b.stable_share < 0.5 for b in self.breaks)

    def offenders(self) -> dict[str, int]:
        """How often each segment is the one that broke the prefix."""
        out: dict[str, int] = {}
        for b in self.breaks:
            if b.breaking is None:
                continue
            key = f"{b.breaking.category.value}:{b.breaking.name or '(unnamed)'}"
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def analyze(profile: Profile) -> CacheReport:
    report = CacheReport(breaks=[])
    for before, after in zip(profile.turns, profile.turns[1:]):
        b = prefix_break(before, after)
        report.breaks.append(b)
        report.reusable_tokens += b.stable_tokens
        report.rebuilt_tokens += b.total_tokens - b.stable_tokens
    report.marked_tokens = sum(t.cached_tokens() for t in profile.turns)
    return report
