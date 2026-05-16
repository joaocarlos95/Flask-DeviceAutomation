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


# ---------------------------------------------------------------------------
# Path and Environment Resolution
# ---------------------------------------------------------------------------
def resolve_env_value(primary_key: str, secondary_key: str, default_value: pathlib.Path | str) -> str:
    """Read a value from env with primary/secondary keys and fallback default."""
    return os.getenv(primary_key) or os.getenv(secondary_key) or str(default_value)

def normalize_path(path_value: pathlib.Path | str) -> str:
    """Normalize paths to absolute paths relative to PROJECT_ROOT when needed."""
    path_obj = pathlib.Path(path_value).expanduser()
    if not path_obj.is_absolute():
        path_obj = PROJECT_ROOT / path_obj
    return str(path_obj.resolve(strict=False))

def get_config_file() -> str:
    """Return the active config.yaml absolute path."""
    value = app.config.get("CONFIG_FILE") or PROJECT_ROOT / "config.yaml"
    return normalize_path(value)

def get_root_directory() -> str:
    """Return root directory from runtime config or environment."""
    value = app.config.get("ROOT_DIRECTORY") or resolve_env_value("root_directory", "ROOT_DIRECTORY",PROJECT_ROOT)
    return normalize_path(value)

def set_root_directory(path_value: str) -> None:
    """Persist normalized root directory in runtime app config."""
    normalized_path = normalize_path(path_value)
    app.config["ROOT_DIRECTORY"] = normalized_path

def get_inventory_directory() -> str:
    """Resolve inventory directory with precedence: UI/app config > .env > default."""
    value = app.config.get("INVENTORY_DIRECTORY")
    if not value:
        value = resolve_env_value("inventory_directory", "INVENTORY_DIRECTORY", PROJECT_ROOT / "inputfiles" / "inventory")
    return normalize_path(value)

def set_inventory_directory(path_value: str, reload_handler: bool = True) -> None:
    """Update inventory directory and optionally reinitialize Nornir handler."""
    normalized_path = normalize_path(path_value)
    app.config["INVENTORY_DIRECTORY"] = normalized_path
    if reload_handler:
        init_network_handler()

def resolve_inventory_files() -> dict:
    """Return resolved inventory paths and whether all expected files exist."""
    inventory_dir = pathlib.Path(get_inventory_directory())
    hosts = inventory_dir / "hosts.yaml"
    groups = inventory_dir / "groups.yaml"
    defaults = inventory_dir / "defaults.yaml"

    return {
        "inventory_dir": str(inventory_dir),
        "hosts": str(hosts),
        "groups": str(groups),
        "defaults": str(defaults),
        "has_all_files": all(path.exists() for path in (hosts, groups, defaults)),
    }

def has_inventory_files(path_obj: pathlib.Path) -> bool:
    """Check whether a folder contains hosts/groups/defaults inventory files."""
    inventory_files = ("hosts.yaml", "groups.yaml", "defaults.yaml")
    return all((path_obj / filename).exists() for filename in inventory_files)

def get_netbox_url() -> str:
    """Get NetBox URL from runtime config or environment."""
    return app.config.get("NETBOX_URL") or resolve_env_value("netbox_url", "NETBOX_URL", "")

def set_netbox_url(url_value: str) -> None:
    """Persist NetBox URL in runtime app config."""
    url = url_value.strip()
    app.config["NETBOX_URL"] = url

def get_netbox_token() -> str:
    """Get NetBox token from runtime config or environment."""
    return app.config.get("NETBOX_TOKEN") or resolve_env_value("netbox_token", "NETBOX_TOKEN", "")

def set_netbox_token(token_value: str) -> None:
    """Persist NetBox token in runtime app config."""
    token = token_value.strip()
    app.config["NETBOX_TOKEN"] = token


set_root_directory(get_root_directory())
set_inventory_directory(get_inventory_directory(), reload_handler=False)
set_netbox_url(get_netbox_url())
set_netbox_token(get_netbox_token())


# ---------------------------------------------------------------------------
# Runtime Service Accessors
# ---------------------------------------------------------------------------
def get_network_handler() -> NetworkHandler:
    """Fetch shared NetworkHandler instance from Flask extensions."""
    return app.extensions.get("network_handler")

def set_network_handler(handler: NetworkHandler) -> None:
    """Store shared NetworkHandler instance in Flask extensions."""
    app.extensions["network_handler"] = handler

def get_netbox() -> Netbox:
    """Fetch shared NetBox client from Flask extensions."""
    return app.extensions.get("netbox")

def set_netbox(netbox: Netbox) -> None:
    """Store shared NetBox client in Flask extensions."""
    app.extensions["netbox"] = netbox

def get_template_context() -> dict:
    """Context values reused by template-rendering routes."""
    return {
        'inventory_directory': get_inventory_directory(),
        'root_directory': get_root_directory(),
        'netbox_url': get_netbox_url(),
        'netbox_token_saved': bool(get_netbox_token()),
    }

def normalize_target_source(source: str | None) -> str:
    """Normalize target source to supported values, defaulting to inventory."""
    if source in VALID_TARGET_SOURCES:
        return source
    return TARGET_SOURCE_INVENTORY

def empty_target_options(source: str, error_message: str = "") -> dict:
    """Standard empty payload for target-source responses with optional error."""
    return {
        "source": source,
        "inventory_hosts": [],
        "group_devices": {},
        "error": error_message,
    }

# ---------------------------------------------------------------------------
# Config Options
# ---------------------------------------------------------------------------
def build_config_options_from_yaml() -> dict:
    """Build UI config options from the user_defined.device_data section."""
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
    """Get a section from cached config options, initializing cache if needed."""
    config_options = app.config.get("CONFIG_OPTIONS")
    if not config_options:
        init_config_options()
        config_options = app.config.get("CONFIG_OPTIONS", {})
    return config_options.get(section, {})

def set_config_options(section: str, options: dict) -> None:
    """Update a section in cached config options."""
    config_options = app.config.get("CONFIG_OPTIONS")
    if not config_options:
        init_config_options()
        config_options = app.config.get("CONFIG_OPTIONS", {})
    config_options[section] = options or {}
    app.config["CONFIG_OPTIONS"] = config_options


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html', **get_template_context())

@app.route('/get_configs')
def get_configs():
    """Render get-configs page with selected target source options."""
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
    """Return target options (inventory or NetBox) in JSON."""
    target_source = normalize_target_source(request.args.get('source'))
    options = get_target_options(target_source)

    if options.get('error'):
        return jsonify(options), 400

    return jsonify(options)

@app.route('/netbox_status')
def netbox_status():
    """Return current NetBox connectivity status."""
    return jsonify(get_netbox_status())

@app.route('/browse_folders')
def browse_folders():
    """Browse directories and flag which folders contain inventory files."""
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
    """Persist UI-selected device group options in runtime config."""
    set_config_options('device_group', request.json.get('device_group_options'))
    return jsonify(success=True)

@app.route('/update_root_directory', methods=['POST'])
def update_root_directory():
    """Update inventory directory from UI and reload inventory handler."""
    set_inventory_directory(request.form.get('root_directory'))
    return get_inventory_directory()

@app.route('/target_settings', methods=['POST'])
def target_settings():
    """Apply target settings from UI and refresh services when needed."""
    settings = request.get_json() or {}
    inventory_directory = settings.get('inventoryDirectory')
    netbox_url = settings.get('netboxUrl')
    netbox_token = settings.get('netboxToken')
    should_reinit_netbox = False

    if inventory_directory is not None and inventory_directory.strip():
        set_inventory_directory(inventory_directory.strip())

    if netbox_url is not None:
        set_netbox_url(netbox_url)
        should_reinit_netbox = True

    if netbox_token is not None:
        set_netbox_token(netbox_token)
        should_reinit_netbox = True

    if should_reinit_netbox:
        init_netbox()

    return jsonify(success=True)


# ---------------------------------------------------------------------------
# Target Source Builders
# ---------------------------------------------------------------------------
def get_target_options(source: str) -> dict:
    """Dispatch target source loading to inventory or NetBox."""
    if source == TARGET_SOURCE_NETBOX:
        return get_netbox_targets_for_template()

    return get_inventory_hosts_for_template()

def get_inventory_hosts_for_template() -> dict:
    """
    Build inventory host/group payload for templates.
    Primary source is active Nornir inventory; fallback is resolved inventory files.
    """
    inventory_files = resolve_inventory_files()
    hosts_file = inventory_files["hosts"]
    groups_file = inventory_files["groups"]
    inventory_hosts = []
    group_devices = defaultdict(list)
    network_handler = get_network_handler()

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

        inventory_hosts = sorted_hosts(inventory_hosts)
        group_devices = sort_group_devices(group_devices)
        if not group_devices:
            group_devices = {
                group_name: []
                for group_name in network_handler.nornir.inventory.groups.keys()
            }
        return {
            'source': TARGET_SOURCE_INVENTORY,
            'inventory_hosts': inventory_hosts,
            'group_devices': group_devices,
        }

    groups_from_file = {}
    if os.path.exists(groups_file):
        with open(groups_file, 'r', encoding='utf-8') as groups_data:
            groups_from_file = yaml.safe_load(groups_data) or {}

    if not os.path.exists(hosts_file):
        group_devices = {group_name: [] for group_name in groups_from_file.keys()}
        return {
            'source': TARGET_SOURCE_INVENTORY,
            'inventory_hosts': inventory_hosts,
            'group_devices': group_devices,
        }

    with open(hosts_file, 'r', encoding='utf-8') as hosts_data:
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

    inventory_hosts = sorted_hosts(inventory_hosts)
    group_devices = sort_group_devices(group_devices)
    if not group_devices:
        group_devices = {
            group_name: []
            for group_name in groups_from_file.keys()
        }

    return {
        'source': TARGET_SOURCE_INVENTORY,
        'inventory_hosts': inventory_hosts,
        'group_devices': group_devices,
    }

def get_netbox_targets_for_template() -> dict:
    """Build inventory-like payload from NetBox devices."""
    netbox_url = get_netbox_url()
    netbox_token = get_netbox_token()

    if not netbox_url or not netbox_token:
        return empty_target_options(TARGET_SOURCE_NETBOX, "NetBox URL/token are not configured.")

    netbox = get_netbox()
    if netbox is None:
        init_netbox()
        netbox = get_netbox()

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

    inventory_hosts = sorted_hosts(inventory_hosts)
    group_devices = sort_group_devices(group_devices)
    if not group_devices:
        group_devices = {'NetBox devices': []}

    return {
        'source': TARGET_SOURCE_NETBOX,
        'inventory_hosts': inventory_hosts,
        'group_devices': group_devices,
    }

def get_netbox_status() -> dict:
    """Check whether the current NetBox settings are configured and reachable."""
    netbox_url = get_netbox_url()
    netbox_token = get_netbox_token()

    if not netbox_url or not netbox_token:
        return {"connected": False, "message": "Not configured"}

    netbox = get_netbox()
    if netbox is None:
        init_netbox()
        netbox = get_netbox()

    try:
        netbox.get_request('/dcim/devices/', params={'limit': 1})
        return {"connected": True, "message": "Connected"}
    except Exception:
        return {"connected": False, "message": "Not connected"}

# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------
def normalize_netbox_ip(address: str) -> str:
    """Strip CIDR suffix from NetBox IP address values."""
    return address.split('/')[0] if address else ''

def sorted_hosts(hosts: list[dict]) -> list[dict]:
    """Sort hosts by name for deterministic UI ordering."""
    return sorted(hosts, key=lambda host: host['name'])

def sort_group_devices(group_devices: defaultdict | dict) -> dict[str, list[str]]:
    """Sort groups and host names within each group."""
    return {
        group_name: sorted(devices)
        for group_name, devices in sorted(group_devices.items())
    }


# ---------------------------------------------------------------------------
# Execution Routes
# ---------------------------------------------------------------------------
@app.route('/run_get_configs', methods=['POST'])
def run_get_configs():
    """Execute selected get-configs tasks against filtered Nornir targets."""
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
    
    print(f"{Colors.OK_GREEN}[>]{Colors.END} Execution time: {time.time() - start_time} seconds")
    return Response(status=204)


def build_nornir_target_filter(selected_groups: list[str], selected_devices: list[str]):
    """Create Nornir filter expression from selected groups and device names."""
    nornir_target_filter = None

    for group in selected_groups:
        group_filter = F(groups__contains=group)
        nornir_target_filter = group_filter if nornir_target_filter is None else nornir_target_filter | group_filter

    for device in selected_devices:
        device_filter = F(name=device)
        nornir_target_filter = device_filter if nornir_target_filter is None else nornir_target_filter | device_filter

    return nornir_target_filter

# ---------------------------------------------------------------------------
# Service Initialization
# ---------------------------------------------------------------------------
def init_config_options() -> None:
    """Initialize cached config options."""
    app.config["CONFIG_OPTIONS"] = build_config_options_from_yaml()

def init_network_handler() -> None:
    '''Initialize NetworkHandler for the currently selected root directory.'''
    inventory_files = resolve_inventory_files()

    network_handler = NetworkHandler(
        host_file=inventory_files["hosts"],
        group_file=inventory_files["groups"],
        defaults_file=inventory_files["defaults"],
    )
    network_handler.dir = inventory_files["inventory_dir"]
    set_network_handler(network_handler)

def init_netbox() -> None:
    '''Initialize NetBox client for the currently configured URL/token.'''

    netbox = Netbox(
        url=get_netbox_url().rstrip("/"), 
        token=get_netbox_token()
    )
    set_netbox(netbox)

def main():
    """Application entrypoint."""

    init_config_options()
    init_network_handler()
    init_netbox()

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
