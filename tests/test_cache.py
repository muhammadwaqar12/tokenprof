from tokenprof.attribute import profile_request, profile_stream, read_jsonl
from tokenprof.cache import analyze, prefix_break
from tokenprof.types import Category, Profile, Segment, Turn


def _turn(digests, index=0, tokens=10):
    return Turn(
        segments=[Segment(Category.SYSTEM, tokens, tokens * 4, digest=d) for d in digests],
        index=index,
    )


def test_identical_prefix_is_fully_stable():
    b = prefix_break(_turn(["a", "b"], 0), _turn(["a", "b"], 1))
    assert b.stable_segments == 2
    assert b.healthy


def test_appending_keeps_the_prefix_healthy():
    # Growing the conversation is the normal case and must not be flagged.
    b = prefix_break(_turn(["a", "b"], 0), _turn(["a", "b", "c"], 1))
    assert b.healthy
    assert b.stable_segments == 2


def test_change_at_the_front_destroys_the_whole_prefix():
    b = prefix_break(_turn(["X", "b", "c"], 0), _turn(["Y", "b", "c"], 1))
    assert not b.healthy
    assert b.stable_segments == 0
    assert b.stable_tokens == 0


def test_break_names_the_segment_that_changed():
    before = Turn(segments=[Segment(Category.SYSTEM, 5, 20, name="sys", digest="a")])
    after = Turn(segments=[Segment(Category.SYSTEM, 5, 20, name="sys", digest="b")], index=1)
    b = prefix_break(before, after)
    assert b.breaking is not None
    assert b.breaking.name == "sys"


def test_segments_without_digests_never_count_as_stable():
    # A missing digest means unknown, and unknown must not be reported as a
    # cache hit, or the tool overstates savings.
    b = prefix_break(_turn(["", ""], 0), _turn(["", ""], 1))
    assert b.stable_segments == 0


def test_stable_share_of_empty_turn_is_zero():
    assert prefix_break(Turn(), Turn(index=1)).stable_share == 0.0


def test_analyze_needs_two_turns():
    assert analyze(Profile(turns=[_turn(["a"])])).breaks == []


def test_timestamp_in_system_prompt_is_detected_as_thrash(thrash_path):
    profile = profile_stream(read_jsonl(thrash_path))
    report = analyze(profile)
    assert report.thrashing
    # The tool must name the culprit, not merely report a low number.
    assert "system:system" in report.offenders()
    assert report.offenders()["system:system"] == 3


def test_append_only_session_names_no_offender_for_growth(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    report = analyze(profile)
    healthy = [b for b in report.breaks if b.healthy]
    assert healthy, "turn 0 -> 1 only appends and should stay healthy"


def test_registering_a_tool_mid_session_breaks_the_prefix(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    report = analyze(profile)
    assert "tool_schema:trace_calls" in report.offenders()


def test_anthropic_cache_control_marks_the_prefix(anthropic_request):
    turn = profile_request(anthropic_request)
    assert turn.cached_tokens() > 0
    assert turn.cached_tokens() + turn.uncached_tokens() == turn.total_tokens
    # Everything up to and including the last marker is cached, and the
    # tool_result that arrives after it is not.
    assert all(not s.cached for s in turn.segments if s.category is Category.TOOL_RESULT)


def test_no_markers_means_nothing_marked(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    assert analyze(profile).marked_tokens == 0
