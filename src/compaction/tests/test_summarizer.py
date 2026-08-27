"""LlmSummarizer：直接 stream，不走 agent 循环。"""

from compaction.summarizer import LlmSummarizer
from llm.types import BlockStart, FinishChunk, FinishReason, TextBlock, TextDelta, create_user_message


class ScriptedProvider:
    def __init__(self, chunks):
        self.chunks = chunks
        self.last_request = None

    async def stream(self, request, signal=None):
        self.last_request = request
        for chunk in self.chunks:
            yield chunk


async def test_summarizer_returns_text_and_appends_instruction():
    provider = ScriptedProvider(
        [
            BlockStart(index=0, block_type="text"),
            TextDelta(index=0, text="## Next Step\n- continue"),
            FinishChunk(reason=FinishReason(kind="stop")),
        ]
    )
    summarizer = LlmSummarizer(provider, provider_name="fake", model="m")
    history = [create_user_message([TextBlock(text="hello")])]
    text = await summarizer.summarize(history)
    assert "continue" in text
    assert provider.last_request is not None
    assert len(provider.last_request.messages) == 2
    assert provider.last_request.messages[-1].source.plugin == "compaction"
    assert provider.last_request.tools == ()
