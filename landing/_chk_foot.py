import urllib.request
h = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8")
for s in ["jelly-foot", "Самозанятая", "oferta", "18", "fonts.css", "lead-form", "site-foot"]:
    print(s, h.find(s))
idx = h.find("Самозанятая")
print("---", repr(h[idx:idx+500]))
idx2 = h.rfind("<footer")
print("footer at", idx2)
print(repr(h[idx2:idx2+1200]))
