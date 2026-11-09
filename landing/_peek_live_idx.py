from pathlib import Path

t = Path("/root/tarolog/landing/templates/index.html").read_text(encoding="utf-8")
for needle in ("id=\"contacts\"", "id='contacts'", "contacts-title", "{% include", "show_lead"):
    print("needle", needle, t.find(needle))
i = t.find("id=\"contacts\"")
if i < 0:
    i = t.find("contacts-title")
print("---around contacts---")
print(t[max(0, i - 400) : i + 2200])
print("---siteapp legal---")
s = Path("/root/tarolog/landing/SiteApp.py").read_text(encoding="utf-8")
print("register_legal", "register_legal" in s, "legal_pages" in s)
print("oferta exists", Path("/root/tarolog/landing/templates/oferta.html").exists())
print("privacy exists", Path("/root/tarolog/landing/templates/privacy.html").exists())
print("lead include", Path("/root/tarolog/landing/templates/_lead_form.html").exists())
