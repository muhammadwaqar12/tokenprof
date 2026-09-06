import pytest

from ctxprof.types import Category, Profile, Segment, Turn


def _turn(**kw) -> Turn:
    return Turn(
        segments=[
            Segment(Category.SYSTEM, 100, 400),
            Segment(Category.TOOL_SCHEMA, 500, 2000, name="search"),
            Segment(Category.TOOL_SCHEMA, 300, 1200, name="read"),
            Segment(Category.TOOL_RESULT, 900, 3600, name="search", index=3),
            Segment(Category.CURRENT_USER, 20, 80, index=4),
        ],
        **kw,
    )


def test_totals():
    t = _turn()
    assert t.total_tokens == 1820
    assert t.total_chars == 7280


def test_by_category_aggregates_duplicates():
    assert _turn().by_category()[Category.TOOL_SCHEMA] == 800


def test_by_name_within_category_does_not_mix_categories():
    t = _turn()
    # "search" exists as both a schema and a result. They must not merge,
    # or the tool breakdown blames the schema for its own output.
    assert t.by_name(Category.TOOL_SCHEMA) == {"search": 500, "read": 300}
    assert t.by_name(Category.TOOL_RESULT) == {"search": 900}


def test_fixed_overhead_is_system_plus_schemas_only():
    assert _turn().fixed_overhead_tokens() == 900


def test_top_is_sorted_descending():
    top = _turn().top(2)
    assert [s.tokens for s in top] == [900, 500]


def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        Segment(Category.SYSTEM, -1, 0)


def test_empty_turn_is_safe():
    t = Turn()
    assert t.total_tokens == 0
    assert t.by_category() == {}
    assert t.top() == []


def test_profile_sums_overhead_across_turns():
    p = Profile(turns=[_turn(index=0), _turn(index=1)])
    assert p.total_tokens == 3640
    assert p.fixed_overhead_tokens() == 1800
