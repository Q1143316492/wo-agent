"""is_retryable 只认稳定 code，不解析消息文本。"""

from llm.errors import AUTH, CONTEXT_WINDOW_EXCEEDED, QUOTA_EXCEEDED, RATE_LIMIT, STREAM_CLOSED, is_retryable


def test_retryable_and_not():
    assert is_retryable(RATE_LIMIT)
    assert is_retryable(STREAM_CLOSED)
    assert not is_retryable(AUTH)
    assert not is_retryable(QUOTA_EXCEEDED)
    assert not is_retryable(CONTEXT_WINDOW_EXCEEDED)
    assert not is_retryable("UNKNOWN")
