"""Plain-text reports.

No rendering dependency. rich is nice and it is not worth making someone
install anything to find out where their tokens went.
"""

from __future__ import annotations

from tokenprof.cache import CacheReport
from tokenprof.cost import cost_split, cost_usd
from tokenprof.diff import TurnDiff
from tokenprof.types import Category, Profile, Turn

BAR_WIDTH = 28
TURN_RULE = "-" * (20 + 9 + 7 + BAR_WIDTH + 13)
SESSION_RULE = "-" * (5 + 9 + 9 + 6 + BAR_WIDTH + 5)


def _bar(fraction: float, width: int = BAR_WIDTH) -> str:
    filled = int(round(fraction * width))
    return "#" * filled + "." * (width - filled)


def _pct(part: int, whole: int) -> float:
    return (part / whole) if whole else 0.0


def _fmt_cost(tokens: int, model: str, rate: float | None) -> str:
    c = cost_usd(tokens, model, rate)
    return f"${c:,.4f}" if c is not None else "  -   "


def render_turn(turn: Turn, top: int = 10, rate: float | None = None) -> str:
    total = turn.total_tokens
    lines = [
        f"turn {turn.index}  model={turn.model or '?'}  provider={turn.provider}",
        f"tokenizer: {turn.tokenizer}",
        "",
        f"{'category':<20} {'tokens':>9} {'share':>7}  {'':<{BAR_WIDTH}} {'cost':>9}",
        TURN_RULE,
    ]
    for cat, n in sorted(turn.by_category().items(), key=lambda kv: kv[1], reverse=True):
        frac = _pct(n, total)
        lines.append(
            f"{cat.label:<20} {n:>9,} {frac * 100:>6.1f}%  "
            f"{_bar(frac)} {_fmt_cost(n, turn.model, rate):>9}"
        )
    lines.append(TURN_RULE)
    lines.append(
        f"{'TOTAL':<20} {total:>9,} {'100.0%':>7}  {'':<{BAR_WIDTH}} "
        f"{_fmt_cost(total, turn.model, rate):>9}"
    )

    if turn.cached_tokens():
        split = cost_split(
            turn.cached_tokens(), turn.uncached_tokens(), turn.model, turn.provider, rate
        )
        lines.append("")
        msg = (
            f"marked for caching: {turn.cached_tokens():,} tokens "
            f"({_pct(turn.cached_tokens(), total) * 100:.1f}%)"
        )
        if split is not None:
            naive = cost_usd(total, turn.model, rate)
            msg += f", so this turn bills ${sum(split):,.4f} rather than ${naive:,.4f}"
        lines.append(msg)

    overhead = turn.fixed_overhead_tokens()
    if overhead:
        lines.append("")
        lines.append(
            f"fixed overhead (system + tool schemas): {overhead:,} tokens "
            f"({_pct(overhead, total) * 100:.1f}% of this turn), re-sent on every request"
            + (", at cache rates where marked" if turn.cached_tokens() else "")
        )

    tools = turn.by_name(Category.TOOL_SCHEMA)
    if tools:
        lines.append("")
        lines.append(f"tool schemas ({len(tools)} registered)")
        for name, n in sorted(tools.items(), key=lambda kv: kv[1], reverse=True)[:top]:
            lines.append(f"  {name:<34} {n:>7,}  {_bar(_pct(n, total), 18)}")
        if len(tools) > top:
            lines.append(f"  ... {len(tools) - top} more")

    biggest = turn.top(top)
    if biggest:
        lines.append("")
        lines.append(f"largest segments (top {min(top, len(biggest))})")
        for s in biggest:
            label = s.name or s.category.label
            where = f"[{s.index}]" if s.index is not None else "   "
            lines.append(f"  {where:<5} {s.category.value:<18} {label:<26} {s.tokens:>7,}")
    return "\n".join(lines)


def render_profile(profile: Profile, top: int = 10, rate: float | None = None) -> str:
    if not profile.turns:
        return "no turns found"

    model = profile.turns[0].model
    total = profile.total_tokens
    overhead = profile.fixed_overhead_tokens()

    lines = [
        f"{len(profile.turns)} turns  |  {total:,} input tokens  |  "
        f"{_fmt_cost(total, model, rate).strip()}",
        "",
        f"{'turn':>5} {'tokens':>9} {'overhead':>9} {'tools':>6}",
        SESSION_RULE,
    ]
    peak = max(t.total_tokens for t in profile.turns) or 1
    for t in profile.turns:
        n_tools = len(t.by_name(Category.TOOL_SCHEMA))
        lines.append(
            f"{t.index:>5} {t.total_tokens:>9,} {t.fixed_overhead_tokens():>9,} "
            f"{n_tools:>6}  {_bar(_pct(t.total_tokens, peak))}"
        )
    lines.append(SESSION_RULE)
    lines.append("")
    lines.append(
        f"fixed overhead across the session: {overhead:,} tokens "
        f"({_pct(overhead, total) * 100:.1f}% of all input), "
        f"{_fmt_cost(overhead, model, rate).strip()}"
    )
    growth = profile.turns[-1].total_tokens - profile.turns[0].total_tokens
    lines.append(
        f"turn 0 -> turn {profile.turns[-1].index}: "
        f"{profile.turns[0].total_tokens:,} -> {profile.turns[-1].total_tokens:,} tokens "
        f"({growth:+,})"
    )
    return "\n".join(lines)


def render_diff(d: TurnDiff, rate: float | None = None, model: str = "") -> str:
    def row(label: str, before: int, after: int) -> str:
        change = after - before
        pct = f"{(change / before * 100):+.1f}%" if before else "   new"
        return f"{label:<24} {before:>9,} {after:>9,} {change:>+9,} {pct:>8}"

    lines = [
        f"turn {d.before_index} -> turn {d.after_index}",
        "",
        f"{'':<24} {'before':>9} {'after':>9} {'change':>9} {'pct':>8}",
        "-" * 62,
        row("TOTAL", d.total.before, d.total.after),
        "-" * 62,
    ]
    for x in d.categories:
        lines.append(row(x.key, x.before, x.after))
    if d.tools:
        lines.append("")
        lines.append("tool schema changes")
        for x in d.tools:
            state = "added" if x.before == 0 else "removed" if x.after == 0 else "changed"
            lines.append(f"  {x.key:<30} {x.change:>+8,}  ({state})")
    return "\n".join(lines)


def render_cache(report: CacheReport, profile: Profile, rate: float | None = None) -> str:
    if not report.breaks:
        return "need at least two turns to analyse the prompt cache"

    provider = profile.turns[0].provider
    model = profile.turns[0].model
    lines = [
        f"prompt cache, {len(profile.turns)} turns  provider={provider}",
        "",
        f"{'turns':>9} {'stable':>9} {'total':>9} {'share':>7}  what broke the prefix",
        "-" * 74,
    ]
    for b in report.breaks:
        who = (
            "(nothing, append-only)"
            if b.healthy
            else (f"{b.breaking.category.value}:{b.breaking.name or '(unnamed)'}")
        )
        lines.append(
            f"{b.before_index:>4} -> {b.after_index:<2} {b.stable_tokens:>9,} "
            f"{b.total_tokens:>9,} {b.stable_share * 100:>6.1f}%  {who}"
        )
    lines.append("-" * 74)
    lines.append("")
    lines.append(
        f"reusable across turns: {report.reusable_tokens:,} tokens "
        f"| re-sent after a break: {report.rebuilt_tokens:,}"
    )

    if report.marked_tokens:
        split = cost_split(report.marked_tokens, 0, model, provider, rate)
        note = ""
        if split is not None:
            full = cost_usd(report.marked_tokens, model, rate)
            if full:
                note = f", ${split[0]:,.4f} instead of ${full:,.4f}"
        lines.append(f"explicitly marked for caching: {report.marked_tokens:,} tokens{note}")
    elif provider == "anthropic_messages":
        lines.append(
            "no cache_control markers found. Anthropic caching is opt-in, so none "
            "of this is being cached."
        )

    offenders = report.offenders()
    if offenders:
        lines.append("")
        lines.append("segments that broke the prefix")
        for key, n in offenders.items():
            lines.append(f"  {key:<44} {n:>3}x")

    if report.thrashing:
        worst = report.worst
        lines.append("")
        lines.append(
            f"WARNING: the prefix breaks early. Turn {worst.after_index} reuses only "
            f"{worst.stable_share * 100:.1f}% of its prompt."
        )
        lines.append(
            "  Anything that changes near the front of the prompt costs you the whole "
            "cache. Timestamps, session ids and reordered tool lists are the usual "
            "causes. Move volatile content to the end."
        )
    return "\n".join(lines)
