"""Token counting.

Exact counts need the provider's own tokenizer, which is not always available
and is never available offline for every model. So this module is explicit
about which counter produced a number, and every report says so. A profile
built on a heuristic is still useful for comparing segments against each
other, and misleading if you treat it as a budget.
"""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    name: str

    def count(self, text: str) -> int: ...


class HeuristicTokenizer:
    """chars / 4, the universal fallback.

    Runs low on code and on non-Latin scripts. Good enough to rank segments,
    not good enough to size a context budget.
    """

    name = "heuristic(chars/4)"
    divisor = 4

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, round(len(text) / self.divisor))


class TiktokenTokenizer:
    """Exact counts for OpenAI models, when tiktoken is installed."""

    def __init__(self, model: str = "gpt-4o") -> None:
        import tiktoken  # imported lazily so the package has no hard dependency

        try:
            self._enc = tiktoken.encoding_for_model(model)
            self.name = f"tiktoken({model})"
        except KeyError:
            self._enc = tiktoken.get_encoding("o200k_base")
            self.name = "tiktoken(o200k_base)"

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._enc.encode(text, disallowed_special=()))


def get_tokenizer(model: str = "", prefer_exact: bool = True) -> Tokenizer:
    """Best available tokenizer for a model.

    Falls back to the heuristic rather than raising, because a profile with a
    stated approximation beats no profile at all.
    """
    if prefer_exact and _looks_openai(model):
        try:
            return TiktokenTokenizer(model or "gpt-4o")
        except Exception:
            pass
    return HeuristicTokenizer()


def _looks_openai(model: str) -> bool:
    m = model.lower()
    return m.startswith(("gpt-", "o1", "o3", "o4", "text-", "chatgpt"))
