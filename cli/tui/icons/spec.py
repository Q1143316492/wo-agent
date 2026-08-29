"""启动 icon 的对外形状。新版本不管是半格像素还是方块字，都做成这个。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.text import Text


@dataclass(frozen=True)
class Icon:
    id: str
    title: str
    render: Callable[[], Text]
