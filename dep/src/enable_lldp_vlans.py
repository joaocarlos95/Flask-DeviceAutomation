import os
import re
import subprocess
import sys
import tempfile
import time

from classes.colors import Colors
from classes.network_handler import NetworkHandler


ROOT_DIR = 'C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation'
CLIENT_NAME = 'ANA Aeroportos'


def open_temp_file_in_text_editor(info):
    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(info)
        # Get the path to the temporary file
        temp_file_path = temp_file.name

    try:
        # Open the temporary file in a text editor or viewer
        if os.name == 'nt':
            os.startfile(temp_file_path)  # For Windows
        elif os.name == 'posix':
            subprocess.run(['xdg-open', temp_file_path])  # For Linux

        # Wait for the user to close the editor, choosing the right answer (Yes or No)
        
        validations = {'yes': True, 'y': True, 'no': False, 'n': False}
        while True:
            print(f"{Colors.OK_YELLOW}[>]{Colors.END} Please confirm the devices being intervencioned (Yes or No).")
            try:
                if validations[input(f"    {Colors.WHITE_UNDER}Answer{Colors.END}: ").lower()]: break
                else:
                    print(f"{Colors.NOK_RED}[>]{Colors.END} Please choose the correct devices.")
                    sys.exit()
            except KeyError:
                continue

    finally:
        # Clean up: Delete the temporary file
        try:
            os.remove(temp_file_path)
        except Exception as e:
            print("Failed to delete temporary file:", e)

def get_ports_by_vlan(device_list: list, output_parsed: dict, vlan_list: list) -> dict:
    '''
    For each device, get the ports that belong to a given VLAN
    '''

    def interface_key(interface):
        parts = interface.split(":")
        return tuple(map(int, parts))

    device_ports = {}
    for entry in output_parsed:
        # Creat e new key in the dictionary relative to the device, if it doesn't exist already
        if entry['device_ip_address'] not in device_ports.keys():
            device_ports[entry['device_ip_address']] = {"enabled_ports": []}
            # device_ports[entry['device_ip_address']] = {"enabled_ports": [], "disabled_ports": []}
            vlans = []
            vlans.extend([vlan_id for vlan_id in entry.get('vlan', []) if vlan_id])
            vlans.extend([vlan_id for vlan_ids in entry.get('tagged_vlan', []) for vlan_id in vlan_ids.split(',') if vlan_id])
            vlans.extend([vlan_id for vlan_ids in entry.get('untagged_vlan', []) for vlan_id in vlan_ids.split(',') if vlan_id])
            for vlan in vlans:
                if vlan in vlan_list:
                    device_ports[entry['device_ip_address']]['enabled_ports'].append(entry['port'])
                # else:
                #     device_ports[entry['device_ip_address']]['disabled_ports'].append(entry['port'])
        else:
            vlans = []
            vlans.extend([vlan_id for vlan_id in entry.get('vlan', []) if vlan_id])
            vlans.extend([vlan_id for vlan_ids in entry.get('tagged_vlan', []) for vlan_id in vlan_ids.split(',') if vlan_id])
            vlans.extend([vlan_id for vlan_ids in entry.get('untagged_vlan', []) for vlan_id in vlan_ids.split(',') if vlan_id])
            for vlan in vlans:
                if vlan in vlan_list:
                    device_ports[entry['device_ip_address']]['enabled_ports'].append(entry['port'])
                # else:
                #     device_ports[entry['device_ip_address']]['disabled_ports'].append(entry['port'])

    for key, value in device_ports.items():
        enabled_ports = list(set(value['enabled_ports']))
        # disabled_ports = list(set(value['disabled_ports']))
        device_ports[key]['enabled_ports'] = enabled_ports#sorted(enabled_ports, key=interface_key)
        # device_ports[key]['disabled_ports'] = sorted([x for x in disabled_ports if x not in enabled_ports], key=interface_key)

    return device_ports

if __name__ == '__main__':

    start_time = time.time()

    # Create a new client object
    client = Client(ROOT_DIR, CLIENT_NAME)

    # Initialize all data (command list) and get device information for each information requested
    client.get_devices_from_csv()
    client.get_commands()
    client.get_concurrent_configs(get_configs_info=['VLAN Ports'])

    # Generate script data, converting all class objects to nested dicts
    script_data = client.generate_data_dict()
    output_parsed = client.generate_config_parsed(script_data)

    while True:
        print(f"{Colors.OK_YELLOW}[>]{Colors.END} Please provide the VLAN IDs in order to find the ports for the LLDP, separated by comma. Only numbers are allowed.")
        try:
            answer = input(f"    {Colors.WHITE_UNDER}Answer{Colors.END}: ").lower()
            vlan_list = re.findall(r'[^,\s]+', answer)
            if all(isinstance(int(item), int) for item in vlan_list): break
            else: continue
        except KeyError:
            continue
        except ValueError:
            continue

    # Get the ports that belong to a given VLAN
    device_ports = get_ports_by_vlan(client.device_list, output_parsed['VLAN Ports'], vlan_list)
    print(device_ports)

    # Initialize all data (templates, templates data)
    client.get_j2_template()
    client.get_j2_data()

    for key, value in device_ports.items():
        device_ports[key] = {'lldp': {**client.j2_data['lldp'], **value}}

    # ADD CONCURRENCY TO THIS LAST PART
    for device_obj in client.device_list:
        config = device_obj.set_configs(config_blocks=['lldp'], j2_data=device_ports[device_obj.ip_address])