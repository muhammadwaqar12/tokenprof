"""Anthropic Messages API request payloads."""

from __future__ import annotations

import dataclasses
from typing import Any

from tokenprof.adapters.base import measure, stringify
from tokenprof.tokenizer import Tokenizer
from tokenprof.types import Category, Segment


class AnthropicMessagesAdapter:
    name = "anthropic_messages"

    def matches(self, request: dict[str, Any]) -> bool:
        if not isinstance(request.get("messages"), list):
            return False
        if isinstance(request.get("system"), (str, list)):
            return True
        for spec in request.get("tools") or []:
            if isinstance(spec, dict) and "input_schema" in spec:
                return True
        return False

    def model_of(self, request: dict[str, Any]) -> str:
        return str(request.get("model", ""))

    def segments(self, request: dict[str, Any], tok: Tokenizer) -> list[Segment]:
        # Emitted in the order the provider actually assembles the prompt:
        # tools, then system, then messages. Cache prefixes are computed over
        # that order, so getting it wrong would put the breakpoint in the
        # wrong place.
        out: list[Segment] = []
        marked: list[int] = []

        for spec in request.get("tools") or []:
            name = spec.get("name", "?") if isinstance(spec, dict) else "?"
            t, c, dg = measure(stringify(spec), tok)
            if isinstance(spec, dict) and spec.get("cache_control"):
                marked.append(len(out))
            out.append(Segment(Category.TOOL_SCHEMA, t, c, name=name, digest=dg))

        system = request.get("system")
        if system is not None:
            if isinstance(system, list):
                for i, block in enumerate(system):
                    text = block.get("text", "") if isinstance(block, dict) else str(block)
                    t, c, dg = measure(text, tok)
                    if not (t or c):
                        continue
                    if isinstance(block, dict) and block.get("cache_control"):
                        marked.append(len(out))
                    out.append(
                        Segment(Category.SYSTEM, t, c, name=f"block[{i}]", index=i, digest=dg)
                    )
            else:
                t, c, dg = measure(str(system), tok)
                if t or c:
                    out.append(Segment(Category.SYSTEM, t, c, name="system", digest=dg))

        messages = request.get("messages") or []
        last_user = _last_user_index(messages)

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "")
            content = msg.get("content")

            # A single user message can carry several tool_result blocks. They
            # are attributed individually, because "which tool is flooding the
            # context" is the question worth answering.
            for cat, name, text, is_marked in _split_content(content, role):
                t, c, dg = measure(text, tok)
                if t == 0 and c == 0:
                    continue
                if cat is None:
                    cat = _role_category(role, i == last_user)
                if is_marked:
                    marked.append(len(out))
                out.append(Segment(cat, t, c, name=name, index=i, digest=dg))

        # A cache_control marker caches the whole prefix up to and including
        # that block, so only the last marker matters for how much is cached.
        if marked:
            cutoff = max(marked)
            out = [
                dataclasses.replace(s, cached=True) if i <= cutoff else s for i, s in enumerate(out)
            ]
        return out


def _role_category(role: str, is_last_user: bool) -> Category:
    if role == "user":
        return Category.CURRENT_USER if is_last_user else Category.HISTORY_USER
    if role == "assistant":
        return Category.HISTORY_ASSISTANT
    return Category.OTHER


def _last_user_index(messages: list[Any]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "user":
            return i
    return -1


def _split_content(content: Any, role: str) -> list[tuple[Category | None, str, str, bool]]:
    """Break message content into (category_override, name, text, cache_marked)."""
    if content is None:
        return []
    if isinstance(content, str):
        return [(None, "", content, False)]
    if not isinstance(content, list):
        return [(None, "", stringify(content), False)]

    out: list[tuple[Category | None, str, str, bool]] = []
    for block in content:
        if not isinstance(block, dict):
            out.append((None, "", str(block), False))
            continue
        marked = bool(block.get("cache_control"))
        btype = block.get("type")
        if btype == "tool_result":
            name = str(block.get("tool_use_id") or "tool_result")
            out.append((Category.TOOL_RESULT, name, stringify(block.get("content")), marked))
        elif btype == "tool_use":
            name = str(block.get("name") or "tool_use")
            out.append((Category.HISTORY_ASSISTANT, name, stringify(block), marked))
        elif btype == "text":
            out.append((None, "", block.get("text", ""), marked))
        else:
            out.append((None, str(btype or ""), stringify(block), marked))
    return out
