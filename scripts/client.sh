#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 10.1.0.1

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6


sudo mkdir /etc/wireguard_manager/
sudo mv /home/vagrant/wireguard_configs/*.json /etc/wireguard_manager/
## Install app
cd /home/vagrant/client_app
npm install

cat << EOF > config.json
{
  "server_ip": "$1",
  "server_port": "8080",
  "log_file": "/var/log/client.log"
}
EOF

## Install wireguard manager software
sudo apt update
sudo apt install -y wireguard python3-pip
cd /home/vagrant/wireguard_manager
pip3 install -r requirements.txt
chmod a+x start.sh
chmod a+x stop.sh

## Run wireguard manager SW
nohup sh start.sh &
