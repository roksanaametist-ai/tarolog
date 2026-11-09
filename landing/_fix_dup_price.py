from pathlib import Path

dup = (
    "Предоплата 11 111 ₽ за консультацию. "
    "Дальнейшая работа и расчёты — только по отдельному согласованию объёма. "
    "Дальнейшая работа и расчёты — только по отдельному согласованию объёма."
)
one = (
    "Предоплата 11 111 ₽ за консультацию. "
    "Дальнейшая работа и расчёты — только по отдельному согласованию объёма."
)

for p in (
    Path("/root/tarolog/landing/templates/index.html"),
    Path("/opt/targpt/landing/templates/index.html"),
):
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    n = t.count(dup)
    p.write_text(t.replace(dup, one), encoding="utf-8")
    print(p, n)
