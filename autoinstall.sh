#!/bin/bash
apt update
apt upgrade -y
apt install mariadb-server -y

MYSQL_ROOT_PASSWORD="your_new_root_password"

mysql -u root <<EOF
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
FLUSH PRIVILEGES;
EOF

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" < SCRIPT.sql

apt install python3-pip -y
mkdir ~/.config
mkdir ~/.config/pip

cat > ~/.config/pip/pip.conf <<'EOF'
[global]
break-system-packages = true
user = true
EOF

pip3 install -r requirements.txt
