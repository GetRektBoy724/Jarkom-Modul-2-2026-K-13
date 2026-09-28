#!/usr/bin/env python3
"""
verify_soal3.py — Soal 3 verification: routing internal lintas segmen via
rootkit + resolver awal 192.168.122.1 pada seluruh host non-router.

Part A — routing matrix: satu host per segmen ping satu host di setiap segmen
lain (5 segmen = 20 kombinasi directed ping):
    seg1 (prab)  seg2 (alpha)  seg3 (delta)  seg4 (abbey)  seg5 (penny)
Part B — resolver: tiap host non-router punya `nameserver 192.168.122.1` di
/etc/resolv.conf dan bisa resolve+ping google.com (2 received).

Usage: python3 verify_soal3.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

HOSTS_BY_SEG = {
    1: {"src": "prab",  "targets": ["tedd", "obladi", "desmond", "oblada", "molly"]},
    2: {"src": "alpha", "targets": ["beta", "gamma"]},
    3: {"src": "delta", "targets": ["epsilon"]},
    4: {"src": "abbey", "targets": []},
    5: {"src": "penny", "targets": []},
}
NON_ROUTER = [
    "prab", "tedd", "obladi", "desmond", "oblada", "molly",
    "alpha", "beta", "gamma", "delta", "epsilon", "abbey", "penny",
]


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        tag = f"Y{int(time.time()*1000)%977:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
    finally:
        con.close()


def ping_pass(out):
    return "2 received" in out


def main():
    token = req("POST", "/v3/access/users/authenticate",
                {"username": "K-13", "password": "K-13@GNS3"})[1]["access_token"]
    pid = next(p["project_id"] for p in req("GET", "/v3/projects", token=token)[1]
               if p["name"] == "K-13-MODUL-2")
    ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)[1]
    nodes = {n["name"]: n for n in ns}
    ipmap = NAME_TO_IP = {
        "prab": "10.70.1.2", "tedd": "10.70.1.3",
        "obladi": "10.70.1.4", "desmond": "10.70.1.5",
        "oblada": "10.70.1.6", "molly": "10.70.1.7",
        "alpha": "10.70.2.2", "beta": "10.70.2.3", "gamma": "10.70.2.4",
        "delta": "10.70.3.2", "epsilon": "10.70.3.3",
        "abbey": "10.70.4.2", "penny": "10.70.5.2",
    }

    results = []

    # ── Part A: cross-segment ping matrix (satu host per segmen) ──
    print("=== PART A: routing matrix lintas segmen ===")
    src_by_seg = {1: "prab", 2: "alpha", 3: "delta", 4: "abbey", 5: "penny"}
    pass_a = 0
    total_a = 0
    for s_i, src in src_by_seg.items():
        for s_j, tgt in src_by_seg.items():
            if s_i == s_j:
                continue
            total_a += 1
            out = run_one(nodes, src, f"ping -c 2 -W 2 {ipmap[tgt]}")
            ok = ping_pass(out)
            pass_a += 1 if ok else 0
            results.append(ok)
            mark = "PASS" if ok else "FAIL"
            print(f"  {mark}: {src} -> {tgt} ({ipmap[tgt]})")
    print(f"  matrix: {pass_a}/{total_a} PASS")

    # ── Part B: resolver 192.168.122.1 + google.com di semua non-router ──
    print("=== PART B: resolver + resolusi domain ===")
    pass_b = 0
    for name in NON_ROUTER:
        resolv = run_one(nodes, name, "cat /etc/resolv.conf")
        has_ns = "nameserver 192.168.122.1" in resolv
        gp_out = run_one(nodes, name, "ping -c 2 -W 3 google.com")
        dns_ok = ping_pass(gp_out)
        ok = has_ns and dns_ok
        pass_b += 1 if ok else 0
        results.append(ok)
        mark = "PASS" if ok else "FAIL"
        detail = []
        if not has_ns:
            detail.append("no 192.168.122.1")
        if not dns_ok:
            detail.append("google.com unreachable/resolution failed")
        suffix = f" ({', '.join(detail)})" if detail else ""
        print(f"  {mark}: {name}{suffix}")
    print(f"  resolver: {pass_b}/{len(NON_ROUTER)} PASS")

    good = sum(1 for ok in results if ok)
    total = len(results)
    print(f"\n=== SOAL 3 VERIFICATION: {good}/{total} checks PASS ===")
    sys.exit(0 if good == total else 1)


if __name__ == "__main__":
    main()
