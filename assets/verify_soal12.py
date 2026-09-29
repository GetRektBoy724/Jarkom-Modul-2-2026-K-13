#!/usr/bin/env python3
"""
verify_soal12.py — Soal 12 verification: basic auth pada path /admin penny.
  tanpa kredensial  -> 401 (+ WWW-Authenticate: Basic)
  kredensial salah  -> 401
  prabs + password  -> 200 + halaman "Dokumen Rahasia Sindikat"
  /admin layanan lokal penny (lolos dari ProxyPass ke vault)

Usage: python3 verify_soal12.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

AUTH_USER = "prabs"
AUTH_PASS = "pakar_pinter_jadi_goblok"


def run_one(nodes, name, cmd, wait=30):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        con.send_line("echo RS$?RS")
        con.read_until(b"RS0RS", 25)
        tag = f"N{int(time.time()*1000)%937:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        cleaned = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
        return cleaned.split("\n", 1)[-1]
    finally:
        con.close()


def code_of(nodes, src, url, auth=None):
    if auth:
        cmd = f"curl -s -u '{auth}' -o /dev/null -w '%{{http_code}}' {url}"
    else:
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' {url}"
    out = run_one(nodes, src, cmd)
    m = re.search(r"(\d{3})", out)
    return m.group(1) if m else "???"


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

    # akses lokal di penny (source of truth konfigurasi)
    check("penny: tanpa kredensial -> 401", code_of(nodes, "penny", "http://127.0.0.1/admin/") == "401")
    out = run_one(nodes, "penny", "curl -s -I http://127.0.0.1/admin/")
    check("penny: header WWW-Authenticate hadir", "WWW-Authenticate: Basic" in out)

    # dari dua klien berbeda via hostname
    for src, host in (("alpha", "www.k13.com"), ("delta", "penny.k13.com")):
        url = f"http://{host}/admin/"
        c1 = code_of(nodes, src, url)
        check(f"{src}: {url} tanpa kredensial -> {c1}", c1 == "401")
        c2 = code_of(nodes, src, url, f"{AUTH_USER}:{AUTH_PASS}")
        check(f"{src}: dengan kredensial {AUTH_USER} -> {c2}", c2 == "200")
        body = run_one(nodes, src, f"curl -s -u '{AUTH_USER}:{AUTH_PASS}' {url}")
        check(f"{src}: isi halaman rahasia tampil", "Dokumen Rahasia Sindikat" in body)
        c3 = code_of(nodes, src, url, f"{AUTH_USER}:password-salah")
        check(f"{src}: kredensial salah -> 401", c3 == "401")

    # /admin jangan sampai di-proxy ke vault
    body = run_one(nodes, "alpha", f"curl -s -u '{AUTH_USER}:{AUTH_PASS}' http://www.k13.com/admin/")
    check("penny: /admin lokal (bukan konten vault)", "penny" in body)

    # jalur proxy tetap terbuka tanpa auth (regression check soal 11)
    c = code_of(nodes, "alpha", "http://www.k13.com/arsip/")
    check("regresi: proxy vault tetap tanpa auth (200)", c == "200")

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 12 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
