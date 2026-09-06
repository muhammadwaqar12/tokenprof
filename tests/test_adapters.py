import pytest

from ctxprof.adapters import ADAPTERS, detect, get_adapter
from ctxprof.adapters.anthropic_messages import AnthropicMessagesAdapter
from ctxprof.adapters.openai_chat import OpenAIChatAdapter
from ctxprof.tokenizer import HeuristicTokenizer
from ctxprof.types import Category

TOK = HeuristicTokenizer()


def test_detects_anthropic_by_top_level_system():
    req = {"model": "claude-sonnet-4", "system": "hi", "messages": []}
    assert detect(req).name == "anthropic_messages"


def test_detects_anthropic_by_input_schema_without_system():
    req = {"messages": [], "tools": [{"name": "t", "input_schema": {}}]}
    assert detect(req).name == "anthropic_messages"


def test_detects_openai_by_function_wrapped_tools():
    req = {
        "model": "gpt-4o",
        "messages": [],
        "tools": [{"type": "function", "function": {"name": "t"}}],
    }
    assert detect(req).name == "openai_chat"


def test_detects_openai_for_bare_messages():
    assert (
        detect({"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}).name
        == "openai_chat"
    )


def test_detection_is_not_ambiguous_across_adapters():
    # Exactly one adapter should claim any given payload, otherwise ordering
    # in the registry silently decides correctness.
    payloads = [
        {"model": "claude-sonnet-4", "system": "s", "messages": []},
        {"messages": [], "tools": [{"name": "t", "input_schema": {}}]},
        {
            "model": "gpt-4o",
            "messages": [],
            "tools": [{"type": "function", "function": {"name": "t"}}],
        },
    ]
    for p in payloads:
        assert sum(a.matches(p) for a in ADAPTERS) == 1, p


def test_detect_raises_on_unrecognised_payload():
    with pytest.raises(ValueError, match="could not detect"):
        detect({"prompt": "legacy completions"})


def test_get_adapter_error_lists_known_names():
    with pytest.raises(KeyError, match="anthropic_messages"):
        get_adapter("nope")


def test_openai_attributes_each_tool_schema_separately():
    req = {
        "model": "gpt-4o",
        "tools": [
            {"type": "function", "function": {"name": "alpha", "description": "a" * 100}},
            {"type": "function", "function": {"name": "beta", "description": "b" * 400}},
        ],
        "messages": [{"role": "user", "content": "hi"}],
    }
    schemas = OpenAIChatAdapter().segments(req, TOK)
    by_name = {s.name: s.tokens for s in schemas if s.category is Category.TOOL_SCHEMA}
    assert set(by_name) == {"alpha", "beta"}
    assert by_name["beta"] > by_name["alpha"]


def test_openai_marks_only_the_last_user_message_as_current():
    req = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "second"},
        ],
    }
    segs = OpenAIChatAdapter().segments(req, TOK)
    current = [s for s in segs if s.category is Category.CURRENT_USER]
    history = [s for s in segs if s.category is Category.HISTORY_USER]
    assert len(current) == 1 and current[0].index == 2
    assert len(history) == 1 and history[0].index == 0


def test_openai_counts_assistant_tool_calls_not_just_content():
    # content is None here; the tokens live entirely in tool_calls. Missing
    # this would under-report assistant history on every agentic turn.
    req = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"query":"x"}'},
                    }
                ],
            },
        ],
    }
    segs = OpenAIChatAdapter().segments(req, TOK)
    assert [s.category for s in segs] == [Category.HISTORY_ASSISTANT]
    assert segs[0].tokens > 0


def test_openai_tool_role_becomes_tool_result_named_by_tool():
    req = {
        "model": "gpt-4o",
        "messages": [
            {"role": "tool", "tool_call_id": "c1", "name": "search_docs", "content": "x" * 200}
        ],
    }
    seg = OpenAIChatAdapter().segments(req, TOK)[0]
    assert seg.category is Category.TOOL_RESULT
    assert seg.name == "search_docs"


def test_anthropic_splits_system_blocks(anthropic_request):
    segs = AnthropicMessagesAdapter().segments(anthropic_request, TOK)
    system = [s for s in segs if s.category is Category.SYSTEM]
    assert len(system) == 2


def test_anthropic_extracts_tool_result_from_user_content(anthropic_request):
    segs = AnthropicMessagesAdapter().segments(anthropic_request, TOK)
    results = [s for s in segs if s.category is Category.TOOL_RESULT]
    assert len(results) == 1
    assert results[0].name == "tu_1"
    # The log dump must not be misfiled as user input; that is the whole
    # reason tool_result blocks are pulled out of the user message.
    assert results[0].tokens > 100


def test_anthropic_tool_use_block_is_assistant_history(anthropic_request):
    segs = AnthropicMessagesAdapter().segments(anthropic_request, TOK)
    uses = [s for s in segs if s.category is Category.HISTORY_ASSISTANT and s.name == "query_logs"]
    assert len(uses) == 1


def test_anthropic_text_alongside_tool_result_is_current_user(anthropic_request):
    segs = AnthropicMessagesAdapter().segments(anthropic_request, TOK)
    assert any(s.category is Category.CURRENT_USER for s in segs)


def test_empty_content_produces_no_segments():
    req = {"model": "gpt-4o", "messages": [{"role": "user", "content": ""}]}
    assert OpenAIChatAdapter().segments(req, TOK) == []
