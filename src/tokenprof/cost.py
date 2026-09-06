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


def cost_usd(tokens: int, model: str = "", rate_per_mtok: float | None = None) -> float | None:
    rate = rate_per_mtok if rate_per_mtok is not None else price_per_mtok(model)
    if rate is None:
        return None
    return tokens / 1_000_000 * rate
