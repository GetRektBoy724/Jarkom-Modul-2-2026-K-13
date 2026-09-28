#!/usr/bin/env python3
"""
verify_soal4.py — Soal 4 verification: zona authoritative k13.com (prab=master,
tedd=slave) + resolver reorder (prab -> tedd -> 192.168.122.1) di semua
host non-router.

Checks (via telnet console):
  prab (ns1): apex A -> penny(10.70.5.2), A prab/tedd, NS records,
              authoritative (aa flag)
  tedd (ns2): transfered zone answers authoritative with SAME SOA serial
  alpha     : getent hosts via local resolver config (uses prab first)
  all 13    : /etc/resolv.conf = 10.70.1.2, 10.70.1.3, 192.168.122.1 (order)
  prab      : forwarders work (dig @prab google.com answers)

Usage: python3 verify_soal4.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

NON_ROUTER = [
    "prab", "tedd", "obladi", "desmond", "oblada", "molly",
    "alpha", "beta", "gamma", "delta", "epsilon", "abbey", "penny",
]


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        tag = f"D{int(time.time()*1000)%977:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
    finally:
        con.close()


def soa_serial(nodes, server_ip):
    out = run_one(nodes, "prab" if server_ip == "10.70.1.2" else "tedd",
                  f"dig @{server_ip} k13.com SOA +short")
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith(("dig", "echo", "root@")):
            parts = line.split()
            if len(parts) >= 3:
                return parts[2]
    return None


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

    # ── prab (master) ──
    apex = run_one(nodes, "prab", "dig @10.70.1.2 k13.com A +short")
    check("prab: apex k13.com -> 10.70.5.2 (penny)", "10.70.5.2" in apex)
    pa = run_one(nodes, "prab", "dig @10.70.1.2 prab.k13.com A +short")
    check("prab: prab.k13.com -> 10.70.1.2", "10.70.1.2" in pa)
    ta = run_one(nodes, "prab", "dig @10.70.1.2 tedd.k13.com A +short")
    check("prab: tedd.k13.com -> 10.70.1.3", "10.70.1.3" in ta)
    nsrec = run_one(nodes, "prab", "dig @10.70.1.2 k13.com NS +short")
    flat = nsrec.replace("\n", " ")
    check("prab: NS records prab.k13.com & tedd.k13.com",
          "prab.k13.com" in flat and "tedd.k13.com" in flat)
    flags = run_one(nodes, "prab", "dig +norec @10.70.1.2 k13.com A")
    check("prab: jawaban authoritative (flag aa)", " aa" in flags or "flags: aa" in flags)

    # ── tedd (slave) ──
    t_apex = run_one(nodes, "tedd", "dig @10.70.1.3 k13.com A +short")
    check("tedd: zona ter-transfer, apex -> 10.70.5.2", "10.70.5.2" in t_apex)
    t_flags = run_one(nodes, "tedd", "dig +norec @10.70.1.3 k13.com A")
    check("tedd: jawaban authoritative (flag aa)", " aa" in t_flags or "flags: aa" in t_flags)
    ser_master = soa_serial(nodes, "10.70.1.2")
    ser_slave = soa_serial(nodes, "10.70.1.3")
    check(f"tedd: serial sama dengan prab ({ser_master})",
          ser_master is not None and ser_master == ser_slave)

    # ── forwarders di prab ──
    gw = run_one(nodes, "prab", "dig @10.70.1.2 google.com A +short", wait=25)
    check("prab: forwarders 192.168.122.1 aktif (google.com terjawab)",
          bool(re.search(r"\d+\.\d+\.\d+\.\d+", gw)))

    # ── host-side: alpha pakai resolver lokal ──
    ge = run_one(nodes, "alpha", "getent hosts k13.com")
    check("alpha: getent hosts k13.com -> 10.70.5.2 (via prab)", "10.70.5.2" in ge)

    # ── resolv.conf urutan di seluruh host non-router ──
    res_ok = 0
    for name in NON_ROUTER:
        rc = run_one(nodes, name, "cat /etc/resolv.conf")
        ok = ("nameserver 10.70.1.2" in rc and "nameserver 10.70.1.3" in rc
              and "nameserver 192.168.122.1" in rc
              and rc.find("nameserver 10.70.1.2") < rc.find("nameserver 10.70.1.3")
              < rc.find("nameserver 192.168.122.1"))
        res_ok += 1 if ok else 0
        if not ok:
            print(f"    [!] {name}: resolv.conf salah urutan/isi")
    check(f"resolv.conf prab->tedd->192.168.122.1 di seluruh host ({res_ok})",
          res_ok == len(NON_ROUTER))

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 4 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
