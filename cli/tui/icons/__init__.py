"""启动 icon 目录。加新版本：写 ``vN.py`` 暴露 ``ICON``，再登记到 ``_ICONS``。

切换：``Banner("v2")``，或环境变量 ``WO_AGENT_ICON``。默认 v2。还原大猫：``WO_AGENT_ICON=v1``。
"""

from __future__ import annotations

import os

from cli.tui.icons.spec import Icon
from cli.tui.icons.v1 import ICON as V1
from cli.tui.icons.v2 import ICON as V2

_ICONS: dict[str, Icon] = {
    V1.id: V1,
    V2.id: V2,
}

DEFAULT = V2.id
ENV_KEY = "WO_AGENT_ICON"


def catalog() -> dict[str, Icon]:
    return dict(_ICONS)


def icon_ids() -> tuple[str, ...]:
    return tuple(_ICONS)


def resolve(icon_id: str | None = None) -> Icon:
    chosen = (icon_id or os.environ.get(ENV_KEY) or DEFAULT).strip()
    icon = _ICONS.get(chosen)
    if icon is None:
        known = ", ".join(icon_ids())
        raise ValueError(f"unknown icon {chosen!r}; want one of: {known}")
    return icon
