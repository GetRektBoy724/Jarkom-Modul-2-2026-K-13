#!/usr/bin/env python3
"""
verify_soal9.py — Soal 9 verification: layanan web statis Apache + autoindex
/arsip/ pada area vault (obladi, desmond), akses melalui hostname.

Checks (via telnet console):
  obladi/desmond : apache2 running; curl 127.0.0.1/arsip/ contains all 3 docs
  alpha          : curl http://obladi.k13.com/arsip/ = 200 + doc filenames
                   curl http:// vault.k13.com/arsip/ = 200
  delta          : curl http://desmond.k13.com/arsip/ = 200 + filenames

Usage: python3 verify_soal9.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

DOCS = ["dokumen-1.txt", "dokumen-2.txt", "dokumen-3.txt"]


def run_one(nodes, name, cmd, wait=30):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        con.send_line("echo RS$?RS")
        con.read_until(b"RS0RS", 25)
        tag = f"P{int(time.time()*1000)%937:03d}"
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

    # ── server side: apache hidup, autoindex melayani daftar file ──
    for server in ("obladi", "desmond"):
        out = run_one(nodes, server, "pidof apache2 >/dev/null && echo PIDOK || echo PIDBAD")
        ok = "PIDOK" in out
        check(f"{server}: apache2 berjalan", ok)
        missing = [d for d in DOCS
                   if d not in run_one(nodes, server, "curl -s http://127.0.0.1/arsip/")]
        check(f"{server}: autoindex /arsip/ menampilkan 3 dokumen"
              + (f" (hilang: {', '.join(missing)})" if missing else ""), not missing)

    # ── akses dari client: WAJIB hostname, bukan IP ──
    for client, url in (("alpha", "obladi.k13.com"),
                        ("alpha", "vault.k13.com"),
                        ("delta", "desmond.k13.com")):
        out = run_one(nodes, client,
                      f"curl -s -o /dev/null -w '%{{http_code}}' http://{url}/arsip/")
        code = re.search(r"(\d{3})", out)
        ok = code and code.group(1) == "200"
        check(f"{client}: curl http://{url}/arsip/ -> {code.group(1) if code else '???'}", ok)
        if ok:
            missing = [d for d in DOCS
                       if d not in run_one(nodes, client, f"curl -s http://{url}/arsip/")]
            documents_ok = not missing
            check(f"{client}: isi http://{url}/arsip/ konsisten (3 dokumen)"
                  + (f" (hilang: {', '.join(missing)})" if missing else ""), documents_ok)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 9 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
