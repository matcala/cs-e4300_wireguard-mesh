#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 10.1.0.1

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

## Install app
cd /home/vagrant/client_app
npm install

##edit config file to server's virtual network

sudo apt update
sudo apt install -y wireguard

cd /home/vagrant/wireguard_manager