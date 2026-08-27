"""压缩引擎：日志 replace、阈值、busy 锁。"""

from llm.types import TextBlock, create_user_message
from session import Session, JsonlSessionStore
from session.events import CompactionStart, UserMessageEvent
from compaction.engine import BasicCompaction, CompactionOptions, unmatched_compaction_start
from compaction.protocol import CompactionBusy, is_compact_checkpoint_source
from compaction.summarizer import SUMMARY_OPEN_TAG

CHUNK = "abcdefghij" * 40  # 400 字符，保证摘要装帧仍小于被遮蔽内容


class FakeSummarizer:
    def __init__(self, text="EARLIER WORK"):
        self.text = text
        self.calls = 0
        self.last_messages = None

    async def summarize(self, messages, signal=None):
        self.calls += 1
        self.last_messages = list(messages)
        return self.text


def _user(text):
    return create_user_message([TextBlock(text=text)])


def _fill(session, n, text="abcdefghij"):
    for _ in range(n):
        session.append(UserMessageEvent(message=_user(text)))


async def test_compact_now_replaces_head_keeps_tail():
    session = Session()
    _fill(session, 5, CHUNK)
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(threshold_chars=1000, retain_chars=900))
    result = await engine.compact_now(session)
    assert result is not None
    texts = [m.content[0].text for m in session.derive_messages()]
    assert any(SUMMARY_OPEN_TAG in t for t in texts)
    assert is_compact_checkpoint_source(session.derive_messages()[0].source)
    # 尾部原样保留（至少一条原始 user 还在）
    assert texts[-1] == CHUNK
    # 日志 ev 数增加了 start/summary/replace/end，旧消息还在
    assert any(e.event.type == "compaction/start" for e in session.events)
    assert any(e.event.type == "compaction/end" and e.event.error is None for e in session.events)
    assert sum(1 for e in session.events if e.event.type == "user/message") > len(texts)


async def test_pressure_below_threshold_is_noop():
    session = Session()
    _fill(session, 2, "hi")
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(threshold_chars=10_000, retain_chars=1))
    assert await engine.compact_if_needed(session, trigger="pressure") is None
    assert [m.content[0].text for m in session.derive_messages()] == ["hi", "hi"]


async def test_overflow_skips_threshold():
    session = Session()
    _fill(session, 5, CHUNK)
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(threshold_chars=10_000, retain_chars=900))
    result = await engine.compact_if_needed(session, trigger="overflow")
    assert result is not None
    assert SUMMARY_OPEN_TAG in session.derive_messages()[0].content[0].text


async def test_busy_lock_blocks_compact_now():
    session = Session()
    _fill(session, 4, CHUNK)
    session.append(CompactionStart(compaction_id="open"))
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(retain_chars=500))
    try:
        await engine.compact_now(session)
        assert False, "expected CompactionBusy"
    except CompactionBusy:
        pass
    assert unmatched_compaction_start(session) is not None


async def test_failed_summary_closes_lock_without_replace():
    class Boom:
        async def summarize(self, messages, signal=None):
            raise RuntimeError("nope")

    session = Session()
    _fill(session, 5, CHUNK)
    engine = BasicCompaction(Boom(), CompactionOptions(retain_chars=900))
    assert await engine.compact_if_needed(session, trigger="overflow") is None
    assert any(e.event.type == "compaction/end" and e.event.error for e in session.events)
    assert unmatched_compaction_start(session) is None
    assert all(m.content[0].text == CHUNK for m in session.derive_messages())


async def test_jsonl_roundtrip_after_compact(tmp_path):
    session = Session()
    _fill(session, 5, CHUNK)
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(retain_chars=900))
    await engine.compact_now(session)
    store = JsonlSessionStore(tmp_path)
    store.save(session)
    loaded = store.load(session.id)
    assert loaded.derive_messages() == session.derive_messages()
    assert loaded.surface_seqs() == session.surface_seqs()
