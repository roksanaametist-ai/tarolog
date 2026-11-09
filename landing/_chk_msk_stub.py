from pathlib import Path

p = Path("/opt/targpt/.env")
print("env_exists", p.exists())
if p.exists():
    t = p.read_text(encoding="utf-8", errors="replace")
    line = next((l for l in t.splitlines() if l.startswith("LLM_PUBLIC_STUB=")), "MISSING")
    print("stub_line", line)

for rel in (
    "/opt/targpt/user_data.json",
    "/opt/targpt/bot_state.sqlite3",
    "/root/tarolog/user_data.json",
    "/root/tarolog/bot_state.sqlite3",
):
    path = Path(rel)
    if path.exists():
        print(rel, "bytes", path.stat().st_size, "mtime", int(path.stat().st_mtime))
    else:
        print(rel, "ABSENT")
