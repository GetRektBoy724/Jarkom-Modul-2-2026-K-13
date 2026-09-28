#!/bin/sh
# init_prab.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:prab] $*"; }

# 1. hostname
echo "prab" > /etc/hostname && chmod 644 /etc/hostname && hostname "prab"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "prab" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 1 (gw 10.70.1.1)
auto eth0
iface eth0 inet static
    address 10.70.1.2
    netmask 255.255.255.0
    gateway 10.70.1.1
EOF
log "wrote /etc/network/interfaces"

# 3. resolver
cat > /etc/resolv.conf <<'EOF'
nameserver 10.70.1.2
nameserver 10.70.1.3
nameserver 192.168.122.1
EOF

# 4. alamat IP
ip link set eth0 up
ip addr replace 10.70.1.2/24 dev eth0
ip route replace default via 10.70.1.1

# 5. DNS master (soal 4)
if ! command -v named >/dev/null 2>&1; then
    log "installing bind9 (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq bind9 bind9-utils bind9-dnsutils
fi
cat > /etc/bind/named.conf <<'CONF'
options {
    directory "/var/cache/bind";
    forwarders { 192.168.122.1; };
    allow-recursion { any; };
    dnssec-validation no;
    listen-on { any; };
};

zone "k13.com" {
    type master;
    file "/etc/bind/db.k13.com";
    notify yes;
    also-notify { 10.70.1.3; };
    allow-transfer { 10.70.1.3; };
};
CONF
SERIAL="$(date +%y%m%d%H%M)"
cat > /etc/bind/db.k13.com <<ZONE
\$TTL 300
@   IN SOA prab.k13.com. admin.k13.com. (
        $SERIAL   ; serial
        3600      ; refresh
        300       ; retry
        604800    ; expire
        300 )     ; negative TTL
    IN NS  prab.k13.com.
    IN NS  tedd.k13.com.
prab     IN A 10.70.1.2
tedd     IN A 10.70.1.3
@        IN A 10.70.5.2
rootkit  IN A 10.70.1.1 ; soal 5: domain per-node (prab/tedd dikecualikan, sudah ada)
alpha    IN A 10.70.2.2
beta     IN A 10.70.2.3
gamma    IN A 10.70.2.4
delta    IN A 10.70.3.2
epsilon  IN A 10.70.3.3
abbey    IN A 10.70.4.2
penny    IN A 10.70.5.2
obladi   IN A 10.70.1.4
desmond  IN A 10.70.1.5
oblada   IN A 10.70.1.6
molly    IN A 10.70.1.7
ZONE
pkill named 2>/dev/null || true
mkdir -p /run/named && chown bind:bind /run/named
sleep 1
named -u bind
sleep 2
SER="$(dig @127.0.0.1 k13.com SOA +short 2>/dev/null | awk '{print $3}')"
log "bind9 master aktif - serial zona: ${SER:-TIDAK JALAN}"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
