#!/usr/bin/env python3
"""
verify_soal1.py — Soal 1 verification: every Entitas has its IP address and
default gateway set, and can reach its gateway.

Checks per node (via telnet console):
  1. expected IPv4 present on the interface (ip -br a)
  2. default route via the segment gateway (ip route)
  3. gateway answers ping (2 packets)

Usage: python3 verify_soal1.py [node ...]   (default: all 15)
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

EXPECTED = {
    # node: (iface, ip, gateway)
    "rootkit": None,  # special: five segment IPs, no single gateway
    "prab":    ("eth0", "10.70.1.2", "10.70.1.1"),
    "tedd":    ("eth0", "10.70.1.3", "10.70.1.1"),
    "obladi":  ("eth0", "10.70.1.4", "10.70.1.1"),
    "desmond": ("eth0", "10.70.1.5", "10.70.1.1"),
    "oblada":  ("eth0", "10.70.1.6", "10.70.1.1"),
    "molly":   ("eth0", "10.70.1.7", "10.70.1.1"),
    "alpha":   ("eth0", "10.70.2.2", "10.70.2.1"),
    "beta":    ("eth0", "10.70.2.3", "10.70.2.1"),
    "gamma":   ("eth0", "10.70.2.4", "10.70.2.1"),
    "delta":   ("eth0", "10.70.3.2", "10.70.3.1"),
    "epsilon": ("eth0", "10.70.3.3", "10.70.3.1"),
    "abbey":   ("eth0", "10.70.4.2", "10.70.4.1"),
    "penny":   ("eth0", "10.70.5.2", "10.70.5.1"),
}

ROOTKIT_SEGS = {f"eth{i}": f"10.70.{i}.1/24" for i in (1, 2, 3, 4, 5)}


def run(con, cmd, wait=10):
    tag = f"V{int(time.time()*1000)%997:03d}"
    con.buf = b""
    con.send_line(f"{cmd}; echo {tag}$?{tag}")
    ok, out = con.read_until((tag + "0" + tag).encode(), wait)
    return ok, re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)


def main():
    wanted = sys.argv[1:]
    targets = [n for n in EXPECTED if not wanted or n in wanted]

    token = req("POST", "/v3/access/users/authenticate",
                {"username": "K-13", "password": "K-13@GNS3"})[1]["access_token"]
    pid = next(p["project_id"] for p in req("GET", "/v3/projects", token=token)[1]
               if p["name"] == "K-13-MODUL-2")
    ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)[1]
    nodes = {n["name"]: n for n in ns}

    results = {}
    for name in targets:
        if name not in nodes:
            print(f"[!] {name}: node not in project")
            results[name] = False
            continue
        node = nodes[name]
        if node["status"] != "started":
            print(f"[!] {name}: not started")
            results[name] = False
            continue

        con = Console(console_endpoint(node), node["console"])
        try:
            con.connect()
            checks = []

            if name == "rootkit":
                _, ip_out = run(con, "ip -br a")
                for iface, want_ip in ROOTKIT_SEGS.items():
                    checks.append((f"{iface}={want_ip}", want_ip in ip_out))
            else:
                iface, ip, gw = EXPECTED[name]
                _, ip_out = run(con, "ip -br a")
                _, route_out = run(con, "ip route")
                _, ping_out = run(con, f"ping -c 2 -W 2 {gw}", wait=15)
                checks.append((f"{iface}={ip}/24", f"{ip}/24" in ip_out))
                checks.append((f"default via {gw}", f"default via {gw}" in route_out))
                checks.append((f"ping {gw}", "2 received" in ping_out or
                               "2 packets received" in ping_out))

            passed = all(ok for _, ok in checks)
            results[name] = passed
            mark = "PASS" if passed else "FAIL"
            print(f"[{'+' if passed else '!'}] {name}: {mark}")
            for label, ok in checks:
                if not ok:
                    print(f"        {label}: MISSING")
        except Exception as e:
            print(f"[!] {name}: console error — {e}")
            results[name] = False
        finally:
            con.close()

    good = sum(1 for ok in results.values() if ok)
    print(f"\n=== SOAL 1 VERIFICATION: {good}/{len(results)} nodes PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
