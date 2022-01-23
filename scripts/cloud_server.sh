#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 10.1.0.1

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6


##install docker
#cd /home/vagrant
#curl -fsSL https://get.docker.com -o get-docker.sh
#sudo sh ./get-docker.sh

##build image
#cd /home/vagrant/server_app
#docker build . -t cloud/node-web-app

##run containers
#docker run -p 9999:8080 -d cloud/node-web-app
#docker run -p 9998:8080 -d cloud/node-web-app

## Install wireguard manager software
sudo apt update
sudo apt install -y wireguard
sudo apt install -y python3-pip
cd /home/vagrant/wireguard_manager
pip3 install -r requirements.txt
chmod a+x start.sh
chmod a+x stop.sh

## Run wireguard manager as a service
cat << EOF > /etc/systemd/system/wg_manager.service
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


##TODO ensure creation of interfaces before plugin to the docket containers