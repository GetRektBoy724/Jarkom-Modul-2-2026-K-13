#!/bin/sh
# init_obladi.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:obladi] $*"; }

# 1. hostname
echo "obladi" > /etc/hostname && chmod 644 /etc/hostname && hostname "obladi"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "obladi" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 1 (gw 10.70.1.1)
auto eth0
iface eth0 inet static
    address 10.70.1.4
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
ip addr replace 10.70.1.4/24 dev eth0
ip route replace default via 10.70.1.1

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

# 6. web statis apache (soal 9)
if ! command -v apache2 >/dev/null 2>&1; then
    log "installing apache2 (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apache2
fi
mkdir -p /var/www/html/arsip
for F in dokumen-1.txt dokumen-2.txt dokumen-3.txt; do
    if [ ! -f /var/www/html/arsip/$F ]; then
        echo "dokumen sindikat: $F" > /var/www/html/arsip/$F
    fi
done
cat > /etc/apache2/conf-available/autoindex-arsip.conf <<'CONF'
ServerName obladi.k13.com

<Directory /var/www/html/arsip>
    Options +Indexes
    AllowOverride None
    Require all granted
</Directory>
CONF
a2enconf autoindex-arsip >/dev/null 2>&1 || true
a2enmod autoindex >/dev/null 2>&1 || true
apache2ctl configtest >/dev/null 2>&1 || true
apache2ctl stop >/dev/null 2>&1 || true
apache2ctl start
N=0
until pidof apache2 >/dev/null 2>&1 || [ $N -ge 10 ]; do
    sleep 1
    N=$((N+1))
done
PID="$(pidof apache2 || echo TIDAK JALAN)"
log "apache2 aktif - pid: $PID"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
