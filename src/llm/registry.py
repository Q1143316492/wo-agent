"""薄 provider 注册表。目前只有一家 provider，保持最小；需要按名选适配器时再扩展。"""

from __future__ import annotations

from .protocol import LLMProvider


class ModelRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> LLMProvider | None:
        return self._providers.get(name)

    def names(self) -> list[str]:
        return list(self._providers)
