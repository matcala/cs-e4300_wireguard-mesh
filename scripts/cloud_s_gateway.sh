#!/usr/bin/env bash

## Traffic going to the internet
route add default gw 172.30.30.1

## Outbound NAT
iptables -t nat -A POSTROUTING -o enp0s8 -j MASQUERADE

## FULL CONE TO SERVER
iptables -t nat -A PREROUTING -p udp --source 172.16.16.16 --dport 51280 -j DNAT --to-destination 10.1.0.2
iptables -t nat -A PREROUTING -p udp --source 172.18.18.18 --dport 51281 -j DNAT --to-destination 10.1.0.2

## Iptables rules
iptables -A INPUT -i enp0s3 -j ACCEPT                         #ACCEPT vagrant ssh trrafic from enp0s3
iptables -A INPUT -p udp --dport 51280 -j ACCEPT              #ACCEPT wireguard trrafic
iptables -A INPUT -p udp --dport 51281 -j ACCEPT              #ACCEPT wireguard trrafic
iptables -P INPUT DROP                                        #DROP everything else policy


## Save the iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

