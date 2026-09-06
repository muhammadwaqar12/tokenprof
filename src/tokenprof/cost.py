"""Input-token pricing.

Deliberately tiny and deliberately overridable. Prices move faster than any
package can track, so the table is a convenience and the CLI takes an
explicit rate. A wrong price is worse than no price, so an unknown model
returns None rather than guessing.
"""

from __future__ import annotations

#: USD per 1M input tokens. Non-cached, standard tier.
PRICES_PER_MTOK: dict[str, float] = {
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "gpt-4.1": 2.00,
    "gpt-4.1-mini": 0.40,
    "o3": 2.00,
    "claude-3-5-haiku": 0.80,
    "claude-3-5-sonnet": 3.00,
    "claude-3-7-sonnet": 3.00,
    "claude-sonnet-4": 3.00,
    "claude-opus-4": 15.00,
}


def price_per_mtok(model: str) -> float | None:
    """Look up a price by longest matching prefix, or None if unknown."""
    if not model:
        return None
    m = model.lower()
    best: tuple[int, float] | None = None
    for key, price in PRICES_PER_MTOK.items():
        if m.startswith(key) and (best is None or len(key) > best[0]):
            best = (len(key), price)
    return best[1] if best else None


#: What a cache *read* costs relative to a fresh input token. Anthropic bills
#: cache reads at 10% of base; OpenAI's automatic caching is 50%. Both charge
#: full price the first time, and Anthropic charges 1.25x to write.
CACHE_READ_MULTIPLIER = {
    "anthropic_messages": 0.10,
    "openai_chat": 0.50,
}


def cache_read_multiplier(provider: str) -> float:
    return CACHE_READ_MULTIPLIER.get(provider, 1.0)


def cost_split(
    cached_tokens: int,
    uncached_tokens: int,
    model: str = "",
    provider: str = "",
    rate_per_mtok: float | None = None,
) -> tuple[float, float] | None:
    """Return (cached_cost, uncached_cost), or None if the price is unknown.

    Reporting one blended number would overstate the cost of exactly the
    segments people cache, which are the system prompt and the tool schemas.
    """
    rate = rate_per_mtok if rate_per_mtok is not None else price_per_mtok(model)
    if rate is None:
        return None
    m = cache_read_multiplier(provider)
    return (cached_tokens / 1_000_000 * rate * m, uncached_tokens / 1_000_000 * rate)


def cost_usd(tokens: int, model: str = "", rate_per_mtok: float | None = None) -> float | None:
    rate = rate_per_mtok if rate_per_mtok is not None else price_per_mtok(model)
    if rate is None:
        return None
    return tokens / 1_000_000 * rate
