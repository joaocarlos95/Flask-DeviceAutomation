from classes.network_handler import NetworkHandler
from classes.netbox import Netbox
from services.settings_service import (
    get_netbox_token,
    get_netbox_url,
    get_root_directory,
    resolve_inventory_files,
)


def get_network_handler(app) -> NetworkHandler:
    """Fetch shared NetworkHandler instance from Flask extensions."""
    return app.extensions.get("network_handler")


def set_network_handler(app, handler: NetworkHandler) -> None:
    """Store shared NetworkHandler instance in Flask extensions."""
    app.extensions["network_handler"] = handler


def get_netbox(app) -> Netbox:
    """Fetch shared NetBox client from Flask extensions."""
    return app.extensions.get("netbox")


def set_netbox(app, netbox: Netbox) -> None:
    """Store shared NetBox client in Flask extensions."""
    app.extensions["netbox"] = netbox


def init_network_handler(app) -> None:
    """Initialize NetworkHandler for the currently selected inventory."""
    inventory_files = resolve_inventory_files(app)
    network_handler = NetworkHandler(
        host_file=inventory_files["hosts"],
        group_file=inventory_files["groups"],
        defaults_file=inventory_files["defaults"],
    )
    network_handler.dir = get_root_directory(app)
    set_network_handler(app, network_handler)


def init_netbox(app) -> None:
    """Initialize NetBox client for the currently configured URL/token."""
    netbox = Netbox(
        url=get_netbox_url(app).rstrip("/"),
        token=get_netbox_token(app),
    )
    set_netbox(app, netbox)
