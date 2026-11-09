# -*- coding: utf-8 -*-
from pathlib import Path
import py_compile

p = Path("/root/tarolog/analytics/store.py")
t = p.read_text(encoding="utf-8")
old = """            active = int(
                conn.execute(
                    \"\"\"
                    SELECT COUNT(DISTINCT user_id) AS n FROM events
                    WHERE local_date BETWEEN ? AND ? AND user_id IS NOT NULL
                      AND event_name NOT LIKE 'admin_%'
                    \"\"\",
                    (start, end),
                ).fetchone()[\"n\"]
            )"""
new = """            active = int(
                conn.execute(
                    \"\"\"
                    SELECT COUNT(DISTINCT user_id) AS n FROM events
                    WHERE local_date BETWEEN ? AND ? AND user_id IS NOT NULL
                      AND event_name NOT LIKE 'admin_%'
                      AND event_name NOT LIKE 'broadcast_%'
                      AND event_name NOT LIKE 'winback_%'
                      AND event_name NOT LIKE 'tomorrow_push_%'
                    \"\"\",
                    (start, end),
                ).fetchone()[\"n\"]
            )"""
if old not in t:
    raise SystemExit("active block not found")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("patched ok")
