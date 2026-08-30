from cli.commands import apply_suggestion, dispatch, parse_line, suggest
from cli.commands.registry import CommandRegistry
from cli.commands.types import CommandContext, CommandOutcome, CommandSpec, ParsedCommand


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


def test_register_makes_command_suggestable():
    table = CommandRegistry()
    table.register(
        CommandSpec("model", "列出或切换模型", handler=lambda p, c: CommandOutcome("note", "deepseek"))
    )
    names = [item.name for item in table.suggest("/m")]
    assert names == ["model"]
    out = table.dispatch(ParsedCommand("model", ""), CommandContext())
    assert out.kind == "note"
    assert "deepseek" in out.text


def test_session_commands_are_suggestable():
    names = [item.name for item in _session_table().suggest("/")]
    assert names == ["help", "clear", "quit", "resume", "new", "name"]


def _session_table():
    from cli.commands.builtins import mount_core, mount_session

    table = CommandRegistry()
    mount_core(table)
    mount_session(table)
    return table


def test_resume_without_args_lists(tmp_path):
    from session import JsonlSessionStore, Session

    store = JsonlSessionStore(tmp_path)
    saved = Session()
    saved.title = "alpha"
    store.save(saved)
    ctx = CommandContext(store=store, session=Session())
    out = _session_table().dispatch(ParsedCommand("resume", ""), ctx)
    assert out.kind == "note"
    assert saved.id[:8] in out.text
    assert "alpha" in out.text


def test_resume_prefix_loads(tmp_path):
    from session import JsonlSessionStore, Session

    store = JsonlSessionStore(tmp_path)
    saved = Session()
    store.save(saved)
    ctx = CommandContext(store=store, session=Session())
    out = _session_table().dispatch(ParsedCommand("resume", " " + saved.id[:8]), ctx)
    assert out.kind == "load_session"
    assert out.session_id == saved.id


def test_resume_ambiguous_prefix_does_not_load(tmp_path):
    from session import JsonlSessionStore, Session

    store = JsonlSessionStore(tmp_path)
    a, b = Session(), Session()
    store.save(a)
    store.save(b)
    shared = ""
    for i in range(1, min(len(a.id), len(b.id)) + 1):
        if a.id[:i] == b.id[:i]:
            shared = a.id[:i]
        else:
            break
    if not shared:
        return
    ctx = CommandContext(store=store, session=Session())
    out = _session_table().dispatch(ParsedCommand("resume", " " + shared), ctx)
    if a.id.startswith(shared) and b.id.startswith(shared) and a.id != b.id:
        assert out.kind == "note"
        assert out.session_id == ""


def test_new_returns_new_session(tmp_path):
    from session import JsonlSessionStore, Session

    ctx = CommandContext(store=JsonlSessionStore(tmp_path), session=Session())
    out = _session_table().dispatch(ParsedCommand("new", ""), ctx)
    assert out.kind == "new_session"


def test_name_sets_title():
    from session import Session

    session = Session()
    ctx = CommandContext(session=session, store=None)
    out = _session_table().dispatch(ParsedCommand("name", " 登录页"), ctx)
    assert session.title == "登录页"
    assert out.kind == "note"
