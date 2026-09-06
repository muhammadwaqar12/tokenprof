from tokenprof.cost import cost_usd, price_per_mtok


def test_unknown_model_returns_none():
    # Guessing a price is worse than showing none.
    assert price_per_mtok("mystery-model-9") is None
    assert cost_usd(1_000_000, "mystery-model-9") is None


def test_longest_prefix_wins():
    assert price_per_mtok("gpt-4o-mini-2024-07-18") == 0.15
    assert price_per_mtok("gpt-4o-2024-11-20") == 2.50


def test_explicit_rate_overrides_table():
    assert cost_usd(1_000_000, "gpt-4o", rate_per_mtok=1.0) == 1.0


def test_cost_scales_linearly():
    assert cost_usd(2_000_000, "gpt-4o") == 5.0


def test_empty_model_is_none():
    assert price_per_mtok("") is None
