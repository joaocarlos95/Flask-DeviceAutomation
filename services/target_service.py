import os
from collections import defaultdict

import yaml

from services.runtime_service import get_netbox, get_network_handler, init_netbox
from services.settings_service import get_netbox_token, get_netbox_url, resolve_inventory_files


TARGET_SOURCE_INVENTORY = "inventory"
TARGET_SOURCE_NETBOX = "netbox"
VALID_TARGET_SOURCES = {TARGET_SOURCE_INVENTORY, TARGET_SOURCE_NETBOX}


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


def normalize_netbox_ip(address: str) -> str:
    """Strip CIDR suffix from NetBox IP address values."""
    return address.split("/")[0] if address else ""


def sorted_hosts(hosts: list[dict]) -> list[dict]:
    """Sort hosts by name for deterministic UI ordering."""
    return sorted(hosts, key=lambda host: host["name"])


def sort_group_devices(group_devices: defaultdict | dict) -> dict[str, list[str]]:
    """Sort groups and host names within each group."""
    return {group_name: sorted(devices) for group_name, devices in sorted(group_devices.items())}


def get_inventory_hosts_for_template(app) -> dict:
    """Build inventory host/group payload for templates."""
    inventory_files = resolve_inventory_files(app)
    hosts_file = inventory_files["hosts"]
    groups_file = inventory_files["groups"]
    inventory_hosts = []
    group_devices = defaultdict(list)
    network_handler = get_network_handler(app)

    if network_handler and network_handler.nornir.inventory.hosts:
        for host_name, host in network_handler.nornir.inventory.hosts.items():
            host_groups = [group.name for group in host.groups]
            inventory_hosts.append({"name": host_name, "hostname": host.hostname or "", "groups": host_groups})
            for group_name in host_groups:
                group_devices[group_name].append(host_name)

        inventory_hosts = sorted_hosts(inventory_hosts)
        group_devices = sort_group_devices(group_devices)
        if not group_devices:
            group_devices = {group_name: [] for group_name in network_handler.nornir.inventory.groups.keys()}
        return {
            "source": TARGET_SOURCE_INVENTORY,
            "inventory_hosts": inventory_hosts,
            "group_devices": group_devices,
        }

    groups_from_file = {}
    if os.path.exists(groups_file):
        with open(groups_file, "r", encoding="utf-8") as groups_data:
            groups_from_file = yaml.safe_load(groups_data) or {}

    if not os.path.exists(hosts_file):
        group_devices = {group_name: [] for group_name in groups_from_file.keys()}
        return {"source": TARGET_SOURCE_INVENTORY, "inventory_hosts": inventory_hosts, "group_devices": group_devices}

    with open(hosts_file, "r", encoding="utf-8") as hosts_data:
        hosts = yaml.safe_load(hosts_data) or {}

    for host_name, host_data in hosts.items():
        host_data = host_data or {}
        host_groups = host_data.get("groups") or []
        inventory_hosts.append({"name": host_name, "hostname": host_data.get("hostname", ""), "groups": host_groups})
        for group_name in host_groups:
            group_devices[group_name].append(host_name)

    inventory_hosts = sorted_hosts(inventory_hosts)
    group_devices = sort_group_devices(group_devices)
    if not group_devices:
        group_devices = {group_name: [] for group_name in groups_from_file.keys()}

    return {
        "source": TARGET_SOURCE_INVENTORY,
        "inventory_hosts": inventory_hosts,
        "group_devices": group_devices,
    }


def get_netbox_targets_for_template(app) -> dict:
    """Build inventory-like payload from NetBox devices."""
    netbox_url = get_netbox_url(app)
    netbox_token = get_netbox_token(app)
    if not netbox_url or not netbox_token:
        return empty_target_options(TARGET_SOURCE_NETBOX, "NetBox URL/token are not configured.")

    netbox = get_netbox(app)
    if netbox is None:
        init_netbox(app)
        netbox = get_netbox(app)

    try:
        response = netbox.get_request("/dcim/devices/", params={"limit": 0})
    except Exception as exception:
        return empty_target_options(TARGET_SOURCE_NETBOX, f"Could not load NetBox devices: {exception}")

    if not response:
        return empty_target_options(TARGET_SOURCE_NETBOX, "NetBox did not return device data.")

    inventory_hosts = []
    group_devices = defaultdict(list)
    for device in response.get("results", []):
        device_name = device.get("name") or device.get("display") or ""
        if not device_name:
            continue

        site = device.get("site") or {}
        role = device.get("role") or {}
        platform = device.get("platform") or {}
        primary_ip = device.get("primary_ip4") or device.get("primary_ip") or {}
        host_groups = []

        for group_name in [site.get("name"), role.get("name"), platform.get("name")]:
            if group_name and group_name not in host_groups:
                host_groups.append(group_name)
        if not host_groups:
            host_groups.append("NetBox devices")

        inventory_hosts.append(
            {"name": device_name, "hostname": normalize_netbox_ip(primary_ip.get("address", "")), "groups": host_groups}
        )
        for group_name in host_groups:
            group_devices[group_name].append(device_name)

    inventory_hosts = sorted_hosts(inventory_hosts)
    group_devices = sort_group_devices(group_devices)
    if not group_devices:
        group_devices = {"NetBox devices": []}
    return {"source": TARGET_SOURCE_NETBOX, "inventory_hosts": inventory_hosts, "group_devices": group_devices}


def get_target_options(app, source: str) -> dict:
    """Dispatch target source loading to inventory or NetBox."""
    if source == TARGET_SOURCE_NETBOX:
        return get_netbox_targets_for_template(app)
    return get_inventory_hosts_for_template(app)


def get_netbox_status(app) -> dict:
    """Check whether the current NetBox settings are configured and reachable."""
    netbox_url = get_netbox_url(app)
    netbox_token = get_netbox_token(app)
    if not netbox_url or not netbox_token:
        return {"connected": False, "message": "Not configured"}

    netbox = get_netbox(app)
    if netbox is None:
        init_netbox(app)
        netbox = get_netbox(app)

    try:
        netbox.get_request("/dcim/devices/", params={"limit": 1})
        return {"connected": True, "message": "Connected"}
    except Exception:
        return {"connected": False, "message": "Not connected"}
