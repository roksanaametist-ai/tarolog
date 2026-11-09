from pathlib import Path

text = Path("/root/tarolog/bot_core/__init__.py").read_text(encoding="utf-8")
print("FILE BEGIN")
print(text)
print("FILE END size", len(text))
try:
    import bot_core
    print("module file", bot_core.__file__)
    print("dir", [x for x in dir(bot_core) if not x.startswith("_")])
except Exception as e:
    import traceback
    traceback.print_exc()
