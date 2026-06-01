from services.report_export_service import export_parsed_excel


def run_get_configs_pipeline(network_handler, nornir_filtered, get_configs_info: list[str], root_directory: str, progress_callback=None, should_stop=None) -> None:
    """
    Execute get-configs workflow:
    1) Run commands on devices
    2) Parse output via TextFSM
    3) Export parsed XLSX (one tab per command)
    """
    if progress_callback:
        progress_callback({
            "device": "-",
            "ip": "-",
            "config_info": "run",
            "command": "collect",
            "status": "running",
            "message": "Starting device command collection"
        })
    network_handler.nornir_get_configs(
        get_configs_info=get_configs_info,
        nornir_filtered=nornir_filtered,
        progress_callback=progress_callback,
        should_stop=should_stop
    )
    if progress_callback:
        progress_callback({
            "device": "-",
            "ip": "-",
            "config_info": "run",
            "command": "collect",
            "status": "success",
            "message": "Device command collection completed"
        })
        progress_callback({
            "device": "-",
            "ip": "-",
            "config_info": "run",
            "command": "parse",
            "status": "running",
            "message": "Building parsed data"
        })
    script_data = network_handler.nornir_generate_data_dict(progress_callback=progress_callback)
    parsed_data = network_handler.nornir_build_config_parsed(script_data)
    if progress_callback:
        progress_callback({
            "device": "-",
            "ip": "-",
            "config_info": "run",
            "command": "parse",
            "status": "success",
            "message": "Parsed data built"
        })

    export_parsed_excel(root_directory=root_directory, parsed_data=parsed_data, progress_callback=progress_callback)
