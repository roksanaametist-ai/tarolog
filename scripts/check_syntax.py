#!/usr/bin/env python3
"""Проверка синтаксиса main.py перед деплоем."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def main() -> int:
    source = MAIN.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(MAIN))
    except SyntaxError as e:
        print(f"SyntaxError in {MAIN}:{e.lineno}: {e.msg}")
        if e.text:
            print(e.text.rstrip())
        return 1
    print(f"OK: {MAIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
