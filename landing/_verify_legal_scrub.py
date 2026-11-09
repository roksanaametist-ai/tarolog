# -*- coding: utf-8 -*-
import urllib.request

for u in ("http://127.0.0.1:5002/privacy", "http://127.0.0.1:5002/oferta", "http://127.0.0.1:5002/"):
    t = urllib.request.urlopen(u).read().decode("utf-8", "replace")
    print(
        u,
        "samoz",
        t.lower().count("самозаня"),
        "909",
        t.count("909"),
        "gmail",
        t.count("gmail"),
        "phone_lit",
        t.count("+7"),
    )
