#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 10.1.0.1


## Redirect wireguard overlay trrafic to the right mapped docker port
iptables -t nat -I PREROUTING -p tcp -i wg-server-a --dport 8080 -j REDIRECT --to-ports 9999
iptables -t nat -I PREROUTING -p tcp -i wg-server-b --dport 8080 -j REDIRECT --to-ports 9998

## Bloc wireguard overlays to reach the docker mapped port directly
iptables -t mangle -I PREROUTING -p tcp --source 10.0.0.0/16 --dport 9998:9999 -j DROP

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

sudo mkdir /etc/wireguard_manager/
sudo mv /home/vagrant/wireguard_configs/*.json /etc/wireguard_manager/


##install docker
cd /home/vagrant
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh ./get-docker.sh

#build image
cd /home/vagrant/server_app
docker build . -t cloud/node-web-app

##run containers
docker run -p 9999:8080 -d cloud/node-web-app
docker run -p 9998:8080 -d cloud/node-web-app

## Install wireguard manager software
sudo apt install -y wireguard python3-pip
cd /home/vagrant/wireguard_manager
pip3 install -r requirements.txt
chmod a+x start.sh
chmod a+x stop.sh

## Run wireguard manager SW
nohup sh start.sh &

