from pathlib import Path
import re

idx = Path("/root/tarolog/landing/templates/index.html")
t = idx.read_text(encoding="utf-8")

t2, n = re.subn(
    r"\n\s*<section\b[^>]*id=\"buyer\"[\s\S]*?</section>\s*",
    "\n",
    t,
    count=1,
)
if n != 1:
    raise SystemExit(f"buyer section count={n}")

for junk in (
    '                        <a href="#buyer">Покупателю</a>\n',
    '                <a href="#buyer">Покупателю</a>\n',
):
    t2 = t2.replace(junk, "")

t2 = re.sub(r"main\.css\?v=\d+", "main.css?v=203", t2, count=1)
idx.write_text(t2, encoding="utf-8")
print("dropped buyer", "buyer id left", t2.count('id="buyer"'), "v203", "v=203" in t2)
