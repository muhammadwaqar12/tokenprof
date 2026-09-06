"""OpenAI Chat Completions request payloads."""

from __future__ import annotations

from typing import Any

from tokenprof.adapters.base import measure, stringify
from tokenprof.tokenizer import Tokenizer
from tokenprof.types import Category, Segment


class OpenAIChatAdapter:
    name = "openai_chat"

    def matches(self, request: dict[str, Any]) -> bool:
        """Discriminate against Anthropic, which also uses a "messages" list.

        Two signals only one of them has: Anthropic puts the system prompt at
        the top level, and its tool specs carry "input_schema". OpenAI wraps
        tool specs in "function" and keeps the system prompt inside messages.
        """
        if not isinstance(request.get("messages"), list):
            return False
        if isinstance(request.get("system"), (str, list)):
            return False
        for spec in request.get("tools") or []:
            if isinstance(spec, dict):
                if "input_schema" in spec:
                    return False
                if "function" in spec:
                    return True
        return True

    def model_of(self, request: dict[str, Any]) -> str:
        return str(request.get("model", ""))

    def segments(self, request: dict[str, Any], tok: Tokenizer) -> list[Segment]:
        out: list[Segment] = []

        for spec in request.get("tools") or []:
            fn = spec.get("function", spec) if isinstance(spec, dict) else {}
            name = fn.get("name", "?") if isinstance(fn, dict) else "?"
            t, c = measure(stringify(spec), tok)
            out.append(Segment(Category.TOOL_SCHEMA, t, c, name=name))

        messages = request.get("messages") or []
        last_user = _last_user_index(messages)

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "")
            text = _content_text(msg.get("content"))

            if role == "assistant" and msg.get("tool_calls"):
                text += stringify(msg["tool_calls"])

            t, c = measure(text, tok)
            if t == 0 and c == 0:
                continue

            if role == "system" or role == "developer":
                out.append(Segment(Category.SYSTEM, t, c, name=role, index=i))
            elif role == "tool":
                out.append(
                    Segment(
                        Category.TOOL_RESULT,
                        t,
                        c,
                        name=str(msg.get("name") or msg.get("tool_call_id") or "tool"),
                        index=i,
                    )
                )
            elif role == "assistant":
                out.append(Segment(Category.HISTORY_ASSISTANT, t, c, index=i))
            elif role == "user":
                cat = Category.CURRENT_USER if i == last_user else Category.HISTORY_USER
                out.append(Segment(cat, t, c, index=i))
            else:
                out.append(Segment(Category.OTHER, t, c, name=role, index=i))

        return out


def _last_user_index(messages: list[Any]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, dict) and m.get("role") == "user":
            return i
    return -1


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or stringify(block))
            else:
                parts.append(str(block))
        return "".join(parts)
    return stringify(content)
