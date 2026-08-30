"""``python -m cli``：装好 Textual 后进对话循环。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
# 未 pip install -e 时也能 import src/；``python cli/__main__.py`` 时也能 import cli。
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wo-agent")
    parser.add_argument("-c", action="store_const", const="latest", dest="resume", help="续最近一次会话")
    parser.add_argument("--session", dest="resume", metavar="ID", help="按会话 id 续")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        from textual.app import App  # noqa: F401
    except ImportError:
        print("pip install -e \".[cli]\"", file=sys.stderr)
        raise SystemExit(1) from None

    from cli.boot import api_key

    if not api_key():
        print("set UTAGENT_API_KEY or DEEPSEEK_API_KEY", file=sys.stderr)
        raise SystemExit(1)

    from cli.tui.app import WoCli

    WoCli(resume=args.resume).run()


if __name__ == "__main__":
    main()
