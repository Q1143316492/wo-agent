"""稳定、可机器路由的错误码。

dsh 的思想：策略（重试还是不重试）依据稳定的 ``code`` 字符串，而不是渲染
后的消息文本。适配器发一个终止 ``finish``，其 reason 携带 ``LlmFailure``；
code 让 agent 循环判断这次调用是否值得重试。
"""

from __future__ import annotations


class LlmError(Exception):
    """带稳定、可机器路由 ``code`` 的 harness 错误。"""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


# Provider / 传输失败码（provider 中立、稳定）。
AUTH = "AUTH"  # 凭据不可用
RATE_LIMIT = "RATE_LIMIT"  # 临时限流，退避后可重试
CONTEXT_WINDOW_EXCEEDED = "CONTEXT_WINDOW_EXCEEDED"  # 请求超出上下文窗口，不可重试
QUOTA_EXCEEDED = "QUOTA_EXCEEDED"  # 账户额度耗尽，不可重试
EMPTY_RESPONSE = "EMPTY_RESPONSE"  # 退化成功：结束但没有任何内容
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"  # provider 返回了无法解析的数据
STREAM_CLOSED = "STREAM_CLOSED"  # SSE 在 [DONE] 之前断开
ABORTED = "ABORTED"  # 调用方取消了本次调用

# 循环只对这类失败再请求一次；AUTH / 窗口 / 额度 / 取消不重试。
RETRYABLE_CODES = frozenset({RATE_LIMIT, STREAM_CLOSED, EMPTY_RESPONSE, MALFORMED_RESPONSE})


def is_retryable(code: str) -> bool:
    return code in RETRYABLE_CODES
