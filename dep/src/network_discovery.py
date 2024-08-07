# -*- coding: UTF-8 -*-

import ipaddress
import time

from netmiko.ssh_autodetect import SSHDetect
from netmiko.snmp_autodetect import SNMPDetect

import sys

def ssh_device_detect(ip_address, username, password):

    device = {
        'device_type': 'autodetect',
        'host': ip_address,
        'username': username,
        'password': password
    }

    guesser = SSHDetect(**device)
    best_match = guesser.autodetect()
    print(best_match)
    print(guesser.potential_matches)
    return best_match


def snmp_device_detect(ip_address, username, auth_key, auth_proto, encrypt_key, encrypt_proto):

    my_snmp = SNMPDetect(
        ip_address,
        snmp_version="v3",
        user=username,
        auth_key=auth_key,
        encrypt_key=encrypt_key,
        auth_proto=auth_proto,
        encrypt_proto=encrypt_proto,
    )
    device_type = my_snmp.autodetect()
    print(device_type)


if __name__ == '__main__':
    start_time = time.time()

    network_range = "192.168.75.100/24"
    ip_range = ipaddress.ip_network(network_range)

    for ip_address in ip_range:
        ssh_device_detect(ip_address, 'admin', '')
        snmp_device_detect(ip_address, 'ANAuser', 'ANApassword', 'md5', 'ANApassword', 'des')
    
    print(f"Execution time: {time.time() - start_time} seconds")
