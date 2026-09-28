#!/bin/sh
# init_tedd.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:tedd] $*"; }

# 1. hostname
echo "tedd" > /etc/hostname && chmod 644 /etc/hostname && hostname "tedd"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "tedd" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 1 (gw 10.70.1.1)
auto eth0
iface eth0 inet static
    address 10.70.1.3
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
ip addr replace 10.70.1.3/24 dev eth0
ip route replace default via 10.70.1.1

# 5. DNS slave (soal 4)
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
    type slave;
    masters { 10.70.1.2; };
    file "/var/cache/bind/db.k13.com";
};
CONF
pkill named 2>/dev/null || true
rm -f /var/cache/bind/db.k13.com*
mkdir -p /run/named && chown bind:bind /run/named
sleep 1
named -u bind
N=0
SER=""
while [ $N -lt 15 ]; do
    SER="$(dig @127.0.0.1 k13.com SOA +short 2>/dev/null | awk '{print $3}')"
    if [ -n "$SER" ]; then
        break
    fi
    N=$((N+1))
    sleep 2
done
log "bind9 slave aktif - serial zona dari master: ${SER:-BELUM TRANSFER}"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
