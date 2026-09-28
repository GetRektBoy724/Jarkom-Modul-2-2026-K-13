#!/usr/bin/env python3
"""
verify_soal5.py — Soal 5 verification: hostname system-wide di semua node
+ domain per-node (rootkit.k13.com ... molly.k13.com, kecuali prab/tedd yang
sudah punya A record sejak soal 4).

Checks (via telnet console):
  14 nodes : `hostname` dan /etc/hostname = nama node
  prab     : dig 12 nama per-node baru -> IP yang diharapkan
  tedd     : sama (zona hasil transfer)
  delta    : getent hosts oblada.k13.com (resolusi via resolver lokal)

Usage: python3 verify_soal5.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

NODE_NAMES = [
    "rootkit", "alpha", "beta", "gamma", "delta", "epsilon",
    "prab", "tedd", "abbey", "penny", "obladi", "desmond", "oblada", "molly",
]

NEW_DOMAINS = {
    "rootkit": "10.70.1.1",
    "alpha": "10.70.2.2",
    "beta": "10.70.2.3",
    "gamma": "10.70.2.4",
    "delta": "10.70.3.2",
    "epsilon": "10.70.3.3",
    "abbey": "10.70.4.2",
    "penny": "10.70.5.2",
    "obladi": "10.70.1.4",
    "desmond": "10.70.1.5",
    "oblada": "10.70.1.6",
    "molly": "10.70.1.7",
}


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        tag = f"H{int(time.time()*1000)%941:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
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

    print("=== PART A: hostname system-wide (rootkit..molly) ===")
    host_ok = 0
    for name in NODE_NAMES:
        out = run_one(nodes, name, "hostname; cat /etc/hostname")
        ok = out.count(name) >= 2
        host_ok += 1 if ok else 0
        if not ok:
            print(f"    [!] {name}: hostname tidak sesuai -> {out.strip()[:80]}")
    check(f"hostname system-wide sesuai di 14 node ({host_ok}/14)",
          host_ok == len(NODE_NAMES))

    print("=== PART B: A record per-node di zona k13.com ===")
    dig_ok = 0
    for host, ip in NEW_DOMAINS.items():
        on_prab = run_one(nodes, "prab", f"dig @10.70.1.2 {host}.k13.com A +short")
        on_tedd = run_one(nodes, "tedd", f"dig @10.70.1.3 {host}.k13.com A +short")
        ok = ip in on_prab and ip in on_tedd
        dig_ok += 1 if ok else 0
        if not ok:
            print(f"    [!] {host}.k13.com: prab={on_prab.strip()[:40]!r} "
                  f"tedd={on_tedd.strip()[:40]!r}")
    check(f"domain per-node terjawab prab+tedd ({dig_ok}/12)", dig_ok == 12)

    print("=== PART C: resolusi dari sisi host ===")
    ge = run_one(nodes, "delta", "getent hosts oblada.k13.com")
    check("delta: getent hosts oblada.k13.com -> 10.70.1.6", "10.70.1.6" in ge)
    ge2 = run_one(nodes, "alpha", "getent hosts rootkit.k13.com")
    check("alpha: getent hosts rootkit.k13.com -> 10.70.1.1", "10.70.1.1" in ge2)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 5 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
