import json

import pytest

from tokenprof.attribute import profile_request, profile_stream, read_jsonl, unwrap
from tokenprof.types import Category


def test_unwrap_finds_nested_request():
    req = {"messages": [], "model": "gpt-4o"}
    assert unwrap({"ts": 1, "request": req}) is req


def test_unwrap_passes_through_bare_payload():
    req = {"messages": [], "model": "gpt-4o"}
    assert unwrap(req) is req


def test_read_jsonl_reports_line_number_on_bad_json(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"messages": []}\nnot json\n')
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        list(read_jsonl(str(p)))


def test_read_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "ok.jsonl"
    p.write_text('{"messages":[],"model":"gpt-4o"}\n\n\n{"messages":[],"model":"gpt-4o"}\n')
    assert len(list(read_jsonl(str(p)))) == 2


def test_read_jsonl_rejects_non_object_line(tmp_path):
    p = tmp_path / "arr.jsonl"
    p.write_text("[1,2,3]\n")
    with pytest.raises(ValueError, match="expected a JSON object"):
        list(read_jsonl(str(p)))


def test_profile_request_records_provenance(anthropic_request):
    turn = profile_request(anthropic_request)
    assert turn.provider == "anthropic_messages"
    assert turn.model.startswith("claude")
    assert turn.tokenizer  # every profile states how it counted


def test_profile_stream_indexes_turns(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    assert [t.index for t in profile.turns] == [0, 1, 2]


def test_context_grows_across_the_session(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    totals = [t.total_tokens for t in profile.turns]
    assert totals == sorted(totals)
    assert totals[-1] > totals[0]


def test_tool_schema_overhead_is_present_on_every_turn(openai_session_path):
    profile = profile_stream(read_jsonl(openai_session_path))
    for turn in profile.turns:
        assert turn.by_category()[Category.TOOL_SCHEMA] > 0


def test_bloated_tool_dominates_the_schema_budget(openai_session_path):
    # The fixture registers one deliberately verbose auto-generated tool.
    # Naming the worst offender is the point of the per-tool breakdown.
    profile = profile_stream(read_jsonl(openai_session_path))
    tools = profile.turns[0].by_name(Category.TOOL_SCHEMA)
    worst = max(tools, key=lambda k: tools[k])
    assert worst == "bloated_connector"
    assert tools[worst] > sum(v for k, v in tools.items() if k != worst)


def test_forcing_the_wrong_provider_still_parses(openai_session_path):
    # Detection can be overridden; it should not crash, since users will
    # reach for --provider precisely when detection went wrong.
    profile = profile_stream(read_jsonl(openai_session_path), provider="openai_chat")
    assert profile.turns[0].provider == "openai_chat"


def test_segment_totals_equal_turn_total(anthropic_request):
    turn = profile_request(anthropic_request)
    assert sum(s.tokens for s in turn.segments) == turn.total_tokens


def test_stdin_is_supported(monkeypatch, anthropic_request):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(anthropic_request) + "\n"))
    assert len(list(read_jsonl("-"))) == 1
