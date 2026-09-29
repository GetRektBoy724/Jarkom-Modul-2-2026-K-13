#!/usr/bin/env python3
"""
verify_soal8.py — Soal 8 verification: tiga reverse zone (1/4.70.10 ->
area server, 4.70.10 -> abbey, 5.70.10 -> penny), master di prab, slave di
tedd, PTR mengembalikan nama layanan yang benar dan dijawab authoritative.

Checks (via telnet console):
  prab & tedd : dig -x tiap 6 IP (obladi/desmond->vault, oblada/molly->core,
                4.2->abbey, 5.2->penny) + flag aa per zona
  prab & tedd : NS record ketiga reverse zone

Usage: python3 verify_soal8.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

PTRS = {
    "10.70.1.4": "vault.k13.com",     # obladi
    "10.70.1.5": "vault.k13.com",     # desmond
    "10.70.1.6": "core.k13.com",      # oblada
    "10.70.1.7": "core.k13.com",      # molly
    "10.70.4.2": "abbey.k13.com",
    "10.70.5.2": "penny.k13.com",
}
REVERSE_ZONES = ["1.70.10.in-addr.arpa", "4.70.10.in-addr.arpa", "5.70.10.in-addr.arpa"]


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        con.send_line("echo RS$?RS")
        con.read_until(b"RS0RS", 25)
        tag = f"Y{int(time.time()*1000)%929:03d}"
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

    for server, sip, des in (("prab", "10.70.1.2", "master"), ("tedd", "10.70.1.3", "slave")):
        print(f"=== {server} ({des}) ===")
        bad = []
        for ip, want in PTRS.items():
            out = run_one(nodes, server, f"dig @{sip} -x {ip} +short")
            if want not in out:
                bad.append(f"{ip}!={out.strip()[:30]!r}")
        check(f"{server}: 6 PTR mengembalikan nama layanan yang benar"
              + (f" ({'; '.join(bad)})" if bad else ""), not bad)

        aa_bad = []
        for ip, zn in (("10.70.1.4", None), ("10.70.4.2", None), ("10.70.5.2", None)):
            out = run_one(nodes, server, f"dig @{sip} -x {ip}")
            if not ("flags:" in out and " aa" in out):
                aa_bad.append(ip)
        check(f"{server}: query reverse dijawab authoritative (aa, sampel 3 IP)"
              + (f" ({', '.join(aa_bad)})" if aa_bad else ""), not aa_bad)

        ns_bad = []
        for zn in REVERSE_ZONES:
            out = run_one(nodes, server, f"dig @{sip} NS {zn} +short")
            if not ("prab.k13.com" in out and "tedd.k13.com" in out):
                ns_bad.append(zn)
        check(f"{server}: NS record ketiga reverse zone lengkap"
              + (f" ({', '.join(ns_bad)})" if ns_bad else ""), not ns_bad)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 8 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
