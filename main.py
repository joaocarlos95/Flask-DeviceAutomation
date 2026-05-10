import os
import pathlib
import time
import yaml
from collections import defaultdict
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response
from nornir.core.filter import F

from dep.panda.classes.network_handler import NetworkHandler
from dep.panda.classes.colors import Colors
from dep.panda.classes.netbox import Netbox


load_dotenv()


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_INVENTORY_DIRECTORY = PROJECT_ROOT / "inputfiles" / "inventory"


def normalize_inventory_directory(path_value: str | None = None) -> str:
    inventory_path = pathlib.Path(path_value).expanduser() if path_value else DEFAULT_INVENTORY_DIRECTORY

    if (inventory_path / "inputfiles" / "inventory").is_dir():
        inventory_path = inventory_path / "inputfiles" / "inventory"

    return str(inventory_path)


ROOT_DIRECTORY = normalize_inventory_directory(
    os.getenv("inventory_directory") or os.getenv("INVENTORY_DIRECTORY") or os.getenv("root_directory")
)
NETBOX_URL = os.getenv('netbox_url') or os.getenv('NETBOX_URL') or ''
NETBOX_TOKEN = os.getenv('netbox_token') or os.getenv('NETBOX_TOKEN') or ''
TARGET_SOURCE_INVENTORY = "inventory"
TARGET_SOURCE_NETBOX = "netbox"
VALID_TARGET_SOURCES = {TARGET_SOURCE_INVENTORY, TARGET_SOURCE_NETBOX}
CONFIG_OPTIONS = {
    'set_configs': {
        'Authentication': [
            {'id': 'Device Management', 'name': 'Device Management', 'label': 'Management', 'status': ''},
            {'id': 'TACACS', 'name': 'TACACS', 'label': 'TACACS+', 'status': ''},
        ],
        'VLAN': [
            {'id': 'VLAN', 'name': 'VLAN', 'label': 'VLAN', 'status': ''},
        ],
        'Interfaces': [
            {'id': 'Ports', 'name': 'Ports', 'label': 'Ports', 'status': ''},
        ],
        'Discovery Protocols': [
            {'id': 'CDP', 'name': 'CDP', 'label': 'CDP', 'status': ''},
            {'id': 'LLDP', 'name': 'LLDP', 'label': 'LLDP', 'status': ''},
        ],
        'Monitoring': [
            {'id': 'SNMP', 'name': 'SNMP', 'label': 'SNMP', 'status': ''},
        ],
        'Others': [
            {'id': 'General', 'name': 'General', 'label': 'General', 'status': ''},
        ]
    }
}


app = Flask(__name__, template_folder='web/templates', static_folder='web/static')


def get_template_context() -> dict:
    return {
        'inventory_directory': ROOT_DIRECTORY,
        'root_directory': ROOT_DIRECTORY,
        'netbox_url': NETBOX_URL,
    }


def normalize_target_source(source: str | None) -> str:
    if source in VALID_TARGET_SOURCES:
        return source
    return TARGET_SOURCE_INVENTORY


@app.route('/')
def index():
    return render_template('index.html', **get_template_context())

@app.route('/get_configs')
def get_configs():
    target_source = normalize_target_source(request.args.get('target_source'))
    target_options = get_target_options(target_source)

    return render_template(
        'get_configs.html',
        config_options=CONFIG_OPTIONS['get_configs'],
        device_groups=target_options['device_groups'],
        inventory_hosts=target_options['inventory_hosts'],
        group_devices=target_options['group_devices'],
        target_source=target_options['source'],
        target_source_error=target_options.get('error', ''),
        **get_template_context()
    )

@app.route('/set_configs')
def set_configs():
    return render_template('set_configs.html', config_options=CONFIG_OPTIONS['set_configs'], device_groups=NETWORK_HANDLER.nornir.inventory.groups, **get_template_context())

@app.route('/generate_configs')
def generate_configs():
    return render_template('generate_configs.html', config_options=CONFIG_OPTIONS['set_configs'], **get_template_context())

@app.route('/update_netbox')
def update_netbox():
    return render_template('update_netbox.html', config_options=CONFIG_OPTIONS['upd_netbox'], device_groups=NETWORK_HANDLER.nornir.inventory.groups, **get_template_context())


@app.route('/target_options')
def target_options():
    target_source = normalize_target_source(request.args.get('source'))
    options = get_target_options(target_source)

    if options.get('error'):
        return jsonify(options), 400

    return jsonify(options)


@app.route('/browse_folders')
def browse_folders():
    requested_path = request.args.get('path') or ROOT_DIRECTORY
    folder_path = pathlib.Path(requested_path).expanduser()

    try:
        folder_path = folder_path.resolve()
        folders = [
            {
                'name': child.name,
                'path': str(child),
                'hasInventoryFiles': all(
                    (child / filename).exists()
                    for filename in ["defaults.yaml", "groups.yaml", "hosts.yaml"]
                ),
            }
            for child in folder_path.iterdir()
            if child.is_dir() and not child.name.startswith('.')
        ]
    except (OSError, RuntimeError):
        return jsonify(error='Could not open that folder.'), 400

    folders.sort(key=lambda item: item['name'].lower())

    return jsonify({
        'currentPath': str(folder_path),
        'parentPath': str(folder_path.parent) if folder_path.parent != folder_path else '',
        'hasInventoryFiles': all(
            (folder_path / filename).exists()
            for filename in ["defaults.yaml", "groups.yaml", "hosts.yaml"]
        ),
        'folders': folders,
    })

@app.route('/update_device_group_options', methods=['POST'])
def update_device_group_options():
    global CONFIG_OPTIONS
    CONFIG_OPTIONS['device_group'] = request.json.get('device_group_options')
    return jsonify(success=True)

@app.route('/update_root_directory', methods=['POST'])
def update_root_directory():
    global ROOT_DIRECTORY
    ROOT_DIRECTORY = normalize_inventory_directory(request.form.get('root_directory'))
    return ROOT_DIRECTORY


@app.route('/target_settings', methods=['POST'])
def target_settings():
    global ROOT_DIRECTORY, NETBOX_URL, NETBOX_TOKEN

    settings = request.get_json() or {}
    root_directory = settings.get('rootDirectory')
    netbox_url = settings.get('netboxUrl')
    netbox_token = settings.get('netboxToken')

    if root_directory is not None and root_directory.strip():
        ROOT_DIRECTORY = normalize_inventory_directory(root_directory.strip())
        init_network_handler()

    if netbox_url is not None:
        NETBOX_URL = netbox_url.strip()

    if netbox_token:
        NETBOX_TOKEN = netbox_token.strip()

    return jsonify(success=True)


def get_target_options(source: str) -> dict:
    if source == TARGET_SOURCE_NETBOX:
        return get_netbox_targets_for_template()

    inventory_hosts, group_devices = get_inventory_hosts_for_template()
    device_groups = {group_name: {} for group_name in sorted(group_devices.keys())}

    if not device_groups:
        device_groups = {group_name: {} for group_name in NETWORK_HANDLER.nornir.inventory.groups.keys()}

    return {
        'source': TARGET_SOURCE_INVENTORY,
        'device_groups': device_groups,
        'inventory_hosts': inventory_hosts,
        'group_devices': group_devices,
    }


def get_inventory_hosts_for_template() -> tuple[list[dict], dict[str, list[str]]]:
    hosts_file = f"{ROOT_DIRECTORY}/hosts.yaml"
    inventory_hosts = []
    group_devices = defaultdict(list)
    network_handler = globals().get('NETWORK_HANDLER')

    if network_handler and network_handler.nornir.inventory.hosts:
        for host_name, host in network_handler.nornir.inventory.hosts.items():
            host_groups = [group.name for group in host.groups]

            inventory_hosts.append({
                'name': host_name,
                'hostname': host.hostname or '',
                'groups': host_groups,
            })

            for group_name in host_groups:
                group_devices[group_name].append(host_name)

        return sorted_hosts(inventory_hosts), sort_group_devices(group_devices)

    if not os.path.exists(hosts_file):
        return inventory_hosts, {}

    with open(hosts_file, 'r') as hosts_data:
        hosts = yaml.safe_load(hosts_data) or {}

    for host_name, host_data in hosts.items():
        host_data = host_data or {}
        host_groups = host_data.get('groups') or []

        inventory_hosts.append({
            'name': host_name,
            'hostname': host_data.get('hostname', ''),
            'groups': host_groups,
        })

        for group_name in host_groups:
            group_devices[group_name].append(host_name)

    return sorted_hosts(inventory_hosts), sort_group_devices(group_devices)


def get_netbox_targets_for_template() -> dict:
    if not NETBOX_URL or not NETBOX_TOKEN:
        return {
            'source': TARGET_SOURCE_NETBOX,
            'device_groups': {},
            'inventory_hosts': [],
            'group_devices': {},
            'error': 'NetBox URL/token are not configured.',
        }

    netbox = Netbox(NETBOX_URL.rstrip('/'), NETBOX_TOKEN)

    try:
        response = netbox.get_request('/dcim/devices/', params={'limit': 0})
    except Exception as exception:
        return {
            'source': TARGET_SOURCE_NETBOX,
            'device_groups': {},
            'inventory_hosts': [],
            'group_devices': {},
            'error': f'Could not load NetBox devices: {exception}',
        }

    if not response:
        return {
            'source': TARGET_SOURCE_NETBOX,
            'device_groups': {},
            'inventory_hosts': [],
            'group_devices': {},
            'error': 'NetBox did not return device data.',
        }

    inventory_hosts = []
    group_devices = defaultdict(list)

    for device in response.get('results', []):
        device_name = device.get('name') or device.get('display') or ''

        if not device_name:
            continue

        site = device.get('site') or {}
        role = device.get('role') or {}
        platform = device.get('platform') or {}
        primary_ip = device.get('primary_ip4') or device.get('primary_ip') or {}
        host_groups = []

        for group_name in [
            site.get('name'),
            role.get('name'),
            platform.get('name'),
        ]:
            if group_name and group_name not in host_groups:
                host_groups.append(group_name)

        if not host_groups:
            host_groups.append('NetBox devices')

        inventory_hosts.append({
            'name': device_name,
            'hostname': normalize_netbox_ip(primary_ip.get('address', '')),
            'groups': host_groups,
        })

        for group_name in host_groups:
            group_devices[group_name].append(device_name)

    group_devices = sort_group_devices(group_devices)

    return {
        'source': TARGET_SOURCE_NETBOX,
        'device_groups': {group_name: {} for group_name in group_devices.keys()},
        'inventory_hosts': sorted_hosts(inventory_hosts),
        'group_devices': group_devices,
    }


def normalize_netbox_ip(address: str) -> str:
    return address.split('/')[0] if address else ''


def sorted_hosts(hosts: list[dict]) -> list[dict]:
    return sorted(hosts, key=lambda host: host['name'])


def sort_group_devices(group_devices: defaultdict | dict) -> dict[str, list[str]]:
    return {
        group_name: sorted(devices)
        for group_name, devices in sorted(group_devices.items())
    }


# def get_checked_options(method: str):
#     checked_options = []
#     for category, options in CONFIG_OPTIONS[method].items():
#         for option in options:
#             if option['status'] == 'checked' and method == 'get_configs':
#                 checked_options.append(option['id'])
#             elif option['status'] == 'checked' and method == 'set_configs':
#                 checked_options.append(option['id'])

#     return checked_options


@app.route('/run_get_configs', methods=['POST'])
def run_get_configs():
    start_time = time.time()

    selected_data = request.get_json() or {}
    get_configs_info = selected_data.get('informationDataSelected', [])
    nornir_target_filter = build_nornir_target_filter(
        selected_groups=selected_data.get('selectedDeviceGroups', []),
        selected_devices=selected_data.get('selectedDevices', [])
    )

    if not get_configs_info:
        return jsonify(error='No information data selected.'), 400

    if not nornir_target_filter:
        return jsonify(error='No device groups or devices selected.'), 400

    nornir_filtered = NETWORK_HANDLER.nornir.filter(nornir_target_filter)
    NETWORK_HANDLER.nornir_get_configs(get_configs_info=get_configs_info, nornir_filtered=nornir_filtered)

    script_data = NETWORK_HANDLER.nornir_generate_data_dict()
    output_parsed = NETWORK_HANDLER.nornir_generate_config_parsed(script_data)

    # Generate diagrams using CDP or LLDP neighbors
    # if 'Network Diagram CDP' in get_configs_info:
    #     graph = NETWORK_HANDLER.generate_graph(output_parsed=output_parsed, discovery_protocol='CDP')
    #     NETWORK_HANDLER.generate_diagram(graph)
    # elif 'Network Diagram LLDP' in get_configs_info:
    #     graph = NETWORK_HANDLER.generate_graph(output_parsed=output_parsed, discovery_protocol='LLDP')
    #     NETWORK_HANDLER.generate_diagram(graph)
    
    print(f"{Colors.OK_GREEN}[>]{Colors.END} Execution time: {time.time() - start_time} seconds")
    return Response(status=204)


def build_nornir_target_filter(selected_groups: list[str], selected_devices: list[str]):
    nornir_target_filter = None

    for group in selected_groups:
        group_filter = F(groups__contains=group)
        nornir_target_filter = group_filter if nornir_target_filter is None else nornir_target_filter | group_filter

    for device in selected_devices:
        device_filter = F(name=device)
        nornir_target_filter = device_filter if nornir_target_filter is None else nornir_target_filter | device_filter

    return nornir_target_filter


@app.route('/run_set_configs', methods=['POST'])
def run_set_configs():
    start_time = time.time()

    selected_data = request.get_json()
    set_configs_info = selected_data['informationDataSelected']

    selected_groups = selected_data['selectedDeviceGroups']
    nornir_group_filter = F(groups__contains=selected_groups[0])
    for group in selected_groups[1:]:
        nornir_group_filter |= F(groups__contains=group)

    nornir_filtered = NETWORK_HANDLER.nornir.filter(nornir_group_filter)

    NETWORK_HANDLER.nornir_generate_configs(nornir_filtered=nornir_filtered, set_configs_info=set_configs_info)
    NETWORK_HANDLER.nornir_set_configs(nornir_filtered=nornir_filtered)

    # Generate script data, converting all class objects to nested dicts
    # script_data = NETWORK_HANDLER.generate_data_dict()
    # output_parsed = NETWORK_HANDLER.generate_config_parsed(script_data)

    print(f"{Colors.OK_GREEN}[>]{Colors.END} Execution time: {time.time() - start_time} seconds")
    return Response(status=204)


def init_config_options() -> None:
    '''
    Initialize global CONFIG_OPTIONS with the configuration options
    from the config.yaml file. This function is used to populate the website
    with the available options.

    The options are grouped by their respective group, which is defined in the
    config.yaml file.
    '''

    global CONFIG_OPTIONS

    with open(f"{os.path.dirname(__file__)}/dep/panda/config.yaml", 'r') as nornir_config:
        config = yaml.safe_load(nornir_config)

        get_configs = defaultdict(list)
        # Iterate through all the user-defined options in the config.yaml file, specifically for the PANDA
        for key, value in config['user_defined']['device_data'].items():
            # Append the current option to the corresponding group
            get_configs[value['group']].append({
                'id': key,
                'name': key,
                'label': value['label'],
                'status': value['status']
            })

        upd_netbox = defaultdict(list)
        # Iterate through all the user-defined options in the config.yaml file, specifically for the Netbox
        for key, value in config['user_defined']['device_data'].items():
            # Append the current option to the corresponding group
            upd_netbox[value['group']].append({
                'id': key,
                'name': key,
                'label': value['label'],
                'status': value['status'],
            })

    CONFIG_OPTIONS['get_configs'] = dict(get_configs)
    CONFIG_OPTIONS['upd_netbox'] = dict(upd_netbox)


def init_network_handler() -> None:
    ''' '''
    global NETWORK_HANDLER

    hosts = None
    groups = None
    defaults = None

    if os.path.exists(f"{ROOT_DIRECTORY}/hosts.yaml"):
        hosts = f"{ROOT_DIRECTORY}/hosts.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/groups.yaml"):
        groups = f"{ROOT_DIRECTORY}/groups.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/defaults.yaml"):
        defaults = f"{ROOT_DIRECTORY}/defaults.yaml"

    NETWORK_HANDLER = NetworkHandler(host_file=hosts, group_file=groups, defaults_file=defaults)
    NETWORK_HANDLER.dir = ROOT_DIRECTORY


def init_netbox() -> None:
    ''' '''
    global NETBOX

    url = None
    token = None

    NETBOX = Netbox(url, token)


def update_netbox_device(site, output_parsed) -> None:

    device_model_db = NETWORK_HANDLER.nornir.config.user_defined['models_database']
    for get_configs_info_result in output_parsed.values():
        for command_result in get_configs_info_result.values():
            for device in command_result:
                try:
                    model = device['hardware'][0]
                    if model not in device_model_db.keys():
                        print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device model {model} not found in the models_database")
                        continue
                    # Add new device to Netbox
                    NETBOX.add_device(
                        role=device_model_db[model]['role'],
                        model=model,
                        site=site,
                        hostname=device['device_hostname'],
                        serial_number=device['serial_number'][0]
                    )

                except Exception as exception:
                    # If device type doesn't exist in Netbox, create it and add again the device     
                    if "Device type doesn't exist" in str(exception):         
                        NETBOX.add_device_type(
                            manufacturer=device_model_db[model]['manufacturer'],
                            model=model,
                            u_height=device_model_db[model]['u_height'],
                            is_full_depth=device_model_db[model]['is_full_depth'],
                            platform=device_model_db[model]['platform']
                        )
                        NETBOX.add_device(
                            role=device_model_db[model]['role'],
                            model=model,
                            site=site,
                            hostname=device['device_hostname'],
                            serial_number=device['serial_number'][0]
                        )
                    else:
                        print(exception)

def add_device_netbox(site:str, model:str, hostname:str, serial_number:str) -> None:

    device_model_db = NETWORK_HANDLER.nornir.config.user_defined['models_database'][model]
    data = {
        "role": NETBOX.get_device_role_id(device_model_db['role']),
        "manufacturer": device_model_db['manufacturer'],
        "device_type": NETBOX.get_device_type_id(model),
        "status": "active",
        "site": NETBOX.get_site_id(site),
        "name": hostname,
        "serial": serial_number,
    }
    NETBOX.add_device(data)

def add_device_type_netbox(site:str, model:str, hostname:str, serial_number:str) -> None:

    device_model_db = NETWORK_HANDLER.nornir.config.user_defined['models_database'][model]
    data = {
        "role": NETBOX.get_device_role_id(device_model_db['role']),
        "manufacturer": device_model_db['manufacturer'],
        "device_type": NETBOX.get_device_type_id(model),
        "status": "active",
        "site": NETBOX.get_site_id(site),
        "name": hostname,
        "serial": serial_number,
    }
    NETBOX.add_device(data)


def main():

    init_config_options()
    init_network_handler()

    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)


if __name__ == "__main__":
    main()
