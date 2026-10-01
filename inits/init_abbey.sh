#!/bin/sh
# init_abbey.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:abbey] $*"; }

# 1. hostname
echo "abbey" > /etc/hostname && chmod 644 /etc/hostname && hostname "abbey"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "abbey" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 4 (gw 10.70.4.1)
auto eth0
iface eth0 inet static
    address 10.70.4.2
    netmask 255.255.255.0
    gateway 10.70.4.1
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
ip addr replace 10.70.4.2/24 dev eth0
ip route replace default via 10.70.4.1

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

# 6. reverse proxy nginx (soal 11)
if ! command -v nginx >/dev/null 2>&1; then
    log "installing nginx (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
fi
cat > /etc/nginx/sites-available/core-proxy <<'CONF'
upstream core_backends {
    server 10.70.1.6;
    server 10.70.1.7;
}
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://core_backends;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

CONF
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/core-proxy /etc/nginx/sites-enabled/core-proxy
nginx -t >/dev/null 2>&1 || true
nginx -s quit 2>/dev/null || true
sleep 1
nginx
N=0
until curl -s -o /dev/null http://127.0.0.1/ || [ $N -ge 10 ]; do
    sleep 1
    N=$((N+1))
done
log "nginx reverse proxy aktif - upstream core: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/)"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
command -v nginx >/dev/null 2>&1 || (apt update && apt install nginx -y)
echo 'server {' > /etc/nginx/sites-available/redirect
echo '    listen 80;' >> /etc/nginx/sites-available/redirect
echo '    server_name 10.70.4.2 abbey.k13.com;' >> /etc/nginx/sites-available/redirect
echo '    return 302 http://static.k13.com$request_uri;' >> /etc/nginx/sites-available/redirect
echo '}' >> /etc/nginx/sites-available/redirect
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/redirect /etc/nginx/sites-enabled/redirect
pkill nginx 2>/dev/null || true
sleep 1
service nginx start
echo "[init:abbey] redirect abbey aktif (302 ke static.k13.com)"
mkdir -p /var/www/orion
echo '<h1>Orion statis</h1>' > /var/www/orion/index.html
echo '<?php echo "PHP dijalankan"; ?>' > /var/www/orion/tes.php
chmod -R 755 /var/www/orion
echo 'location /orion {' > /etc/nginx/orion-location.conf
echo '    alias /var/www/orion;' >> /etc/nginx/orion-location.conf
echo '    index index.html;' >> /etc/nginx/orion-location.conf
echo '}' >> /etc/nginx/orion-location.conf
grep -q "orion-location" /etc/nginx/sites-available/core-proxy || sed -i '/server_name _;/a\    include /etc/nginx/orion-location.conf;' /etc/nginx/sites-available/core-proxy
nginx -s reload
echo "[init:abbey] orion aktif (statis)"
