from pathlib import Path

p = Path("/root/tarolog/.env")
print("env_exists", p.exists())
if not p.exists():
    raise SystemExit(0)
t = p.read_text(encoding="utf-8", errors="replace")
line = next((l for l in t.splitlines() if l.startswith("LLM_PUBLIC_STUB=")), "MISSING")
print("stub_line", line)
