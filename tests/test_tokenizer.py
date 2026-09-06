from tokenprof.tokenizer import HeuristicTokenizer, get_tokenizer


def test_empty_string_is_zero():
    assert HeuristicTokenizer().count("") == 0


def test_short_string_is_at_least_one():
    # A non-empty string costing zero tokens would let real content vanish
    # from a profile, which is worse than being slightly wrong.
    assert HeuristicTokenizer().count("a") == 1


def test_counts_scale_with_length():
    tok = HeuristicTokenizer()
    assert tok.count("x" * 400) > tok.count("x" * 40)


def test_always_returns_a_tokenizer():
    # Never raise on an unknown model. A stated approximation beats refusing.
    assert get_tokenizer("some-model-nobody-has-heard-of").count("hello") > 0
    assert get_tokenizer("").name


def test_tokenizer_reports_its_name():
    assert "heuristic" in HeuristicTokenizer().name
