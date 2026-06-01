import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from classes.network_handler import NetworkHandler
from dep.j2_templates.classes.templater import Templater

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))
ROOT_DIRECTORY = os.getenv("root_directory") or BASE_DIR


def init_network_handler() -> None:
    ''' '''
    global NETWORK_HANDLER

    NETWORK_HANDLER = NetworkHandler(
        host_file=os.path.join(ROOT_DIRECTORY, "inputfiles", "inventory", "hosts.yaml"), 
        group_file=os.path.join(ROOT_DIRECTORY, "inputfiles", "inventory", "groups.yaml"), 
        defaults_file=os.path.join(ROOT_DIRECTORY, "inputfiles", "inventory", "defaults.yaml")
    )
    NETWORK_HANDLER.dir = ROOT_DIRECTORY


if __name__ == '__main__':

    start_time = time.time()

    init_network_handler()

    platform = 'extreme_exos'

    templater = Templater(vendor_os=platform, config_blocks=['ntp'])
    j2_template = templater.get_j2_template()
    j2_data = templater.get_j2_data_from_file(os.path.join(ROOT_DIRECTORY, "inputfiles", "configs", "defaults.yaml"))

    device_config_list = {}
    nornir_filtered = NETWORK_HANDLER.get_device_filtered(platform=platform)
    for host in nornir_filtered.inventory.hosts.values():
        j2_data['tacacs']['mgmt_ip_addr'] = host.hostname
        device_config_list[host.hostname] = templater.render_config(j2_template, j2_data, hostname=host.name)

    NETWORK_HANDLER.nornir_set_configs(device_config_list, nornir_filtered)