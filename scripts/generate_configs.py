# -*- coding: UTF-8 -*-

import sys
import time
from getpass import getpass
from multiprocessing import Manager, Process
from classes.network_handler import NetworkHandler
from classes.device import Device
from classes.colors import Colors


ROOT_DIR = 'C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation'
CLIENT_NAME = 'ANA Aeroportos'
VENDOR_OS = 'extreme_exos'
CONFIG_BLOCKS = [
    'general',
    'vlan',
    'device_management',
    'port',
    'tacacs',
    'radius',
    'snmp',
    'cdp',
    'lldp',
    'syslog',
    'ntp',
    'spanning-tree',
    # 'dot1x',
    #'stacking',
    #'igmp'
]


def raise_exception(exception: str) -> None:
    sys.exit(f"{Colors.NOK_RED} {exception}")


if __name__ == '__main__':
    start_time = time.time()

    # Create a new client object and a new device object
    client = Client(ROOT_DIR, CLIENT_NAME)
    client.device_list = [Device(client, VENDOR_OS, ip_address=None, credentials=None)]

    # Initialize all data (templates, templates data)
    client.get_j2_template()
    client.get_j2_data()
    
    # Get device information for each information requested
    client.generate_concurrent_configs(config_blocks=CONFIG_BLOCKS)
    
    # # Generate script data, converting all class objects to nested dicts
    # script_data = client.generate_data_dict()
    # output_parsed_dict = client.generate_config_parsed(script_data)

    print(f"Execution time: {time.time() - start_time} seconds")
