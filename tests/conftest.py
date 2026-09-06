import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def openai_session_path() -> str:
    return str(FIXTURES / "openai_session.jsonl")


@pytest.fixture
def anthropic_request() -> dict:
    return json.loads((FIXTURES / "anthropic_turn.json").read_text())


@pytest.fixture
def anthropic_path() -> str:
    return str(FIXTURES / "anthropic_turn.jsonl")


@pytest.fixture
def thrash_path() -> str:
    return str(FIXTURES / "cache_thrash.jsonl")
