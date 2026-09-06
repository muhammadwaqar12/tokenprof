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


def test_cache_split_uses_provider_multiplier():
    from tokenprof.cost import cost_split

    a = cost_split(1_000_000, 0, "claude-sonnet-4", "anthropic_messages")
    o = cost_split(1_000_000, 0, "gpt-4o", "openai_chat")
    assert a is not None and o is not None
    # Anthropic reads cache at 10%, OpenAI at 50%. Blending them into one
    # number is what makes a cost report wrong.
    assert round(a[0], 4) == round(3.00 * 0.10, 4)
    assert round(o[0], 4) == round(2.50 * 0.50, 4)


def test_cache_split_is_none_for_unknown_model():
    from tokenprof.cost import cost_split

    assert cost_split(100, 100, "mystery", "openai_chat") is None


def test_unknown_provider_gets_no_discount():
    from tokenprof.cost import cache_read_multiplier

    assert cache_read_multiplier("something_else") == 1.0
