from cli.__main__ import parse_args


def test_dash_c_means_latest():
    assert parse_args(["-c"]).resume == "latest"


def test_session_flag():
    assert parse_args(["--session", "abc"]).resume == "abc"


def test_default_no_resume():
    assert parse_args([]).resume is None
