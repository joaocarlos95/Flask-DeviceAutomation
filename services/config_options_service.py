from collections import defaultdict

import yaml

from services.settings_service import get_config_file


def build_config_options_from_yaml(app) -> dict:
    """Build UI config options from the user_defined.device_data section."""
    with open(get_config_file(app), "r", encoding="utf-8") as config_file:
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
    return {"get_configs": dict(get_configs)}


def init_config_options(app) -> None:
    """Initialize cached config options."""
    app.config["CONFIG_OPTIONS"] = build_config_options_from_yaml(app)


def get_config_options(app, section: str) -> dict:
    """Get a section from cached config options, initializing cache if needed."""
    config_options = app.config.get("CONFIG_OPTIONS")
    if not config_options:
        init_config_options(app)
        config_options = app.config.get("CONFIG_OPTIONS", {})
    return config_options.get(section, {})


def set_config_options(app, section: str, options: dict) -> None:
    """Update a section in cached config options."""
    config_options = app.config.get("CONFIG_OPTIONS")
    if not config_options:
        init_config_options(app)
        config_options = app.config.get("CONFIG_OPTIONS", {})
    config_options[section] = options or {}
    app.config["CONFIG_OPTIONS"] = config_options
