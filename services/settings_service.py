import os
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


def resolve_env_value(primary_key: str, secondary_key: str, default_value: pathlib.Path | str) -> str:
    """Read a value from env with primary/secondary keys and fallback default."""
    return os.getenv(primary_key) or os.getenv(secondary_key) or str(default_value)


def normalize_path(path_value: pathlib.Path | str) -> str:
    """Normalize paths to absolute paths relative to PROJECT_ROOT when needed."""
    path_obj = pathlib.Path(path_value).expanduser()
    if not path_obj.is_absolute():
        path_obj = PROJECT_ROOT / path_obj
    return str(path_obj.resolve(strict=False))


def get_config_file(app) -> str:
    """Return the active config.yaml absolute path."""
    value = app.config.get("CONFIG_FILE") or PROJECT_ROOT / "config.yaml"
    return normalize_path(value)


def get_root_directory(app) -> str:
    """Return root directory from runtime config or environment."""
    value = app.config.get("ROOT_DIRECTORY") or resolve_env_value("root_directory", "ROOT_DIRECTORY", PROJECT_ROOT)
    return normalize_path(value)


def set_root_directory(app, path_value: str) -> None:
    """Persist normalized root directory in runtime app config."""
    normalized_path = normalize_path(path_value)
    app.config["ROOT_DIRECTORY"] = normalized_path


def get_inventory_directory(app) -> str:
    """Resolve inventory directory with precedence: UI/app config > .env > default."""
    value = app.config.get("INVENTORY_DIRECTORY")
    if not value:
        value = resolve_env_value("inventory_directory", "INVENTORY_DIRECTORY", PROJECT_ROOT / "inputfiles" / "inventory")
    return normalize_path(value)


def set_inventory_directory(app, path_value: str) -> None:
    """Update inventory directory in runtime app config."""
    normalized_path = normalize_path(path_value)
    app.config["INVENTORY_DIRECTORY"] = normalized_path


def get_netbox_url(app) -> str:
    """Get NetBox URL from runtime config or environment."""
    return app.config.get("NETBOX_URL") or resolve_env_value("netbox_url", "NETBOX_URL", "")


def set_netbox_url(app, url_value: str) -> None:
    """Persist NetBox URL in runtime app config."""
    app.config["NETBOX_URL"] = url_value.strip()


def get_netbox_token(app) -> str:
    """Get NetBox token from runtime config or environment."""
    return app.config.get("NETBOX_TOKEN") or resolve_env_value("netbox_token", "NETBOX_TOKEN", "")


def set_netbox_token(app, token_value: str) -> None:
    """Persist NetBox token in runtime app config."""
    app.config["NETBOX_TOKEN"] = token_value.strip()


def resolve_inventory_files(app) -> dict:
    """Return resolved inventory paths and whether all expected files exist."""
    inventory_dir = pathlib.Path(get_inventory_directory(app))
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


def get_template_context(app) -> dict:
    """Context values reused by template-rendering routes."""
    return {
        "inventory_directory": get_inventory_directory(app),
        "root_directory": get_root_directory(app),
        "netbox_url": get_netbox_url(app),
        "netbox_token_saved": bool(get_netbox_token(app)),
    }
