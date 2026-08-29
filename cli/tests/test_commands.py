from cli.commands import apply_suggestion, dispatch, parse_line, suggest


def test_parse_clear():
    parsed = parse_line("/clear")
    assert parsed is not None
    assert parsed.name == "clear"
    assert parsed.raw_input == ""


def test_parse_keeps_trailing_input():
    parsed = parse_line("/help extra")
    assert parsed is not None
    assert parsed.name == "help"
    assert parsed.raw_input == " extra"


def test_plain_text_is_not_a_command():
    assert parse_line("hello") is None
    assert parse_line("/Clear") is None


def test_dispatch_quit():
    parsed = parse_line("/quit")
    assert parsed is not None
    assert dispatch(parsed).kind == "quit"


def test_exit_is_unknown():
    parsed = parse_line("/exit")
    assert parsed is not None
    assert dispatch(parsed).kind == "unknown"


def test_dispatch_unknown():
    parsed = parse_line("/compact")
    assert parsed is not None
    outcome = dispatch(parsed)
    assert outcome.kind == "unknown"
    assert "help" in outcome.text


def test_dispatch_help_lists_clear():
    parsed = parse_line("/help")
    assert parsed is not None
    text = dispatch(parsed).text
    assert "/clear" in text
    assert "/quit" in text
    assert "/exit" not in text


def test_suggest_lists_after_slash():
    names = [item.name for item in suggest("/")]
    assert names == ["help", "clear", "quit"]


def test_suggest_filters_prefix():
    names = [item.name for item in suggest("/c")]
    assert names == ["clear"]
    assert suggest("hello") == ()
    assert suggest("/help ") == ()


def test_apply_suggestion_adds_slash_and_space():
    assert apply_suggestion("clear") == "/clear "
