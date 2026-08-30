from cli.usage import sum_usage
from llm.types import ModelSource, TextBlock, TokenUsage, create_model_message
from session import Session
from session.events import AssistantMessageEvent


def test_sum_usage_adds_assistant_messages():
    s = Session()
    s.append(
        AssistantMessageEvent(
            turn=1,
            step=1,
            message=create_model_message([TextBlock(text="a")], ModelSource(provider="x", model="m")),
            usage=TokenUsage(input=10, output=2, cache_read=3),
        )
    )
    s.append(
        AssistantMessageEvent(
            turn=1,
            step=2,
            message=create_model_message([TextBlock(text="b")], ModelSource(provider="x", model="m")),
            usage=TokenUsage(input=4, output=1),
        )
    )
    u = sum_usage(s)
    assert u.input == 14
    assert u.output == 3
    assert u.cache_read == 3


def test_sum_usage_skips_missing():
    assert sum_usage(Session()) == TokenUsage()
