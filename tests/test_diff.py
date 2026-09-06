from tokenprof.attribute import profile_stream, read_jsonl
from tokenprof.diff import Delta, diff_turns
from tokenprof.types import Category, Segment, Turn


def test_delta_change_and_pct():
    d = Delta("x", 100, 150)
    assert d.change == 50
    assert d.pct == 50.0


def test_delta_pct_is_none_when_baseline_is_zero():
    assert Delta("x", 0, 10).pct is None


def test_diff_flags_growth(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    d = diff_turns(profile.turns[0], profile.turns[-1])
    assert d.grew
    assert d.total.change > 0


def test_diff_surfaces_a_newly_registered_tool(openai_session_path):
    # The fixture adds "trace_calls" on the last turn. A tool appearing
    # mid-session is exactly the kind of silent cost increase this catches.
    profile = profile_stream(read_jsonl(openai_session_path))
    d = diff_turns(profile.turns[0], profile.turns[-1])
    added = {x.key for x in d.tools if x.before == 0 and x.after > 0}
    assert "trace_calls" in added


def test_diff_ignores_unchanged_tools(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    d = diff_turns(profile.turns[0], profile.turns[1])
    assert all(x.change != 0 for x in d.tools)


def test_categories_sorted_by_absolute_change():
    before = Turn(segments=[Segment(Category.SYSTEM, 100, 400)], index=0)
    after = Turn(
        segments=[
            Segment(Category.SYSTEM, 100, 400),
            Segment(Category.TOOL_RESULT, 5000, 20000, name="logs"),
        ],
        index=1,
    )
    d = diff_turns(before, after)
    assert d.categories[0].key == Category.TOOL_RESULT.label


def test_identical_turns_show_no_change():
    t = Turn(segments=[Segment(Category.SYSTEM, 10, 40)])
    d = diff_turns(t, t)
    assert d.total.change == 0
    assert not d.grew
