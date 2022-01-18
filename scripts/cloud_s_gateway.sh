#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 172.30.30.1

## Outbound NAT
iptables -t nat -A POSTROUTING -o enp0s8 -j MASQUERADE

## FULL CONE TO SERVER
iptables -t nat -A PREROUTING --source 172.16.16.16 -j DNAT --to-destination 10.1.0.2
iptables -t nat -A PREROUTING --source 172.18.18.18 -j DNAT --to-destination 10.1.0.2

## Iptables rules
#iptables -A INPUT -i enp0s3 -j ACCEPT                                   #Accept vagrant ssh trrafic from enp0s3
#iptables -A INPUT -i enp0s9 --source 10.1.0.0/16 -j ACCEPT              #ACCEPT internal trrafic from enp0s9
#iptables -P INPUT DROP                                                  #DROP everything else policy

##TODO add port forwarding for vpn trrafic

## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

