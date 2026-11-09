# -*- coding: utf-8 -*-
import urllib.request

html = urllib.request.urlopen("http://127.0.0.1:5002/").read().decode("utf-8", "replace")
print("live 3333", html.count("3 333"), "sums", html.count("price-card__sum"), "tiktok card", "Видеоразбор" in html)
of = urllib.request.urlopen("http://127.0.0.1:5002/oferta").read().decode("utf-8", "replace")
print("oferta 3333", of.count("3 333"), "edition", "17.10.2026" in of)
