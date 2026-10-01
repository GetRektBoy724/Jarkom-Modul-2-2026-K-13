#!/bin/sh
# init_alpha.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:alpha] $*"; }

# 1. hostname
echo "alpha" > /etc/hostname && chmod 644 /etc/hostname && hostname "alpha"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "alpha" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 2 (gw 10.70.2.1)
auto eth0
iface eth0 inet static
    address 10.70.2.2
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
ip addr replace 10.70.2.2/24 dev eth0
ip route replace default via 10.70.2.1

# 5. curl
if ! command -v curl >/dev/null 2>&1; then
    log "installing curl (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl
fi
log "curl siap: $(command -v curl)"


# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."

command -v ab >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apache2-utils)
command -v dig >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq bind9-dnsutils)
command -v dnsmasq >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq dnsmasq-base)
cat > /root/fase18.sh <<'SH18'
#!/bin/bash
pkill dnsmasq 2>/dev/null; sleep 2
dnsmasq --conf-file=/dev/null --user=root --port=5353 --listen-address=127.0.0.1 --bind-interfaces --no-resolv --server=/k13.com/10.70.1.2 --cache-size=500 --pid-file=/tmp/dnsmasq18.pid
sleep 1
echo "Klien: alpha $(hostname -I)"
for i in $(seq 1 20); do
  C=$(dig @127.0.0.1 -p 5353 abbey.k13.com +noall +answer | awk '{print $2" "$5}')
  P=$(dig @10.70.1.2 abbey.k13.com +short)
  echo "$(date +%T)  cache(ttl ip): $C   |   prab langsung: $P"
  sleep 2
done
SH18
chmod +x /root/fase18.sh
