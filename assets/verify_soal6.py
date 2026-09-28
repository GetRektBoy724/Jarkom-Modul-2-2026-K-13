#!/usr/bin/env python3
"""
verify_soal6.py — Soal 6 verification: zone transfer hidup dan serial SOA
prab (master) == tedd (slave).

Checks (via telnet console):
  A. serial SOA sama di kedua server; keduanya jawab authoritative (aa);
     daftar NS identik
  B. AXFR:
       - dari tedd ke prab  -> zone transfer PENUH dibolehkan (allow-transfer)
       - dari prab ke prab  -> REFUSED (hanya tedd yang boleh menarik zona)
       - /var/cache/bind/db.k13.com ada di tedd (hasil transfer tersimpan)
  C. parity record: setiap record zona dijawab sama oleh master & slave
     (SOA serial, 2x NS, apex, prab, tedd, 12 domain per-node)

Usage: python3 verify_soal6.py
"""

import re
import sys
import os
import time

INITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inits")
sys.path.insert(0, os.path.abspath(INITS_DIR))
from push_init_scripts import Console, console_endpoint, req  # noqa: E402

# seluruh isi zona (harus sinkron dengan gen_init_scripts.py)
RECORDS_A = {
    "k13.com": "10.70.5.2",       # apex -> penny
    "prab.k13.com": "10.70.1.2",
    "tedd.k13.com": "10.70.1.3",
    "rootkit.k13.com": "10.70.1.1",
    "alpha.k13.com": "10.70.2.2",
    "beta.k13.com": "10.70.2.3",
    "gamma.k13.com": "10.70.2.4",
    "delta.k13.com": "10.70.3.2",
    "epsilon.k13.com": "10.70.3.3",
    "abbey.k13.com": "10.70.4.2",
    "penny.k13.com": "10.70.5.2",
    "obladi.k13.com": "10.70.1.4",
    "desmond.k13.com": "10.70.1.5",
    "oblada.k13.com": "10.70.1.6",
    "molly.k13.com": "10.70.1.7",
}


def run_one(nodes, name, cmd, wait=20):
    node = nodes[name]
    con = Console(console_endpoint(node), node["console"])
    try:
        con.connect()
        tag = f"Z{int(time.time()*1000)%953:03d}"
        con.buf = b""
        con.send_line(f"{cmd}; echo {tag}$?{tag}")
        ok, out = con.read_until((tag + "0" + tag).encode(), wait)
        return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out)
    finally:
        con.close()


def soa_serial(out):
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith(("dig", "echo", "root@", ";")):
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

    # ── PART A: serial match + authoritative + NS ──
    ser_m = soa_serial(run_one(nodes, "prab", "dig @10.70.1.2 k13.com SOA +short"))
    ser_s = soa_serial(run_one(nodes, "tedd", "dig @10.70.1.3 k13.com SOA +short"))
    check(f"serial SOA sama: prab={ser_m}, tedd={ser_s}",
          ser_m is not None and ser_m == ser_s)

    fl_m = run_one(nodes, "prab", "dig +norec @10.70.1.2 k13.com SOA")
    check("prab kita profile authoritative (aa)", " aa" in fl_m or "flags: aa" in fl_m)
    fl_s = run_one(nodes, "tedd", "dig +norec @10.70.1.3 k13.com SOA")
    check("tedd kita profile authoritative (aa)", " aa" in fl_s or "flags: aa" in fl_s)

    ns_m = run_one(nodes, "prab", "dig @10.70.1.2 k13.com NS +short").replace("\n", " ")
    ns_s = run_one(nodes, "tedd", "dig @10.70.1.3 k13.com NS +short").replace("\n", " ")
    check("daftar NS identik di master & slave",
          "prab.k13.com" in ns_m and "tedd.k13.com" in ns_m
          and "prab.k13.com" in ns_s and "tedd.k13.com" in ns_s)

    # ── PART B: AXFR ibukota pindahkan ──
    axfr_t = run_one(nodes, "tedd", "dig @10.70.1.2 k13.com AXFR", wait=25)
    axfr_ok = "IN" in axfr_t and "k13.com" in axfr_t and "REFUSED" not in axfr_t
    count = axfr_t.count("k13.com")
    check(f"AXFR dari tedd ke prab BOLEH (transfer hidup; ~{count} record)", axfr_ok)

    axfr_p = run_one(nodes, "prab", "dig @10.70.1.2 k13.com AXFR")
    check("AXFR dari pihak lain (prab sendiri as source 10.70.1.2) DITOLAK",
          "REFUSED" in axfr_p or "Transfer failed" in axfr_p)

    tfile = run_one(nodes, "tedd", "ls -la /var/cache/bind/db.k13.com*")
    check("file hasil transfer tersimpan di /var/cache/bind (tedd)",
          re.search(r"db\.k13\.com", tfile) is not None)

    # ── PART C: parity semua record master vs slave ──
    miss = []
    for name, ip in RECORDS_A.items():
        a_m = run_one(nodes, "prab", f"dig @10.70.1.2 {name} A +short")
        a_s = run_one(nodes, "tedd", f"dig @10.70.1.3 {name} A +short")
        if ip not in a_m or ip not in a_s:
            miss.append(name)
    check(f"seluruh {len(RECORDS_A)} A record dijawab sama oleh prab & tedd"
          + (f" (mismatch: {', '.join(miss)})" if miss else ""),
          not miss)

    good = sum(1 for ok in results if ok)
    print(f"\n=== SOAL 6 VERIFICATION: {good}/{len(results)} checks PASS ===")
    sys.exit(0 if good == len(results) else 1)


if __name__ == "__main__":
    main()
