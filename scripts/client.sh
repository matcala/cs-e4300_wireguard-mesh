#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 10.1.0.1

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

## Install app
cd /home/vagrant/client_app
npm install

## TODO edit config file to server's virtual network


## Install wireguard manager software
sudo apt update
sudo apt install -y wireguard
sudo apt install -y python3-pip
pip3 install -r requirements.txt
cd /home/vagrant/wireguard_manager
chmod a+x start.sh
chmod a+x stop.sh


cat << EOF > /home/vagrant/client_app/config.json
{
  "server_ip": $1,
  "server_port": "8080",
  "log_file": "/var/log/client.log"
}
EOF

## Run wireguard manager as a service
cat << EOF > etc/systemd/system/wg_manager.service
[Unit]
Description=wg_manager service
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash /home/vagrant/wireguard_manager/start.sh
ExecStop=/bin/bash /home/vagrant/wireguard_manager/stop.sh
Restart=always
RestartSec=5
TimeoutSec=60
RuntimeMaxSec=infinity
PIDFile=/tmp/wg_manager.pid

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable /etc/systemd/system/wg_manager.service
sudo systemctl daemon-reload
sudo service wg_manager start