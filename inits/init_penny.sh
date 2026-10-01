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

# 6. reverse proxy apache (soal 11)
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
cat > /etc/apache2/conf-available/servername.conf <<'CONF'
ServerName www.k13.com
CONF
a2enconf servername >/dev/null 2>&1 || true
a2enmod proxy proxy_http proxy_balancer lbmethod_byrequests headers >/dev/null 2>&1
cat > /etc/apache2/sites-available/gate-proxy.conf <<'CONF'
<VirtualHost *:80>
    ServerName www.k13.com

    ProxyPreserveHost On
    RequestHeader set X-Real-IP "expr=%{REMOTE_ADDR}"

    <Proxy balancer://vault>
        BalancerMember http://10.70.1.4
        BalancerMember http://10.70.1.5
    </Proxy>
    ProxyPass /admin !
    ProxyPass / balancer://vault/
    ProxyPassReverse / balancer://vault/

    Alias /admin /var/www/admin
    <Directory /var/www/admin>
        Options Indexes
        AllowOverride None
        AuthType Basic
        AuthName "Area Rahasia Sindikat"
        AuthUserFile /etc/apache2/.htpasswd
        Require valid-user
    </Directory>
</VirtualHost>

CONF
a2dissite 000-default >/dev/null 2>&1
a2ensite gate-proxy >/dev/null 2>&1
apache2ctl configtest >/dev/null 2>&1 || true
apache2ctl stop >/dev/null 2>&1 || true
sleep 2
apache2ctl start
N=0
until pidof apache2 >/dev/null 2>&1 || [ $N -ge 10 ]; do
    sleep 1
    N=$((N+1))
done
log "apache reverse proxy aktif - balancer vault: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/arsip/)"

# 7. basic auth /admin (soal 12)
if ! command -v htpasswd >/dev/null 2>&1; then
    log "installing apache2-utils (menunggu koneksi internet untuk apt) ..."
    W=0
    until ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 || [ $W -ge 24 ]; do
        sleep 5
        W=$((W+1))
    done
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apache2-utils
fi
mkdir -p /var/www/admin
cat > /var/www/admin/index.html <<'HTML'
<!DOCTYPE html>
<html>
<head><title>Dokumen Rahasia Sindikat</title></head>
<body>
<h1>Dokumen Rahasia Sindikat</h1>
<p>Area admin penny - dokumen ini hanya untuk anggota inti.</p>
</body>
</html>
HTML
htpasswd -cbB /etc/apache2/.htpasswd prabs 'pakar_pinter_jadi_goblok'
apache2ctl configtest >/dev/null 2>&1 || true
apache2ctl stop >/dev/null 2>&1 || true
sleep 2
apache2ctl start
N=0
until pidof apache2 >/dev/null 2>&1 || [ $N -ge 10 ]; do
    sleep 1
    N=$((N+1))
done
log "basic auth /admin aktif (prabs); /admin dilayani lokal penny"

# verify
log "ip addr:"
ip -brief addr show
log "default routes:"
ip route show | grep -E 'default|^10\.70\.' || true
log "resolver:"
cat /etc/resolv.conf
log "done."
echo '<VirtualHost *:80>' > /etc/apache2/sites-available/penny-redirect.conf
echo '    ServerName penny.k13.com' >> /etc/apache2/sites-available/penny-redirect.conf
echo '    ServerAlias 10.70.5.2' >> /etc/apache2/sites-available/penny-redirect.conf
echo '    Redirect permanent / http://www.k13.com/' >> /etc/apache2/sites-available/penny-redirect.conf
echo '</VirtualHost>' >> /etc/apache2/sites-available/penny-redirect.conf
a2ensite penny-redirect.conf >/dev/null
service apache2 restart
echo "[init:penny] redirect penny aktif (301 ke www.k13.com)"
ls /etc/apache2/mods-available/php*.load >/dev/null 2>&1 || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libapache2-mod-php)
mkdir -p /var/www/eternal
echo '<?php echo "Eternal PHP aktif, versi " . phpversion(); ?>' > /var/www/eternal/index.php
chown -R www-data:www-data /var/www/eternal
echo 'ProxyPass /eternal !' > /etc/apache2/eternal-path.conf
echo 'Alias /eternal /var/www/eternal' >> /etc/apache2/eternal-path.conf
echo '<Directory /var/www/eternal>' >> /etc/apache2/eternal-path.conf
echo '    DirectoryIndex index.php index.html' >> /etc/apache2/eternal-path.conf
echo '    Options -Indexes' >> /etc/apache2/eternal-path.conf
echo '    AllowOverride None' >> /etc/apache2/eternal-path.conf
echo '    Require all granted' >> /etc/apache2/eternal-path.conf
echo '</Directory>' >> /etc/apache2/eternal-path.conf
grep -q "eternal-path" /etc/apache2/sites-available/gate-proxy.conf || sed -i '/ProxyPass \/admin !/a\    Include /etc/apache2/eternal-path.conf' /etc/apache2/sites-available/gate-proxy.conf
service apache2 restart
echo "[init:penny] eternal aktif (php)"
