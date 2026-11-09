from pathlib import Path
p = Path("/root/tarolog/landing/templates/index.html")
t = p.read_text(encoding="utf-8")
t = t.replace("css/main.css') }}?v=142", "css/main.css') }}?v=143")
p.write_text(t, encoding="utf-8")
print("результат count", t.count("результат"))
for i, line in enumerate(t.splitlines(), 1):
    if "результат" in line.lower():
        print(i, line.strip()[:160])
