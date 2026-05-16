import os
import pathlib
import time
import warnings
import yaml
from collections import defaultdict
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response
from nornir.core.filter import F
from nornir.core.configuration import ConflictingConfigurationWarning

from classes.network_handler import NetworkHandler
from classes.colors import Colors
from classes.netbox import Netbox

warnings.filterwarnings("ignore", category=ConflictingConfigurationWarning)

load_dotenv()

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
TARGET_SOURCE_INVENTORY = "inventory"
TARGET_SOURCE_NETBOX = "netbox"
VALID_TARGET_SOURCES = {TARGET_SOURCE_INVENTORY, TARGET_SOURCE_NETBOX}


app = Flask(__name__, template_folder='web/templates', static_folder='web/static')


def resolve_env_value(primary_key: str, secondary_key: str, default_value: pathlib.Path | str) -> str:
    return os.getenv(primary_key) or os.getenv(secondary_key) or str(default_value)

def get_config_file() -> str:
    value = app.config.get("CONFIG_FILE") or PROJECT_ROOT / "config.yaml"
    return str(pathlib.Path(value).expanduser())

def get_root_directory() -> str:
    value = app.config.get("ROOT_DIRECTORY") or resolve_env_value("root_directory", "ROOT_DIRECTORY",PROJECT_ROOT)
    return str(pathlib.Path(value).expanduser())

def set_root_directory(path_value: str) -> None:
    normalized_path = str(pathlib.Path(path_value).expanduser())
    app.config["ROOT_DIRECTORY"] = normalized_path

def get_inventory_directory() -> str:
    value = app.config.get("INVENTORY_DIRECTORY") or resolve_env_value("inventory_directory", "INVENTORY_DIRECTORY", PROJECT_ROOT / "inputfiles" / "inventory")
    return str(pathlib.Path(value).expanduser())

def set_inventory_directory(path_value: str, reload_handler: bool = True) -> None:
    normalized_path = str(pathlib.Path(path_value).expanduser())
    app.config["INVENTORY_DIRECTORY"] = normalized_path
    if reload_handler:
        init_network_handler()

def has_inventory_files(path_obj: pathlib.Path) -> bool:
    inventory_files = ("hosts.yaml", "groups.yaml", "defaults.yaml")
    return all((path_obj / filename).exists() for filename in inventory_files)

def get_netbox_url() -> str:
    return app.config.get("NETBOX_URL") or resolve_env_value("netbox_url", "NETBOX_URL", "")

def set_netbox_url(url_value: str) -> None:
    url = url_value.strip()
    app.config["NETBOX_URL"] = url

def get_netbox_token() -> str:
    return app.config.get("NETBOX_TOKEN") or resolve_env_value("netbox_token", "NETBOX_TOKEN", "")

def set_netbox_token(token_value: str) -> None:
    token = token_value.strip()
    app.config["NETBOX_TOKEN"] = token


set_root_directory(get_root_directory())
set_inventory_directory(get_inventory_directory(), reload_handler=False)
set_netbox_url(get_netbox_url())
set_netbox_token(get_netbox_token())


def get_network_handler() -> NetworkHandler:
    return app.extensions.get("network_handler")

def set_network_handler(handler: NetworkHandler) -> None:
    app.extensions["network_handler"] = handler

def get_template_context() -> dict:
    return {
        'inventory_directory': get_inventory_directory(),
        'root_directory': get_root_directory(),
        'netbox_url': get_netbox_url(),
        'netbox_token_saved': bool(get_netbox_token()),
    }

def normalize_target_source(source: str | None) -> str:
    if source in VALID_TARGET_SOURCES:
        return source
    return TARGET_SOURCE_INVENTORY

def empty_target_options(source: str, error_message: str = "") -> dict:
    return {
        "source": source,
        "inventory_hosts": [],
        "group_devices": {},
        "error": error_message,
    }


def build_config_options_from_yaml() -> dict:
    with open(get_config_file(), "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    device_data = config.get("user_defined", {}).get("device_data", {})
    get_configs = defaultdict(list)

    for key, value in device_data.items():
        group_name = value.get("group", "Others")
        option = {
            "id": key,
            "name": key,
            "label": value.get("label", key),
            "status": value.get("status", "disabled"),
        }
        get_configs[group_name].append(dict(option))

    return {
        "get_configs": dict(get_configs),
    }

def get_config_options(section: str) -> dict:
    config_options = app.config.get("CONFIG_OPTIONS")
    if not config_options:
        init_config_options()
        config_options = app.config.get("CONFIG_OPTIONS", {})
    return config_options.get(section, {})


@app.route('/')
def index():
    return render_template('index.html', **get_template_context())

@app.route('/get_configs')
def get_configs():
    target_source = normalize_target_source(request.args.get('target_source'))
    target_options = get_target_options(target_source)

    return render_template(
        'get_configs.html',
        config_options=get_config_options('get_configs'),
        inventory_hosts=target_options['inventory_hosts'],
        group_devices=target_options['group_devices'],
        target_source=target_options['source'],
        target_source_error=target_options.get('error', ''),
        **get_template_context()
    )

@app.route('/target_options')
def target_options():
    target_source = normalize_target_source(request.args.get('source'))
    options = get_target_options(target_source)

    if options.get('error'):
        return jsonify(options), 400

    return jsonify(options)

@app.route('/netbox_status')
def netbox_status():
    return jsonify(get_netbox_status())

@app.route('/browse_folders')
def browse_folders():
    requested_path = request.args.get('path') or get_inventory_directory()
    folder_path = pathlib.Path(requested_path).expanduser()

    try:
        folder_path = folder_path.resolve()
        folders = [
            {
                'name': child.name,
                'path': str(child),
                'hasInventoryFiles': has_inventory_files(child),
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
        'hasInventoryFiles': has_inventory_files(folder_path),
        'folders': folders,
    })




















@app.route('/update_device_group_options', methods=['POST'])
def update_device_group_options():
    config_options = app.config.get("CONFIG_OPTIONS", {})
    config_options['device_group'] = request.json.get('device_group_options')
    app.config["CONFIG_OPTIONS"] = config_options
    return jsonify(success=True)

@app.route('/update_root_directory', methods=['POST'])
def update_root_directory():
    set_inventory_directory(request.form.get('root_directory'))
    return get_inventory_directory()


@app.route('/target_settings', methods=['POST'])
def target_settings():
    settings = request.get_json() or {}
    inventory_directory = settings.get('inventoryDirectory') or settings.get('rootDirectory')
    netbox_url = settings.get('netboxUrl')
    netbox_token = settings.get('netboxToken')

    if inventory_directory is not None and inventory_directory.strip():
        set_inventory_directory(inventory_directory.strip())

    if netbox_url is not None:
        set_netbox_url(netbox_url)

    if netbox_token:
        set_netbox_token(netbox_token)

    return jsonify(success=True)


def get_target_options(source: str) -> dict:
    if source == TARGET_SOURCE_NETBOX:
        return get_netbox_targets_for_template()

    inventory_hosts, group_devices = get_inventory_hosts_for_template()
    if not group_devices:
        group_devices = {
            group_name: []
            for group_name in get_network_handler().nornir.inventory.groups.keys()
        }

    return {
        'source': TARGET_SOURCE_INVENTORY,
        'inventory_hosts': inventory_hosts,
        'group_devices': group_devices,
    }


def get_inventory_hosts_for_template() -> tuple[list[dict], dict[str, list[str]]]:
    inventory_directory = get_inventory_directory()
    hosts_file = f"{inventory_directory}/hosts.yaml"
    inventory_hosts = []
    group_devices = defaultdict(list)
    network_handler = app.extensions.get('network_handler')

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
    netbox_url = get_netbox_url()
    netbox_token = get_netbox_token()

    if not netbox_url or not netbox_token:
        return empty_target_options(TARGET_SOURCE_NETBOX, "NetBox URL/token are not configured.")

    netbox = Netbox(netbox_url.rstrip('/'), netbox_token)

    try:
        response = netbox.get_request('/dcim/devices/', params={'limit': 0})
    except Exception as exception:
        return empty_target_options(TARGET_SOURCE_NETBOX, f"Could not load NetBox devices: {exception}")

    if not response:
        return empty_target_options(TARGET_SOURCE_NETBOX, "NetBox did not return device data.")

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
        'inventory_hosts': sorted_hosts(inventory_hosts),
        'group_devices': group_devices,
    }


def get_netbox_status() -> dict:
    netbox_url = get_netbox_url()
    netbox_token = get_netbox_token()

    if not netbox_url or not netbox_token:
        return {"connected": False, "message": "Not configured"}

    netbox = Netbox(netbox_url.rstrip('/'), netbox_token)
    try:
        netbox.get_request('/dcim/devices/', params={'limit': 1})
        return {"connected": True, "message": "Connected"}
    except Exception:
        return {"connected": False, "message": "Not connected"}


def normalize_netbox_ip(address: str) -> str:
    return address.split('/')[0] if address else ''


def sorted_hosts(hosts: list[dict]) -> list[dict]:
    return sorted(hosts, key=lambda host: host['name'])


def sort_group_devices(group_devices: defaultdict | dict) -> dict[str, list[str]]:
    return {
        group_name: sorted(devices)
        for group_name, devices in sorted(group_devices.items())
    }


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

    network_handler = get_network_handler()
    nornir_filtered = network_handler.nornir.filter(nornir_target_filter)
    network_handler.nornir_get_configs(get_configs_info=get_configs_info, nornir_filtered=nornir_filtered)

    script_data = network_handler.nornir_generate_data_dict()
    output_parsed = network_handler.nornir_generate_config_parsed(script_data)

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


def init_config_options() -> None:
    app.config["CONFIG_OPTIONS"] = build_config_options_from_yaml()


def init_network_handler() -> None:
    '''Initialize NetworkHandler for the currently selected root directory.'''
    hosts = None
    groups = None
    defaults = None
    inventory_directory = get_inventory_directory()

    if os.path.exists(f"{inventory_directory}/hosts.yaml"):
        hosts = f"{inventory_directory}/hosts.yaml"
    if os.path.exists(f"{inventory_directory}/groups.yaml"):
        groups = f"{inventory_directory}/groups.yaml"
    if os.path.exists(f"{inventory_directory}/defaults.yaml"):
        defaults = f"{inventory_directory}/defaults.yaml"

    network_handler = NetworkHandler(host_file=hosts, group_file=groups, defaults_file=defaults)
    network_handler.dir = inventory_directory
    set_network_handler(network_handler)


def init_netbox() -> None:
    ''' '''
    global NETBOX

    url = None
    token = None

    NETBOX = Netbox(url, token)


def update_netbox_device(site, output_parsed) -> None:
    network_handler = get_network_handler()

    device_model_db = network_handler.nornir.config.user_defined['models_database']
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
    network_handler = get_network_handler()
    device_model_db = network_handler.nornir.config.user_defined['models_database'][model]
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
    add_device_netbox(site, model, hostname, serial_number)


def main():

    init_config_options()
    init_network_handler()

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)


if __name__ == "__main__":
    main()
