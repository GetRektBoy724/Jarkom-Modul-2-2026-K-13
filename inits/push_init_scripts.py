#!/usr/bin/env python3
"""
push_init_scripts.py — Push each node's init script to /root/init.sh via the
node's telnet console, then run it and capture the verification log.

Why telnet: the GNS3 files API only injects /etc/network/interfaces for
docker nodes; /root must be written from inside the node. The console
(telnet served by the controller, ONE client per node at a time) is the
transport.

How: base64-encode the script, feed it in short printf chunks (PTY canonical
mode caps lines at ~255 bytes), decode to /root/init.sh, execute, and read
back the tail of the run log.

NOTE: close any open web console for a node before pushing to it
(one telnet client per node at a time).

Usage:
  python3 push_init_scripts.py               # all 14 host nodes
  python3 push_init_scripts.py rootkit prab  # only these nodes
"""

import base64
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

BASE = "http://10.4.89.246"
PROJECT_NAME = "K-13-MODUL-2"
USERNAME = "K-13"
PASSWORD = "K-13@GNS3"

INIT_DIR = os.path.dirname(os.path.abspath(__file__))

HOST_NODES = [
    "rootkit", "alpha", "beta", "gamma", "delta", "epsilon",
    "prab", "tedd", "abbey", "penny",
    "obladi", "desmond", "oblada", "molly",
]

CHUNK_SIZE = 160          # base64 chars per printf (keeps line < 255 PTY limit)
BOOT_TIMEOUT = 120        # seconds to wait for a node to start
MARKER_TIMEOUT = 20       # seconds for a single marker round-trip
RUN_TIMEOUT = 180         # init.sh may block on DHCP (rootkit eth0)


# ── GNS3 REST helpers ────────────────────────────────────────────────────────
def req(method, path, body=None, token=None, timeout=30):
    r = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(r, data, timeout=timeout) as resp:
                raw = resp.read().decode()
                return resp.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()[:300]
        except Exception as e:
            if attempt == 2:
                return -1, str(e)
            time.sleep(2)


def controller_host():
    return BASE.replace("http://", "").rstrip("/")


def console_endpoint(node):
    """GNS3 reports console_host as a bind-all placeholder (0.0.0.0 / ::);
    the telnet console is actually reachable on the controller itself."""
    host = node.get("console_host")
    if not host or host in ("0.0.0.0", "::", "127.0.0.1", "localhost"):
        return controller_host()
    return host


# ── minimal telnet console client ────────────────────────────────────────────
class Console:
    """Raw-socket telnet client for a GNS3 docker node console.

    Strips telnet IAC negotiation sequences; everything else is treated as
    terminal data. Commands are sent with '\\n'; the shell echo comes back
    in the read stream.
    """

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.sock = None
        self.buf = b""
        self._pending = b""   # unterminated IAC sequence from a previous recv

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.sock.settimeout(0.2)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _strip_iac(self, data):
        # returns (clean_bytes, pending_tail)
        b = self._pending + data
        self._pending = b""
        out = bytearray()
        i = 0
        n = len(b)
        while i < n:
            c = b[i]
            if c != 0xFF:
                out.append(c)
                i += 1
                continue
            if i + 1 >= n:
                self._pending = b[i:]
                break
            cmd = b[i + 1]
            if cmd == 0xFF:                      # escaped 0xFF
                out.append(0xFF)
                i += 2
            elif cmd in (0xFB, 0xFC, 0xFD, 0xFE):  # WILL/WONT/DO/DONT + option
                if i + 2 >= n:
                    self._pending = b[i:]
                    break
                i += 3
            elif cmd == 0xFA:                    # SB ... SE
                j = b.find(b"\xF0", i + 2)
                if j == -1:
                    self._pending = b[i:]
                    break
                i = j + 1
            else:                                # 2-byte commands (NOP, GA, ...)
                i += 2
        return bytes(out)

    def _recv(self):
        try:
            data = self.sock.recv(4096)
        except socket.timeout:
            return b""
        if not data:
            raise ConnectionError("console closed")
        return self._strip_iac(data)

    def send_line(self, line):
        self.sock.sendall(line.encode() + b"\n")

    def read_until(self, marker, timeout):
        """Wait until `marker` (bytes) appears in the stream.
        Returns (ok, consumed_text_including_marker)."""
        marker = marker.encode() if isinstance(marker, str) else marker
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in self.buf:
                idx = self.buf.index(marker) + len(marker)
                consumed, self.buf = self.buf[:idx], self.buf[idx:]
                return True, consumed.decode(errors="replace")
            try:
                self.buf += self._recv()
            except ConnectionError:
                return False, self.buf.decode(errors="replace")
        return False, self.buf.decode(errors="replace")


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)


# ── push one node ────────────────────────────────────────────────────────────
def ensure_started(token, pid, node):
    if node.get("status") == "started":
        return True
    print(f"    starting node ...")
    st, r = req("POST", f"/v3/projects/{pid}/nodes/{node['node_id']}/start", {}, token=token)
    if st not in (200, 201):
        print(f"    start request returned {st}: {r}")
    deadline = time.time() + BOOT_TIMEOUT
    last = None
    while time.time() < deadline:
        st, n = req("GET", f"/v3/projects/{pid}/nodes/{node['node_id']}", token=token)
        status = n.get("status") if st == 200 else f"HTTP {st}"
        if status != last:
            print(f"    status: {status}")
            last = status
        if st == 200 and status == "started":
            time.sleep(3)   # let the console shell spawn
            return True
        time.sleep(2)
    return False


def ensure_all_started(token, pid, nodes, names):
    """Bring up every host node regardless of the push targets: stop-state
    nodes are started in parallel (all start POSTs first), then we poll the
    project until each reports 'started'."""
    pending = [n for n in names
               if n in nodes and nodes[n].get("status") != "started"]
    if pending:
        for name in sorted(pending):
            print(f"    starting {name} ...")
            req("POST", f"/v3/projects/{pid}/nodes/{nodes[name]['node_id']}/start",
                {}, token=token)
        deadline = time.time() + BOOT_TIMEOUT
        remaining = set(pending)
        while time.time() < deadline and remaining:
            time.sleep(2)
            st, ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)
            status_map = {n["name"]: n.get("status") for n in (ns or [])}
            for name in sorted(remaining):
                if status_map.get(name) == "started":
                    print(f"    {name}: started")
                    remaining.discard(name)
        if remaining:
            print(f"[!] still not started: {', '.join(sorted(remaining))}")
            return False
    else:
        print("    all nodes already running")
    return True


def push_node(token, pid, node, script_path):
    name = node["name"]
    if not os.path.exists(script_path):
        return False, f"init script not found: {script_path}"

    if not ensure_started(token, pid, node):
        return False, "node did not start"

    host = console_endpoint(node)
    port = node.get("console")
    if not port:
        return False, "no console port (is the node started?)"

    con = Console(host, port)
    try:
        try:
            con.connect()
        except OSError as e:
            return False, f"console connect failed ({e}) — web console open?"

        # shell alive?
        con.send_line("echo MK$?CHK")
        ok, _ = con.read_until(b"MK0CHK", MARKER_TIMEOUT)
        if not ok:
            return False, "console not responding (booting? web console open?)"

        payload = base64.b64encode(open(script_path, "rb").read()).decode()
        chunks = [payload[i:i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)]

        con.send_line("rm -f /tmp/init.b64")
        for ch in chunks:
            con.send_line(f"printf '%s' '{ch}' >> /tmp/init.b64")
            time.sleep(0.05)

        expected = str(len(payload))
        con.send_line("echo SZ$(wc -c </tmp/init.b64)Z")
        ok, _ = con.read_until(f"SZ{expected}Z".encode(), MARKER_TIMEOUT)
        if not ok:
            return False, f"upload size mismatch (want {expected} bytes)"

        con.send_line("base64 -d /tmp/init.b64 > /root/init.sh && chmod +x /root/init.sh; echo DC$?DC")
        ok, _ = con.read_until(b"DC0DC", MARKER_TIMEOUT)
        if not ok:
            return False, "decode to /root/init.sh failed"

        con.send_line("sh /root/init.sh > /tmp/init_run.log 2>&1; echo RN$?RN")
        ok, _ = con.read_until(b"RN0RN", RUN_TIMEOUT)
        if not ok:
            return False, "init.sh run timed out (see /tmp/init_run.log on node)"

        con.send_line("tail -n 20 /tmp/init_run.log; echo TL$?TL")
        ok, log = con.read_until(b"TL0TL", MARKER_TIMEOUT)
        if not ok:
            return False, "could not read run log"

        return True, log
    finally:
        con.close()


def main():
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    targets = [n for n in HOST_NODES if not wanted or n in wanted]
    unknown = set(wanted) - set(HOST_NODES)
    if unknown:
        sys.exit(f"Unknown node(s): {', '.join(unknown)}\nValid: {', '.join(HOST_NODES)}")

    st, r = req("POST", "/v3/access/users/authenticate",
                {"username": USERNAME, "password": PASSWORD})
    if st != 200:
        sys.exit(f"Authentication failed ({st}): {r}")
    token = r["access_token"]

def main():
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    targets = [n for n in HOST_NODES if not wanted or n in wanted]
    unknown = set(wanted) - set(HOST_NODES)
    if unknown:
        sys.exit(f"Unknown node(s): {', '.join(unknown)}\nValid: {', '.join(HOST_NODES)}")

    st, r = req("POST", "/v3/access/users/authenticate",
                {"username": USERNAME, "password": PASSWORD})
    if st != 200:
        sys.exit(f"Authentication failed ({st}): {r}")
    token = r["access_token"]

    st, projects = req("GET", "/v3/projects", token=token)
    pid = next((p["project_id"] for p in projects if p["name"] == PROJECT_NAME), None)
    if not pid:
        sys.exit(f"Project '{PROJECT_NAME}' not found")

    # the project must be open, otherwise the nodes API returns without
    # full fields (status/console) and console endpoint discovery breaks
    req("POST", f"/v3/projects/{pid}/open", {}, token=token)
    time.sleep(2)

    st, ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)
    nodes = {n["name"]: n for n in (ns or [])}
    missing = [n for n in targets if n not in nodes]
    if missing:
        sys.exit(f"Node(s) missing from project: {', '.join(missing)} — run build_topology.py")

    print(f"[*] Bringing up all host nodes (not just push targets) ...")
    up = ensure_all_started(token, pid, nodes, HOST_NODES)
    if not up:
        print("[!] Some nodes failed to start — only pushes to running nodes will work.\n")
    # refresh records so statuses/console data are current for every node
    st, ns = req("GET", f"/v3/projects/{pid}/nodes", token=token)
    nodes = {n["name"]: n for n in (ns or [])}

    print(f"[*] Pushing init scripts to {len(targets)} node(s): {', '.join(targets)}\n")
    results = {}
    for name in targets:
        script = os.path.join(INIT_DIR, f"init_{name}.sh")
        print(f"── {name} " + "─" * max(1, 60 - len(name)))
        ok, info = push_node(token, pid, nodes[name], script)
        results[name] = ok
        if ok:
            print(f"[+] {name}: pushed & ran OK")
            for line in strip_ansi(info).strip().splitlines():
                if line.strip() and "TL0TL" not in line:
                    print(f"    {line}")
        else:
            print(f"[!] {name}: FAILED — {info}")
        print()

    good = [n for n, ok in results.items() if ok]
    bad = [n for n, ok in results.items() if not ok]
    print(f"=== SUMMARY: {len(good)}/{len(results)} OK ===")
    if bad:
        print(f"[!] Failed: {', '.join(bad)} — close web consoles and re-run for these nodes")
        sys.exit(1)


if __name__ == "__main__":
    main()
