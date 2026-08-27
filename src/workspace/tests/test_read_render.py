"""read 窗口与包络。"""

from workspace.read_render import build_window, format_read_output, split_lines


def test_split_lines_keeps_tabs_and_strips_cr():
    assert split_lines("a\tb\r\nc") == ["a\tb", "c"]


def test_split_lines_empty():
    assert split_lines("") == []


def test_split_lines_no_trailing_newline():
    assert split_lines("only") == ["only"]


def test_window_line_numbers_and_limit():
    text = "a\nb\nc\n"
    window = build_window(text, "n.txt", offset=2, limit=1)
    assert window.total_lines == 3
    assert window.lines[0].number == 2
    assert window.lines[0].text == "b"


def test_format_includes_line_numbers_and_keeps_indent():
    window = build_window("    x = 1\n", "a.py", offset=1, limit=10)
    body = format_read_output("a.py", window)
    assert "<path>a.py</path>" in body
    assert "1:     x = 1" in body
    assert "End of file" in body


def test_offset_past_eof():
    import pytest
    from workspace.errors import WorkspaceError

    with pytest.raises(WorkspaceError) as caught:
        build_window("a\n", "a.txt", offset=3, limit=10)
    assert caught.value.code == "OFFSET_OUT_OF_RANGE"


def test_empty_file_offset_one():
    window = build_window("", "a.txt", offset=1, limit=10)
    assert window.total_lines == 0
    assert window.lines == ()
    assert "total 0 lines" in format_read_output("a.txt", window)
