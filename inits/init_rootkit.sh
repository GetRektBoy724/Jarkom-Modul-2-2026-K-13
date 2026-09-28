#!/bin/sh
# init_rootkit.sh - soal 1 idempotent router initializer

set -u

log() { echo "[init:rootkit] $*"; }

# 1. hostname
echo "rootkit" > /etc/hostname && chmod 644 /etc/hostname
hostname "rootkit"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "rootkit" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# WAN - NAT (DHCP via udhcpc); forwarding + NAT rules dijalankan init.sh
auto eth0
iface eth0 inet dhcp

# Segment Switch1 - zona resolusi + repositori
auto eth1
iface eth1 inet static
    address 10.70.1.1
    netmask 255.255.255.0

# Segment Switch6 - sayap kiri (pengamat)
auto eth2
iface eth2 inet static
    address 10.70.2.1
    netmask 255.255.255.0

# Segment Switch7 - sayap kanan (eksekutor)
auto eth3
iface eth3 inet static
    address 10.70.3.1
    netmask 255.255.255.0

# Segment Switch4 - gerbang abbey
auto eth4
iface eth4 inet static
    address 10.70.4.1
    netmask 255.255.255.0

# Segment Switch5 - gerbang penny
auto eth5
iface eth5 inet static
    address 10.70.5.1
    netmask 255.255.255.0

EOF
log "wrote /etc/network/interfaces"

# 3. alamat IP
ip link set eth1 up
ip addr replace 10.70.1.1/24 dev eth1
ip link set eth2 up
ip addr replace 10.70.2.1/24 dev eth2
ip link set eth3 up
ip addr replace 10.70.3.1/24 dev eth3
ip link set eth4 up
ip addr replace 10.70.4.1/24 dev eth4
ip link set eth5 up
ip addr replace 10.70.5.1/24 dev eth5
if ! ip -4 addr show dev eth0 | grep -q inet; then
    log "eth0 has no IPv4 - requesting DHCP lease in background"
    (udhcpc -i eth0 -n -q -t 4 -T 3 >/tmp/udhcpc.log 2>&1 || true) &
fi

# 4. NAT (soal 2)
sysctl -w net.ipv4.ip_forward=1 >/dev/null
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
for I in eth1 eth2 eth3 eth4 eth5; do
  iptables -C FORWARD -i $I -o eth0 -j ACCEPT 2>/dev/null \
    || iptables -A FORWARD -i $I -o eth0 -j ACCEPT
done
iptables -C FORWARD -i eth0 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null \
  || iptables -A FORWARD -i eth0 -m state --state ESTABLISHED,RELATED -j ACCEPT
log "NAT: ip_forward aktif, MASQUERADE + FORWARD rules terpasang (idempotent)"

# verify
log "ip addr:"
ip -brief addr show
log "internal routes (expect the 5 segments via connected routes):"
ip route show | grep -E '10\.70\.' || true
log "done."
