#!/usr/bin/env python3
"""
verify_soal2.py — Soal 2 verification: internal hosts reach the public
internet by IP through rootkit's NAT.

Checks:
  rootkit : net.ipv4.ip_forward == 1
            MASQUERADE rule present (-t nat POSTROUTING -o eth0)
            FORWARD ACCEPT rules present (eth1..eth5 out + ESTABLISHED in)
  prab    : ping -c 2 8.8.8.8  (10.70.1.2, Switch2 via Switch1 cascade)
  alpha   : ping -c 2 8.8.8.8  (10.70.2.2, Switch6)

Usage: python3 verify_soal2.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402


def run(con, cmd, wait=15):
    tag = f"W{int(time.time()*1000)%997:03d}"
    con.buf = b""
    con.send_line(f"{cmd}; echo {tag}$?{tag}")
    ok, out = con.read_until((tag + "0" + tag).encode(), wait)
    return ok, re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)


def ping_target(node, ip, name):
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        ok, out = run(con, f"ping -c 2 -W 2 {ip}")
        passed = "2 received" in out
        print(f"[{'+' if passed else '!'}] {name}: ping {ip} "
              f"-> {'PASS' if passed else 'FAIL (100% loss)'}")
        if not passed:
            print("    " + out.strip().splitlines()[-2] if len(out.strip().splitlines()) > 1 else out[:200])
        return passed
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

    # ── rootkit NAT state ──
    rk = nodes["rootkit"]
    con = Console(console_endpoint(rk), rk["console"])
    try:
        con.connect()
        _, sysctl_out = run(con, "sysctl net.ipv4.ip_forward")
        fwd_ok = "= 1" in sysctl_out
        _, nat_out = run(con, "iptables -t nat -S POSTROUTING")
        masq_ok = "MASQUERADE" in nat_out and "-o eth0" in nat_out.replace("\n", " ")
        _, fw_out = run(con, "iptables -S FORWARD")
        fw_flat = fw_out.replace("\n", " ")
        fwd_rules = all(f"-i eth{i} -o eth0" in fw_flat for i in (1, 2, 3, 4, 5))
        # kernel may reorder the state list: accept either ESTABLISHED,RELATED
        # or RELATED,ESTABLISHED
        est_ok = "--state" in fw_flat and "ESTABLISHED" in fw_flat and "RELATED" in fw_flat
        print(f"[{'+' if fwd_ok else '!'}] rootkit: net.ipv4.ip_forward == 1")
        print(f"[{'+' if masq_ok else '!'}] rootkit: MASQUERADE -o eth0 present")
        print(f"[{'+' if fwd_rules else '!'}] rootkit: FORWARD ACCEPT eth1..eth5 -> eth0")
        print(f"[{'+' if est_ok else '!'}] rootkit: FORWARD ESTABLISHED,RELATED return path")
        results += [fwd_ok, masq_ok, fwd_rules, est_ok]
    finally:
        con.close()

    # ── internet reachability from two segments ──
    for name in ("prab", "alpha"):
        results.append(ping_target(nodes[name], "8.8.8.8", name))

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 2 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
