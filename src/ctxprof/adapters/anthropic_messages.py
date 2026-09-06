"""Anthropic Messages API request payloads."""

from __future__ import annotations

from typing import Any

from ctxprof.adapters.base import measure, stringify
from ctxprof.tokenizer import Tokenizer
from ctxprof.types import Category, Segment


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
        out: list[Segment] = []

        system = request.get("system")
        if system is not None:
            # System can be a bare string or a list of blocks, and the block
            # form is how cache_control gets attached, so both are common.
            if isinstance(system, list):
                for i, block in enumerate(system):
                    text = block.get("text", "") if isinstance(block, dict) else str(block)
                    t, c = measure(text, tok)
                    if t or c:
                        out.append(Segment(Category.SYSTEM, t, c, name=f"block[{i}]", index=i))
            else:
                t, c = measure(str(system), tok)
                if t or c:
                    out.append(Segment(Category.SYSTEM, t, c, name="system"))

        for spec in request.get("tools") or []:
            name = spec.get("name", "?") if isinstance(spec, dict) else "?"
            t, c = measure(stringify(spec), tok)
            out.append(Segment(Category.TOOL_SCHEMA, t, c, name=name))

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
            for cat, name, text in _split_content(content, role):
                t, c = measure(text, tok)
                if t == 0 and c == 0:
                    continue
                if cat is None:
                    cat = (
                        Category.CURRENT_USER
                        if role == "user" and i == last_user
                        else Category.HISTORY_USER
                        if role == "user"
                        else Category.HISTORY_ASSISTANT
                        if role == "assistant"
                        else Category.OTHER
                    )
                out.append(Segment(cat, t, c, name=name, index=i))

        return out


def _last_user_index(messages: list[Any]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "user":
            return i
    return -1


def _split_content(content: Any, role: str) -> list[tuple[Category | None, str, str]]:
    """Break message content into (category_override, name, text) pieces."""
    if content is None:
        return []
    if isinstance(content, str):
        return [(None, "", content)]
    if not isinstance(content, list):
        return [(None, "", stringify(content))]

    out: list[tuple[Category | None, str, str]] = []
    for block in content:
        if not isinstance(block, dict):
            out.append((None, "", str(block)))
            continue
        btype = block.get("type")
        if btype == "tool_result":
            name = str(block.get("tool_use_id") or "tool_result")
            out.append((Category.TOOL_RESULT, name, stringify(block.get("content"))))
        elif btype == "tool_use":
            name = str(block.get("name") or "tool_use")
            out.append((Category.HISTORY_ASSISTANT, name, stringify(block)))
        elif btype == "text":
            out.append((None, "", block.get("text", "")))
        else:
            out.append((None, str(btype or ""), stringify(block)))
    return out
