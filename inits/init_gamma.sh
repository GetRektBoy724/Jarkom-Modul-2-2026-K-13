#!/bin/sh
# init_gamma.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:gamma] $*"; }

# 1. hostname
echo "gamma" > /etc/hostname && chmod 644 /etc/hostname && hostname "gamma"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "gamma" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 2 (gw 10.70.2.1)
auto eth0
iface eth0 inet static
    address 10.70.2.4
    netmask 255.255.255.0
    gateway 10.70.2.1
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
ip addr replace 10.70.2.4/24 dev eth0
ip route replace default via 10.70.2.1


# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
