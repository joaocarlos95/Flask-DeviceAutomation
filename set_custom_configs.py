# -*- coding: UTF-8 -*-

import os
import sys
import time
from getpass import getpass
from multiprocessing import Manager, Process
from classes.client import Client
from classes.colors import Colors


def raise_exception(exception: str) -> None:
    sys.exit(f"{Colors.NOK_RED} {exception}")

ROOT_DIR = 'C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation'
CLIENT_NAME = 'ANA Aeroportos'
CONFIG = {
    '192.168.75.100': """
        set system lockout emergency-access VinciAdmin
        set system login admin super-user disable
        set system login ro read-only disable
        set system login rw read-write disable
        clear system login meoadmin
    """,
}

if __name__ == '__main__':
    start_time = time.time()
    validations = {'yes': True, 'y': True, 'no': False, 'n': False}

    # Create a new client object
    client = Client(ROOT_DIR, CLIENT_NAME)
    client.get_devices_from_csv()

    # Initialize all data (templates, templates data)
    client.get_j2_template()
    client.get_j2_data()

    for device in client.device_list:
        device.j2_data = None
        device.set_configs(config_blocks=["Custom"], config=CONFIG["192.168.75.100"])

    
    # # Get device information for each information requested
    # client.set_concurrent_configs(config_blocks=config_blocks)

    # # # Generate script data, converting all class objects to nested dicts
    # # script_data = client.generate_data_dict()
    # # output_parsed_dict = client.generate_config_parsed(script_data)

    print(f"Execution time: {time.time() - start_time} seconds")
