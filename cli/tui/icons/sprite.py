"""半格像素：两行格子合成一个 ▀ / ▄。上下同色用 █，避免 Windows 上变成细横条。"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

_MUTED = "#737373"


def render_sprite(
    sprite: str,
    palette: dict[str, str],
    *,
    caption: str = "",
) -> Text:
    rows = [line.rstrip("\n") for line in sprite.strip("\n").splitlines()]
    width = max(len(line) for line in rows)
    rows = [line.ljust(width, ".") for line in rows]
    if len(rows) % 2:
        rows.append("." * width)

    out = Text()
    for y in range(0, len(rows), 2):
        line = Text()
        for x in range(width):
            top = palette.get(rows[y][x])
            bot = palette.get(rows[y + 1][x])
            if top is None and bot is None:
                line.append(" ")
            elif top is None:
                line.append("▄", Style(color=bot))
            elif bot is None:
                line.append("▀", Style(color=top))
            elif top == bot:
                line.append("█", Style(color=top))
            else:
                line.append("▀", Style(color=top, bgcolor=bot))
        out.append(line)
        out.append("\n")
    if caption:
        out.append(caption.center(width), Style(color=_MUTED))
    return out
