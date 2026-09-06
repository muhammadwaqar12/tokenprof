import json

import pytest

from tokenprof.cli import main


def test_analyze_table(capsys, openai_session_path):
    assert main(["analyze", openai_session_path]) == 0
    out = capsys.readouterr().out
    assert "3 turns" in out
    assert "fixed overhead across the session" in out


def test_analyze_json_is_valid(capsys, openai_session_path):
    assert main(["analyze", openai_session_path, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["turn_count"] == 3
    assert data["summary"]["fixed_overhead_tokens"] > 0


def test_analyze_single_turn(capsys, openai_session_path):
    assert main(["analyze", openai_session_path, "--turn", "0"]) == 0
    out = capsys.readouterr().out
    assert "tool schemas" in out
    assert "bloated_connector" in out


def test_single_turn_file_also_prints_the_breakdown(capsys, anthropic_path):
    assert main(["analyze", anthropic_path]) == 0
    out = capsys.readouterr().out
    assert "tool schemas" in out


def test_out_of_range_turn_is_a_clean_error(openai_session_path):
    with pytest.raises(SystemExit, match="out of range"):
        main(["analyze", openai_session_path, "--turn", "99"])


def test_diff_table(capsys, openai_session_path):
    assert main(["diff", openai_session_path, "--from", "0", "--to", "2"]) == 0
    out = capsys.readouterr().out
    assert "trace_calls" in out
    assert "added" in out


def test_diff_json(capsys, openai_session_path):
    assert main(["diff", openai_session_path, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total"]["change"] > 0


def test_rate_override_shows_cost(capsys, openai_session_path):
    main(["analyze", openai_session_path, "--rate", "3.0"])
    assert "$" in capsys.readouterr().out


def test_undetectable_payload_exits_cleanly(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"prompt": "legacy"}\n')
    with pytest.raises(SystemExit, match="could not detect"):
        main(["analyze", str(p)])
