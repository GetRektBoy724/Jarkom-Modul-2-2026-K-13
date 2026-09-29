#!/usr/bin/env python3
"""
verify_soal7.py — Soal 7 verification: A record vault/core (round-robin)
+ CNAME www/static di zona k13.com, ter-resolve konsisten dari dua klien
berbeda.

Checks (via telnet console):
  prab + tedd : dig vault/core (2 IP masing-masing), www -> 10.70.5.2,
                static -> 10.70.4.2
  alpha + delta (dua klien, beda segmen): getent ahostsv4/hosts untuk
                keempat nama — jawaban kedua klien identik

Usage: python3 verify_soal7.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        # a freshly-opened console session replays its boot banner + init log;
        # drain it with a handshake before running the real command
        con.send_line("echo RS$?RS")
        con.read_until(b"RS0RS", 25)
        tag = f"K{int(time.time()*1000)%937:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        cleaned = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
        return cleaned.split("\n", 1)[-1]
    finally:
        con.close()


def stream_ips(out):
    """IP-address tokens only (ignores echoed commands and log text)."""
    return set(re.findall(r"\b10\.70\.\d+\.\d+\b", out))


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

    # ── server-side: kedua server menjawab lengkap ──
    for server, ip in (("prab", "10.70.1.2"), ("tedd", "10.70.1.3")):
        vault_out = run_one(nodes, server, f"dig @10.70.1.{2 if server=='prab' else 3} vault.k13.com A +short")
        ok = "10.70.1.4" in vault_out and "10.70.1.5" in vault_out
        check(f"{server}: vault -> obladi(10.70.1.4) & desmond(10.70.1.5) [round-robin]", ok)
        core_out = run_one(nodes, server, f"dig @10.70.1.{2 if server=='prab' else 3} core.k13.com A +short")
        ok = "10.70.1.6" in core_out and "10.70.1.7" in core_out
        check(f"{server}: core -> oblada(10.70.1.6) & molly(10.70.1.7) [round-robin]", ok)
        www_out = run_one(nodes, server, f"dig @10.70.1.{2 if server=='prab' else 3} www.k13.com A +short")
        ok = "10.70.5.2" in www_out
        check(f"{server}: www (CNAME penny) -> 10.70.5.2", ok)
        st_out = run_one(nodes, server, f"dig @10.70.1.{2 if server=='prab' else 3} static.k13.com A +short")
        ok = "10.70.4.2" in st_out
        check(f"{server}: static (CNAME abbey) -> 10.70.4.2", ok)

    # ── dua klien berbeda: jawaban harus konsisten ──
    def client_ips(client):
        v = stream_ips(run_one(nodes, client, "getent ahostsv4 vault.k13.com"))
        c = stream_ips(run_one(nodes, client, "getent ahostsv4 core.k13.com"))
        w = stream_ips(run_one(nodes, client, "getent hosts www.k13.com"))
        s = stream_ips(run_one(nodes, client, "getent hosts static.k13.com"))
        return {"vault": v, "core": c, "www": w, "static": s}

    a = client_ips("alpha")
    d = client_ips("delta")
    ok = (a["vault"] >= {"10.70.1.4", "10.70.1.5"}
          and a["core"] >= {"10.70.1.6", "10.70.1.7"}
          and "10.70.5.2" in a["www"] and "10.70.4.2" in a["static"])
    check(f"alpha: keempat nama ter-resolve benar {a}", ok)
    ok = (d["vault"] >= {"10.70.1.4", "10.70.1.5"}
          and d["core"] >= {"10.70.1.6", "10.70.1.7"}
          and "10.70.5.2" in d["www"] and "10.70.4.2" in d["static"])
    check(f"delta: keempat nama ter-resolve benar {d}", ok)
    check("jawaban dua klien konsisten",
          a["vault"] == d["vault"] and a["core"] == d["core"]
          and a["www"] == d["www"] and a["static"] == d["static"])

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 7 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
