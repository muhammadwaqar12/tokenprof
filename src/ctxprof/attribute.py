"""Turn a raw request payload into a Turn."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from ctxprof.adapters import Adapter, detect, get_adapter
from ctxprof.tokenizer import Tokenizer, get_tokenizer
from ctxprof.types import Profile, Turn


def profile_request(
    request: dict[str, Any],
    *,
    provider: str | None = None,
    tokenizer: Tokenizer | None = None,
    index: int = 0,
) -> Turn:
    """Profile a single request payload."""
    adapter: Adapter = get_adapter(provider) if provider else detect(request)
    model = adapter.model_of(request)
    tok = tokenizer or get_tokenizer(model)
    return Turn(
        segments=adapter.segments(request, tok),
        model=model,
        provider=adapter.name,
        index=index,
        tokenizer=tok.name,
    )


def profile_stream(
    records: Iterable[dict[str, Any]],
    *,
    provider: str | None = None,
    tokenizer: Tokenizer | None = None,
) -> Profile:
    """Profile a sequence of records into one Profile.

    The tokenizer is resolved once from the first record and reused, because
    building a tiktoken encoding per turn dominates runtime on long sessions.
    """
    profile = Profile()
    tok = tokenizer
    for i, rec in enumerate(records):
        request = unwrap(rec)
        if tok is None:
            adapter = get_adapter(provider) if provider else detect(request)
            tok = get_tokenizer(adapter.model_of(request))
        profile.turns.append(profile_request(request, provider=provider, tokenizer=tok, index=i))
    return profile


def unwrap(record: dict[str, Any]) -> dict[str, Any]:
    """Accept either a bare request payload or a wrapper around one.

    Recorders tend to store {"request": {...}, "ts": ...}. Both shapes are
    accepted so nobody has to reshape their logs before getting an answer.
    """
    for key in ("request", "body", "payload", "kwargs"):
        inner = record.get(key)
        if isinstance(inner, dict) and "messages" in inner:
            return inner
    return record


def read_jsonl(path: str) -> Iterator[dict[str, Any]]:
    """Read a .jsonl file, skipping blank lines.

    A malformed line raises with its line number rather than being dropped
    silently, because a profile that quietly ignored half your session is
    worse than one that refuses to run.
    """
    import sys

    handle = sys.stdin if path == "-" else open(path, encoding="utf-8")
    try:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{lineno}: expected a JSON object")
            yield obj
    finally:
        if handle is not sys.stdin:
            handle.close()
