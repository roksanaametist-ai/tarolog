from pathlib import Path

p = Path("/opt/targpt/.env")
t = p.read_text(encoding="utf-8")
found = False
out = []
for line in t.splitlines(keepends=True):
    if line.startswith("LLM_PUBLIC_STUB="):
        out.append("LLM_PUBLIC_STUB=0\n")
        found = True
    else:
        out.append(line)
if not found:
    if out and not str(out[-1]).endswith("\n"):
        out.append("\n")
    out.append("LLM_PUBLIC_STUB=0\n")
p.write_text("".join(out), encoding="utf-8")
print("stub_set", "replaced" if found else "appended")
print("verify", next(l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("LLM_PUBLIC_STUB=")))
