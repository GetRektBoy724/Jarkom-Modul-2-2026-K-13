#!/usr/bin/env python3
"""
verify_soal11.py — Soal 11 verification: reverse proxy kedua gerbang.
  penny (Apache)  -> balancer vault (obladi 10.70.1.4 + desmond 10.70.1.5)
  abbey (Nginx)   -> upstream core  (oblada 10.70.1.6 + molly 10.70.1.7)
Header Host + X-Real-IP diteruskan; distribusi lalu lintas terbukti dari
pergantian backend yang muncul antar request.

Usage: python3 verify_soal11.py
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
        tag = f"L{int(time.time()*1000)%937:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        cleaned = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
        return cleaned.split("\n", 1)[-1]
    finally:
        con.close()


def backends_seen(nodes, src, url, pattern, hits=6):
    seen = set()
    for _ in range(hits):
        out = run_one(nodes, src, f"curl -s {url}")
        seen.update(re.findall(pattern, out))
    return seen


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

    # ── server side: kedua gerbang hidup ──
    out = run_one(nodes, "penny", "pidof apache2 >/dev/null && echo POK || echo PBAD")
    check("penny: apache2 (reverse proxy) berjalan", "POK" in out)
    out = run_one(nodes, "abbey", "pidof nginx >/dev/null && echo AOK || echo ABAD")
    check("abbey: nginx (reverse proxy) berjalan", "AOK" in out)

    # ── distribusi: backend berganti antar request ──
    seen = backends_seen(nodes, "penny", "http://127.0.0.1/arsip/",
                         r"backend-(obladi|desmond)\.txt")
    check(f"penny (lokal): balancer vault menyentuh kedua backend {sorted(seen)}",
          seen == {"obladi", "desmond"})

    seen = backends_seen(nodes, "abbey", "http://127.0.0.1/",
                         r"di (oblada|molly)")
    check(f"abbey (lokal): upstream core menyentuh kedua backend {sorted(seen)}",
          seen == {"oblada", "molly"})

    # ── dari klien alpha (10.70.2.2) via hostname kanonik ──
    seen = backends_seen(nodes, "alpha", "http://www.k13.com/arsip/",
                         r"backend-(obladi|desmond)\.txt")
    check(f"alpha: www.k13.com/arsip/ menyentuh kedua vault {sorted(seen)}",
          seen == {"obladi", "desmond"})

    seen = backends_seen(nodes, "alpha", "http://static.k13.com/",
                         r"di (oblada|molly)")
    check(f"alpha: static.k13.com/ menyentuh kedua core {sorted(seen)}",
          seen == {"oblada", "molly"})

    out = run_one(nodes, "alpha", "curl -s http://static.k13.com/")
    check("alpha: X-Real-IP pengunjung asli diteruskan (10.70.2.2 terlihat di backend)",
          "X-Real-IP: 10.70.2.2" in out)
    check("alpha: header Host asli diteruskan (Host: static.k13.com terlihat)",
          "Host: static.k13.com" in out)

    # ── dari klien delta (10.70.3.2) ──
    out = run_one(nodes, "delta", "curl -s http://static.k13.com/")
    check("delta: X-Real-IP pengunjung asli diteruskan (10.70.3.2 terlihat di backend)",
          "X-Real-IP: 10.70.3.2" in out)
    out = run_one(nodes, "delta", "curl -s -o /dev/null -w '%{http_code}' http://www.k13.com/arsip/")
    check("delta: www.k13.com/arsip/ via proxy -> 200", "200" in out)

    # ── kontras: akses langsung ke backend (tanpa gerbang) tidak membawa header ──
    out = run_one(nodes, "delta", "curl -s http://oblada.k13.com/")
    check("kontras: akses langsung ke oblada menampilkan X-Real-IP: - "
          "(header hanya hadir via gerbang)",
          "X-Real-IP: -" in out and "Host: oblada.k13.com" in out)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 11 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
