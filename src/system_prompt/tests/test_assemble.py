"""SystemPromptRegistry：按 order 拼接，空段丢弃，重名拒绝。"""

from system_prompt import PromptSection, SystemPromptRegistry


def test_assemble_orders_and_skips_empty():
    registry = SystemPromptRegistry()
    registry.section(PromptSection(name="b", order=10, text="beta"))
    registry.section(PromptSection(name="a", order=-100, text="alpha"))
    registry.section(PromptSection(name="empty", order=0, text="  "))
    assert registry.assemble() == "alpha\n\nbeta"


def test_callable_text_evaluated_at_assemble():
    registry = SystemPromptRegistry()
    box = {"n": 1}
    registry.section(PromptSection(name="dyn", order=0, text=lambda: f"n={box['n']}"))
    assert registry.assemble() == "n=1"
    box["n"] = 2
    assert registry.assemble() == "n=2"


def test_duplicate_name_raises():
    registry = SystemPromptRegistry()
    registry.section(PromptSection(name="x", order=0, text="a"))
    try:
        registry.section(PromptSection(name="x", order=1, text="b"))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected ValueError")
