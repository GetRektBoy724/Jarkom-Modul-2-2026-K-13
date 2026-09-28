# Laporan Resmi Praktikum Modul 2 Jarkom

| No | Nama Anggota | NRP |
|---|---|---|
| 1. | Atik Putri Matulina | 5027251128 |
| 2. | Muhammad Syihan Zhafiri | 5027251052 |

> Prefix IP Kelompok: `10.70.x.x` (K-13) · Controller GNS3: `http://10.4.89.246` (Group A) · Image: `ardhptr21/debinet:latest`

## Soal 1

> Sebagai pusat kesadaran The Mesh, rootkit harus merentangkan koneksinya ke lima gerbang utama (Switch). Tetapkan alamat IP dan default gateway untuk seluruh Entitas, mulai dari para operator (alpha, beta, gamma), penjaga directory (prab, tedd), gerbang penyaring (abbey, penny), hingga repository (obladi, desmond, oblada, molly) sesuai dengan topologi pembagian switch yang dirancang. [GUNAKAN PREFIX IP MASING-MASING KELOMPOK]

---

### Konfigurasi

Topologi dibangun sesuai diagram referensi pada dokumen soal: router **rootkit** sebagai pusat (6 network adapter: eth0 untuk NAT/WAN, eth1–eth5 untuk lima segmen switch), ditambah 7 Ethernet switch dan 13 Entitas client/server (`ardhptr21/debinet:latest`). Switch2 dan Switch3 ber-cascade di bawah Switch1 sehingga zona resolusi (prab, tedd) dan repositori (obladi, desmond, oblada, molly) berada pada satu segmen L2 yang sama.

![topologi](assets/soal1-topologi.png)

Pembagian subnet menggunakan prefix kelompok K-13 yaitu `10.70.x.x` dengan satu /24 per segmen switch:

| Subnet | Switch | Node | Interface | IP Address | Gateway |
|---|---|---|---|---|---|
| 10.70.1.0/24 | Switch1 | rootkit | eth1 | 10.70.1.1/24 | — |
| | (via Switch2) | prab | eth0 | 10.70.1.2/24 | 10.70.1.1 |
| | | tedd | eth0 | 10.70.1.3/24 | 10.70.1.1 |
| | (via Switch3) | obladi | eth0 | 10.70.1.4/24 | 10.70.1.1 |
| | | desmond | eth0 | 10.70.1.5/24 | 10.70.1.1 |
| | | oblada | eth0 | 10.70.1.6/24 | 10.70.1.1 |
| | | molly | eth0 | 10.70.1.7/24 | 10.70.1.1 |
| 10.70.2.0/24 | Switch6 | rootkit | eth2 | 10.70.2.1/24 | — |
| | | alpha | eth0 | 10.70.2.2/24 | 10.70.2.1 |
| | | beta | eth0 | 10.70.2.3/24 | 10.70.2.1 |
| | | gamma | eth0 | 10.70.2.4/24 | 10.70.2.1 |
| 10.70.3.0/24 | Switch7 | rootkit | eth3 | 10.70.3.1/24 | — |
| | | delta | eth0 | 10.70.3.2/24 | 10.70.3.1 |
| | | epsilon | eth0 | 10.70.3.3/24 | 10.70.3.1 |
| 10.70.4.0/24 | Switch4 | rootkit | eth4 | 10.70.4.1/24 | — |
| | | abbey | eth0 | 10.70.4.2/24 | 10.70.4.1 |
| 10.70.5.0/24 | Switch5 | rootkit | eth5 | 10.70.5.1/24 | — |
| | | penny | eth0 | 10.70.5.2/24 | 10.70.5.1 |

(Kolom interface rootkit eth0 untuk WAN/NAT baru dikonfigurasi pada Soal 2.)

Konfigurasi IP statis setiap node ditulis pada `/etc/network/interfaces` — contoh pada rootkit (eth1–eth5 sebagai gateway lima segmen):
```
auto eth1
iface eth1 inet static
    address 10.70.1.1
    netmask 255.255.255.0
auto eth2
iface eth2 inet static
    address 10.70.2.1
    netmask 255.255.255.0
auto eth3
iface eth3 inet static
    address 10.70.3.1
    netmask 255.255.255.0
auto eth4
iface eth4 inet static
    address 10.70.4.1
    netmask 255.255.255.0
auto eth5
iface eth5 inet static
    address 10.70.5.1
    netmask 255.255.255.0
```
dan contoh pada Entitas prab (pola sama untuk seluruh Entitas, disesuaikan IP/gatewaynya):
```
auto eth0
iface eth0 inet static
    address 10.70.1.2
    netmask 255.255.255.0
    gateway 10.70.1.1
```

Karena image `debinet` tidak menyediakan `ifup`/`ifdown`, alamat IP diterapkan secara live menggunakan perintah `ip` (`ip addr replace`, `ip route replace default`) yang bersifat idempotent aman untuk dijalankan ulang. Seluruh konfigurasi ini dibungkus dalam script init per-node (`/root/init.sh`) yang otomatis dieksekusi image debinet pada setiap boot melalui `/etc/debinet-init.sh`, sehingga konfigurasi bertahan saat node di-restart:

```
#!/bin/sh
...
[ -f /root/init.sh ] && [ -x /root/init.sh ] && /root/init.sh
...
```

Setiap hostname juga ditetapkan agar setiap host mengenali identitasnya secara system-wide (contoh verifikasi kartu hostname pada verifikasi di bawah).

### Verifikasi

Setiap node diperiksa alamat IP-nya sesuai tabel di atas. Contoh `ip -br a` pada rootkit — kelima gateway segmen terpasang (eth0 = NAT, dikonfigurasi pada Soal 2):

![rootkit ip](assets/soal1-rootkit-ip.png)

Contoh pada Entitas prab (10.70.1.2/24, default gateway 10.70.1.1):

![prab ip](assets/soal1-prab-ip.png)

Gateway masing-masing segmen menguji keterjangkauan dari Entitas-nya (contoh prab dan alpha):

![gateway ping prab](assets/soal1-gateway-ping-prab.png)

![gateway ping alpha](assets/soal1-gateway-ping-alpha.png)

Kami juga membuat script verifikasi otomatis yang terhubung ke konsol telnet setiap node melalui GNS3 API untuk memeriksa IP, default route, dan ping gateway pada seluruh 15 node sekaligus (kode lengkap pada `assets/soal1-verify_soal1.py`). Hasilnya seluruh node PASS:

![verifikasi soal1](assets/soal1-verifikasi.png)

## Soal 2

> Meskipun The Mesh beroperasi dalam bayang-bayang, Rootkit menyadari bahwa Entitas di dalamnya masih membutuhkan asupan paket dari dunia luar. Buka jalur menuju NAT dengan memastikan antarmuka WAN di router rootkit aktif. Konfigurasikan NAT agar dapat meneruskan lalu lintas keluar bagi seluruh alamat internal, sehingga semua host di dalam jaringan dapat menjangkau internet publik menggunakan IP address.

---

### Konfigurasi

Antarmuka WAN rootkit (eth0) sudah aktif sejak Soal 1 — meminta alamat secara dinamis (DHCP) dari node NAT GNS3 (`iface eth0 inet dhcp`), sehingga rootkit berada pada jaringan 192.168.122.0/24 milik NAT. Agar seluruh alamat internal (10.70.x.x) dapat menjangkau internet publik, blok NAT ditambahkan pada `init_rootkit.sh` (`/root/init.sh` di node rootkit) sehingga aktif otomatis saat boot maupun saat script dijalankan ulang:

```
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth2 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth3 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth4 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth5 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -m state --state ESTABLISHED,RELATED -j ACCEPT
```

Penjelasan tiap rule:
- `sysctl -w net.ipv4.ip_forward=1` - mengizinkan kernel rootkit meneruskan paket antar-interface (L2/L3 gateway untuk kelima segmen).
- `iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE` - menyamarkan source IP internal (10.70.x.x) menjadi IP DHCP eth0 (192.168.122.x) saat paket keluar ke internet, sehingga balasan internet tahu harus kembali ke rootkit.
- `iptables -A FORWARD -i eth1..eth5 -o eth0 -j ACCEPT` - mengizinkan trafik keluar dari kelima segmen LAN menuju WAN.
- `iptables -A FORWARD -i eth0 -m state --state ESTABLISHED,RELATED -j ACCEPT` - mengizinkan paket balasan dari internet masuk kembali, hanya untuk koneksi yang dibangun dari dalam.

Setiap rule dipasang dengan guard `iptables -C` (cek dulu, tambah bila belum ada) sehingga script tetap idempotent. rules dijalankan pada bagian NAT init_rootkit.sh:

![rootkit nat rules](assets/soal2-rootkitnat.png)

### Verifikasi

Dari console Entitas di segmen berbeda, dilakukan pengujian `ping 8.8.8.8` (internet publik via IP, sesuai soal). Berikut hasil dari prab (10.70.1.2, zona resolusi via Switch1-cascade):

![ping internet prab](assets/soal2-pingprab.png)

Dan dari alpha (10.70.2.2, sayap kiri via Switch6):

![ping internet alpha](assets/soal2-pingalpha.png)

Verifikasi otomatis (kode lengkap pada `assets/soal2-verify_soal2.py`) memeriksa status `ip_forward`, rule MASQUERADE/FORWARD pada rootkit, dan ping 8.8.8.8 dari dua segmen:

![verifikasi soal2](assets/soal2-verifikasi.png)

## Soal 3

> Jaringan rahasia tidak akan berfungsi tanpa sinkronisasi antar divisi. Pastikan seluruh Entitas dapat saling terhubung dan berkomunikasi lintas jalur (routing internal via rootkit berfungsi). Untuk menghindari fragmentasi saat persiapan, pastikan setiap host non-router menambahkan resolver 192.168.122.1 (tambah di file /etc/resolv.conf, kalau sudah pakai resolver itu tidak perlu memasukkan resolver google) saat antarmukanya aktif agar akses untuk mengunduh paket instalasi dari internet tersedia sejak awal beroperasi.

---

### Konfigurasi

Routing internal tidak memerlukan konfigurasi tambahan: rootkit mengenal kelima subnet (10.70.1.0/24 hingga 10.70.5.0/24) sebagai directly-connected network pada eth1–eth5, dan setiap Entitas memakai IP rootkit di segmennya sebagai default gateway (Soal 1), sehingga paket lintas segmen otomatis diteruskan oleh rootkit.

Pada setiap host non-router (13 Entitas; rootkit dikecualikan karena berperan sebagai router), resolver awal `192.168.122.1` (DNS internal node NAT GNS3) ditulis ke `/etc/resolv.conf` melalui blok baru pada `init_<node>.sh`:

```
echo "nameserver 192.168.122.1" > /etc/resolv.conf
```

Karena `/root/init.sh` dijalankan otomatis oleh debinet pada setiap boot (lihat Soal 1), resolver ini aktif "saat antarmuka aktif" tepat seperti diminta soal — tersedia sejak awal beroperasi untuk mengunduh paket instalasi.

Contoh isi `/etc/resolv.conf` pada host prab:

![resolver prab](assets/soal3-resolverprab.png)

### Verifikasi

Pengujian routing lintas segmen dilakukan dari satu host per segmen ke segmen lainnya (prab/alpha/delta/abbey/penny) — contoh pengujian tenacity rute dari alpha ke segmen para penjaga direktori dan repositori:

![ping lintas segmen alpha](assets/soal3-pingalpha.png)

Setiap host non-router juga diuji mampu me-resolve dan menjangkau domain publik menggunakan resolver 192.168.122.1 (contoh pada tedd):

![ping google tedd](assets/soal3-pinggoogletedd.png)

Verifikasi otomatis (kode lengkap pada `assets/soal3-verify_soal3.py`) menjalankan matriks ping lintas segmen (kombinasi 20) dan pemeriksaan resolver + resolusi `google.com` pada seluruh 13 host:

![verifikasi soal3](assets/soal3-verifikasi.png)

## Soal 4

> Penjaga Direktori mulai menuliskan hukum The Mesh. Pada node prab, bangun zona <xxxx>.com sebagai authoritative dengan SOA yang menunjuk ke prab.<xxxx>.com, serta tambahkan catatan NS untuk prab.<xxxx>.com dan tedd.<xxxx>.com. Buat A record untuk prab.<xxxx>.com dan tedd.<xxxx>.com yang mengarah ke alamat IP mereka masing-masing, serta A record apex <xxxx>.com yang mengarah ke gerbang aplikasi dinamis (penny). Aktifkan fitur notify dan allow-transfer ke tedd, lalu set forwarders ke 192.168.122.1. Di node tedd, tarik zona <xxxx>.com dari master dan pastikan server menjawab secara authoritative. Setelah fondasi nama ini berdiri kokoh, perbarui urutan resolver pada seluruh Entitas non-router menjadi: IP prab, IP tedd, lalu 192.168.122.1. Verifikasi bahwa query ke domain apex maupun hostname di dalam zona dijawab dengan benar oleh prab atau tedd.

---

### Konfigurasi

Nama kelompok K-13 dipakai sebagai domain internal: **`k13.com`**. Node prab dipasang BIND9 sebagai master (ns1) dan tedd sebagai slave (ns2) melalui `init_prab.sh` dan `init_tedd.sh` (paket diinstal idempotent, service `named` dijalankan ulang oleh script pada setiap boot).

Zona master pada `/etc/bind/db.k13.com` di prab — SOA menunjuk ke `prab.k13.com`, dua NS, A record prab/tedd, dan apex `k13.com` mengarah ke gerbang penny (10.70.5.2). Serial digenerate otomatis dari waktu saat script berjalan (`date +%Y%m%d%H%M`) agar setiap perubahan isi zona selalu menaikkan serial dan slave ikut menyegarkan:

```
$TTL 300
@   IN SOA prab.k13.com. admin.k13.com. (
        202609280000   ; serial
        3600 300 604800 300 )
    IN NS  prab.k13.com.
    IN NS  tedd.k13.com.
prab     IN A 10.70.1.2
tedd     IN A 10.70.1.3
@        IN A 10.70.5.2
```

Konfigurasi `named.conf` prab: zona bertipe master dengan `notify yes`, `also-notify`/`allow-transfer` ke tedd (10.70.1.3), dan `forwarders` ke 192.168.122.1 (DNS internal NAT GNS3) agar rekursi domain luar tetap berfungsi. `dnssec-validation no` dipakai agar resolusi via forwarder tidak SERVFAIL di dalam lab:

![named conf prab](assets/soal4-namedconfprab.png)

Di tedd, zona bertipe slave dengan `masters { 10.70.1.2; }`. Script init tedd menunggu sampai transfer zona berhasil (SOA serial terjawab) sebelum melaporkan diri siap, sehingga tedd menjawab query zona secara authoritative:

![named conf tedd](assets/soal4-namedconftedd.png)

Setelah fondasi DNS hidup, urutan resolver pada seluruh host non-router diperbarui menjadi prab (10.70.1.2) → tedd (10.70.1.3) → 192.168.122.1 melalui blok `/etc/resolv.conf` pada setiap `init_<node>.sh`:

```
nameserver 10.70.1.2
nameserver 10.70.1.3
nameserver 192.168.122.1
```

### Verifikasi

Query langsung ke prab — apex, A record hostname, NS, dan flag `aa` (authoritative answer):

![dig prab](assets/soal4-digprab.png)

Query ke tedd — zona hasil transfer dijawab authoritative dengan serial SOA yang sama dengan prab:

![dig tedd](assets/soal4-digtedd.png)

Resolusi dari sisi host (alpha) menggunakan urutan resolver baru — `getent hosts k13.com` terjawab oleh prab:

![getent alpha](assets/soal4-getentalpha.png)

Verifikasi otomatis (kode lengkap pada `assets/soal4-verify_soal4.py`) memeriksa seluruh record, flag aa di kedua server, kesamaan serial prab-tedd, forwarders, dan urutan resolv.conf pada 13 host:

![verifikasi soal4](assets/soal4-verifikasi.png)

## Soal 5

> "Entitas tanpa identitas adalah anomali," pesan Rootkit. Namai semua Entitas (hostname) sesuai glosarium: rootkit, alpha, beta, gamma, delta, epsilon, prab, tedd, abbey, penny, obladi, desmond, oblada, molly, dan verifikasi bahwa setiap host mengenali hostname tersebut secara system-wide. Buat setiap domain untuk masing-masing node sesuai dengan namanya (contoh: alpha.<xxxx>.com) dan assign IP masing-masing juga. Lakukan pengecualian untuk node yang bertanggung jawab atas prab dan tedd.

---

### Konfigurasi

Penamaan hostname sudah diberlakukan sejak Soal 1 melalui bagian hostname tiap `init_<node>.sh` (ditulis ke `/etc/hostname` dan `hostname` dijalankan), sehingga setiap node mengenali hostname-nya secara system-wide (`hostname` dan `cat /etc/hostname` mengembalikan nama yang sama).

Domain per-node ditambahkan pada zona `k13.com` di `/etc/bind/db.k13.com` (prab) — 12 A record untuk rootkit, klien sayap kiri/kanan, gerbang, dan repositori. Pengecualian untuk prab dan tedd: A record keduanya sudah dibuat pada Soal 4, sehingga tidak diduplikasi:

```
rootkit  IN A 10.70.1.1
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
```

Karena serial SOA digenerate otomatis dari waktu setiap script berjalan, penambahan record ini otomatis menaikkan serial sehingga notify menyebar dan tedd ikut menarik salinan zona yang baru berisi seluruh domain per-node.

![zone file k13.com](assets/soal5-zonefile.png)

### Verifikasi

Hostname system-wide dicek di setiap node (`hostname` = `cat /etc/hostname` = nama node, contoh pada delta dan desmond):

![hostname delta](assets/soal5-hostnamedelta.png)

Query domain per-node dijawab identik oleh master (prab) maupun slave (tedd) — contoh alpha.k13.com dan rootkit.k13.com:

![dig per-node](assets/soal5-digpernode.png)

Resolusi dari sisi host melalui resolver lokal (contoh delta → oblada.k13.com, alpha → rootkit.k13.com):

![getent host per-node](assets/soal5-getent.png)

Verifikasi otomatis (kode lengkap pada `assets/soal5-verify_soal5.py`) memeriksa hostname 14 node, seluruh 12 domain per-node pada kedua server, dan resolusi sisi host:

![verifikasi soal5](assets/soal5-verifikasi.png)

## Soal 6

> Pastikan zone transfer berjalan, pastikan tedd telah menerima salinan zona terbaru dari prab. Nilai serial SOA di keduanya harus sama karena keduanya tidak bisa dipisahkan dan saling melengkapi.

---

### Konfigurasi

Tidak ada konfigurasi tambahan — mekanisme transfer dibangun pada Soal 4 (`notify yes`, `also-notify { 10.70.1.3; }`, `allow-transfer { 10.70.1.3; }` di prab; `type slave; masters { 10.70.1.2; }` di tedd) dan telah terbukti hidup selama pengerjaan: setiap kali isi zona berubah (penambahan 12 domain per-node pada Soal 5), serial SOA di prab otomatis naik (`2609281153` → `2609281154` → `2609281216`) dan tedd selalu mengambil salinan baru hingga serialnya kembali sama.

Serial SOA keduanya terbaca identik pada saat verifikasi:

![serial match](assets/soal6-serialmatch.png)

### Verifikasi

Bukti transfer yang hidup: query **AXFR** (full zone transfer) dari console tedd ke prab dibolehkan — tedd dapat menarik seluruh isi zona kapan pun karena berada di daftar `allow-transfer`:

![axfr tedd](assets/soal6-axfr.png)

Sebaliknya, AXFR dari pihak lain (contoh: console prab sendiri, dengan source IP selain 10.70.1.3) **ditolak (REFUSED)** — membuktikan allow-transfer terpasang dan hanya tedd yang boleh menarik zona. Salinan hasil transfer juga tersimpan di `/var/cache/bind/db.k13.com` pada tedd.

Keduanya menjawab secara authoritative (flag `aa`) untuk zona yang sama, dan verifikasi otomatis (kode lengkap pada `assets/soal6-verify_soal6.py`) menuntaskan pemeriksaan: kesamaan serial, flag aa, AXFR diperbolehkan/lalu ditolak sesuai letak, keberadaan file zona di tedd, serta parity seluruh 15 A record yang dijawab identik oleh master dan slave:

![verifikasi soal6](assets/soal6-verifikasi.png)






