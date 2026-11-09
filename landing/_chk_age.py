import urllib.request
h = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8")
print("18+" in h, "18" in h)
i = h.find("jelly-foot__legal")
print(repr(h[i:i+800]))
