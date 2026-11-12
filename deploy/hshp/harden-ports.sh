#!/bin/bash
# Close miniapp black-hole ports; keep https://.../cards and /yesno working.
set -euo pipefail

echo "==> patch miniapp SiteApp.py (localhost + no debug)"
python3 <<'PY'
from pathlib import Path

files = {
    Path("/root/tarolog/sitetargpt-master/SiteApp.py"): 5000,
    Path("/root/tarolog/sitetargpt2-master/SiteApp.py"): 5001,
}
for path, port in files.items():
    new = f"""from flask import Flask, render_template

app = Flask(__name__, template_folder='.')


@app.route("/")
def web():
    return render_template('index.html')


if __name__ == "__main__":
    # Only nginx on this host should reach the app. Users use https://.../cards|/yesno.
    app.run(debug=False, host="127.0.0.1", port={port})
"""
    path.write_text(new, encoding="utf-8")
    print("wrote", path)
PY

echo "==> restart miniapps"
systemctl restart sitetargpt sitetargpt2
sleep 2
systemctl is-active sitetargpt sitetargpt2
ss -tlnp | grep -E ':5000|:5001|:5002|:443|:80|:22' || true

echo "==> install+enable ufw"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
echo y | ufw --force enable
ufw status verbose

echo "==> journal limit"
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/size.conf <<EOF
[Journal]
SystemMaxUse=100M
RuntimeMaxUse=50M
EOF
systemctl restart systemd-journald || true

echo "==> local checks"
curl -sf -o /dev/null -w "lo5000 %{http_code}\n" http://127.0.0.1:5000/ || echo "lo5000 FAIL"
curl -sf -o /dev/null -w "lo5001 %{http_code}\n" http://127.0.0.1:5001/ || echo "lo5001 FAIL"
curl -sf -o /dev/null -w "cards %{http_code}\n" https://followthefrensy.ru/cards || echo "cards FAIL"
curl -sf -o /dev/null -w "yesno %{http_code}\n" https://followthefrensy.ru/yesno || echo "yesno FAIL"
curl -sf -o /dev/null -w "site %{http_code}\n" https://followthefrensy.ru/ || echo "site FAIL"
df -h /
echo "DONE"
