#!/bin/sh
# init_penny.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:penny] $*"; }

# 1. hostname
echo "penny" > /etc/hostname && chmod 644 /etc/hostname && hostname "penny"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "penny" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 5 (gw 10.70.5.1)
auto eth0
iface eth0 inet static
    address 10.70.5.2
    netmask 255.255.255.0
    gateway 10.70.5.1
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
ip addr replace 10.70.5.2/24 dev eth0
ip route replace default via 10.70.5.1


# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
