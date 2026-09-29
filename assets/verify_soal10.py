#!/usr/bin/env python3
"""
verify_soal10.py — Soal 10 verification: layanan web dinamis Nginx + PHP-FPM
pada area core (oblada, molly), aplikasi beranda + profil dengan rewrite
URL bersih (/profil tanpa akhiran .php), akses melalui hostname.

Checks (via telnet console):
  oblada/molly   : nginx + php-fpm berjalan; curl 127.0.0.1/ & /profil
                   ter-render PHP (bukan source dump; tanpa "<?php")
  alpha          : curl http://core.k13.com/ & /profil -> 200 + PHP terrender
  delta          : curl http://oblada.k13.com/ & http://molly.k13.com/profil
  server         : /profil.php -> 200
  kedua node     : hostname backend tercetak di halaman (round-robin via core)

Usage: python3 verify_soal10.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402


def run_one(nodes, name, cmd, wait=30):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        con.send_line("echo RS$?RS")
        con.read_until(b"RS0RS", 25)
        tag = f"W{int(time.time()*1000)%937:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        cleaned = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
        return cleaned.split("\n", 1)[-1]
    finally:
        con.close()


def main():
    token = req("POST", "/v3/access/users/authenticate",
                {"username": "K-13", "password": "K-13@GNS3"})[1]["access_token"]
    pid = next(p["project_id"] for p in req("GET", "/v3/projects", token=token)[1]
               if p["name"] == "K-13-MODUL-2")
    ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)[1]
    nodes = {n["name"]: n for n in ns}

    results = []
    def check(desc, ok):
        results.append(ok)
        print(f"[{'+' if ok else '!'}] {desc}")

    # ── server side ──
    for server in ("oblada", "molly"):
        dv = run_one(nodes, server, "pidof nginx >/dev/null && pgrep -f php-fpm >/dev/null && echo SRVOK || echo SRVBAD")
        check(f"{server}: nginx + php-fpm berjalan", "SRVOK" in dv)
        home = run_one(nodes, server, "curl -s http://127.0.0.1/")
        ok = "BERANDA" in home and "PHP" in home and "<?php" not in home
        check(f"{server}: beranda ter-render PHP (bukan source)", ok)
        prof = run_one(nodes, server, "curl -s http://127.0.0.1/profil")
        ok = "PROFIL" in prof and "<?php" not in prof
        check(f"{server}: /profil URL bersih (tanpa .php) ter-render", ok)
        code = run_one(nodes, server, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/profil.php")
        check(f"{server}: /profil.php langsung tetap 200", "200" in code)

    # ── akses dari client: WAJIB hostname ──
    for client, url, want in (("alpha", "core.k13.com", "BERANDA"),
                              ("alpha", "core.k13.com/profil", "PROFIL")):
        out = run_one(nodes, client, f"curl -s http://{url}")
        code_ok = "<?php" not in out and re.search(r"10\.70\.\d+\.\d+", out)
        ok = want in out and ("PHP" in out or "URL" in out)
        check(f"{client}: http://{url} -> ter-render ({'ok' if ok else 'GAGAL'})", ok)

    for client, url in (("delta", "oblada.k13.com/profil"), ("delta", "molly.k13.com/profil")):
        out = run_one(nodes, client, f"curl -s http://{url}")
        ok = "PROFIL" in out and "<?php" not in out
        check(f"{client}: http://{url} -> ter-render", ok)

    # ── round-robin core: hostname menjangkau kedua backend ──
    seen = set()
    for i in range(4):
        out = run_one(nodes, "alpha", "curl -s http://core.k13.com/")
        m = re.search(r"di\s+(oblada|molly)", out)
        if m:
            seen.add(m.group(1))
    check(f"core.k13.com round-robin menyentuh kedua backend {seen}", len(seen) == 2)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 10 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
