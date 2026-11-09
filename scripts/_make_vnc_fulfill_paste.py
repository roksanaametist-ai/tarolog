import base64
import pathlib

src = pathlib.Path(__file__).with_name("_vnc_fulfill_pending.py")
out = pathlib.Path(__file__).with_name("_vnc_fulfill_onepaste.sh")
b64 = base64.b64encode(src.read_bytes()).decode("ascii")
chunks = "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))
script = f"""base64 -d <<'B64' > /tmp/_vnc_fulfill_pending.py
{chunks}
B64
cd /root/tarolog
set -a
. ./.env
set +a
export BOT_DATA_DIR=/root/tarolog
export LANDING_DATA_DIR=/root/tarolog
/root/tarolog/venv/bin/python /tmp/_vnc_fulfill_pending.py
"""
out.write_text(script, encoding="utf-8", newline="\n")
print("wrote", out, out.stat().st_size)
