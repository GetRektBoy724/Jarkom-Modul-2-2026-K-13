#!/bin/sh
# init_oblada.sh - soal 1 idempotent node initializer

set -u

log() { echo "[init:oblada] $*"; }

# 1. hostname
echo "oblada" > /etc/hostname && chmod 644 /etc/hostname && hostname "oblada"
CURRENT_HOST="$(hostname)"
log "hostname: $CURRENT_HOST"
if [ "$CURRENT_HOST" != "oblada" ]; then
    log "PERINGATAN: hostname gagal diubah ($CURRENT_HOST)"
fi

# 2. /etc/network/interfaces
cat > /etc/network/interfaces <<'EOF'
# eth0 - segment 1 (gw 10.70.1.1)
auto eth0
iface eth0 inet static
    address 10.70.1.6
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
ip addr replace 10.70.1.6/24 dev eth0
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

# 6. web dinamis nginx (soal 10)
if ! [ -x /usr/sbin/php-fpm8.4 ] || ! command -v nginx >/dev/null 2>&1; then
    log "installing nginx + php8.4-fpm (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx php8.4-fpm
fi
mkdir -p /var/www/beranda
cat > /var/www/beranda/index.php <<'PHP'
<?php
echo "BERANDA The Mesh - PHP " . PHP_VERSION . " di " . gethostname();
echo " | Host: " . ($_SERVER['HTTP_HOST'] ?? '-');
echo " | X-Real-IP: " . ($_SERVER['HTTP_X_REAL_IP'] ?? '-');
PHP
cat > /var/www/beranda/profil.php <<'PHP'
<?php
echo "PROFIL The Mesh - URL: " . htmlspecialchars($_SERVER['REQUEST_URI']);
echo " | PHP " . PHP_VERSION . " di " . gethostname();
PHP
cat > /etc/nginx/sites-available/beranda <<'CONF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/beranda;
    index index.php index.html;

    location / {
        try_files $uri $uri/ $uri.php$is_args$args;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.4-fpm.sock;
    }
}

CONF
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/beranda /etc/nginx/sites-enabled/beranda
service php8.4-fpm restart >/dev/null 2>&1 || /usr/sbin/php-fpm8.4 --daemonize
nginx -t >/dev/null 2>&1 || true
nginx -s quit 2>/dev/null || true
sleep 1
nginx
N=0
until curl -s -o /dev/null http://127.0.0.1/ || [ $N -ge 10 ]; do
    sleep 1
    N=$((N+1))
done
log "nginx + php-fpm aktif - /profil tanpa .php: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/profil)"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
echo "set_real_ip_from 10.70.4.2;" > /etc/nginx/conf.d/realip.conf
echo "real_ip_header X-Forwarded-For;" >> /etc/nginx/conf.d/realip.conf
service nginx restart
