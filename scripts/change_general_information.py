import csv
import os
import sys
from nornir.core.filter import F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from classes.network_handler import NetworkHandler
from dep.j2_templates.classes.templater import Templater

ROOT_DIRECTORY = "C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation"


def get_general_information_from_csv(file_path: str) -> dict:

    with open(file_path, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        device_list = {}
        for row in csv_reader:
            ip_address = row['ip_address']
            del row['ip_address']
            device_list[ip_address] = {
                'general': row
            }

    return device_list

def init_network_handler() -> None:
    ''' '''
    global NETWORK_HANDLER

    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/hosts.yaml"):
        hosts = f"{ROOT_DIRECTORY}/inputfiles/inventory/hosts.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/groups.yaml"):
        groups = f"{ROOT_DIRECTORY}/inputfiles/inventory/groups.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/defaults.yaml"):
        defaults = f"{ROOT_DIRECTORY}/inputfiles/inventory/defaults.yaml"

    NETWORK_HANDLER = NetworkHandler(host_file=hosts, group_file=groups, defaults_file=defaults)
    NETWORK_HANDLER.dir = ROOT_DIRECTORY

def nornir_filter_by_ip_list(device_list: list):

    nornir_group_filter = F(hostname__in=device_list)
    nornir_filtered = NETWORK_HANDLER.nornir.filter(nornir_group_filter)
    return nornir_filtered


def generate_config(nornir_filtered, device_data_list) -> dict:

    device_config_list = {}
    for device in nornir_filtered.inventory.hosts.values():

        templater = Templater(vendor_os=device.platform, config_blocks=['general'])
        j2_template = templater.get_j2_template()
        j2_data = device_data_list[device.hostname]

        config = templater.render_config(j2_template=j2_template, j2_data=j2_data, hostname=device.hostname)
        device_config_list[device.hostname] = config

    return device_config_list

def main():

    csv_file = f"{ROOT_DIRECTORY}/inputfiles/change_general_information.csv"
    device_list_info = get_general_information_from_csv(csv_file)

    init_network_handler()
    nornir_filtered = nornir_filter_by_ip_list(list(device_list_info.keys()))
    device_config_list = generate_config(nornir_filtered, device_list_info)
    NETWORK_HANDLER.nornir_set_configs(nornir_filtered=nornir_filtered, device_config_list=device_config_list)

if __name__ == '__main__':
    main()