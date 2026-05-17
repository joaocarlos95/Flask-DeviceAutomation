import os
import time
import warnings
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response
from nornir.core.configuration import ConflictingConfigurationWarning

from classes.colors import Colors
from services.config_options_service import get_config_options, init_config_options, set_config_options
from services.execution_service import build_nornir_target_filter
from services.runtime_service import get_network_handler, init_netbox, init_network_handler
from services.settings_service import (
    get_inventory_directory,
    get_netbox_token,
    get_netbox_url,
    get_root_directory,
    get_template_context,
    has_inventory_files,
    set_inventory_directory,
    set_netbox_token,
    set_netbox_url,
    set_root_directory,
)
from services.target_service import get_netbox_status, get_target_options, normalize_target_source

warnings.filterwarnings("ignore", category=ConflictingConfigurationWarning)

load_dotenv()

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')


set_root_directory(app, get_root_directory(app))
set_inventory_directory(app, get_inventory_directory(app))
set_netbox_url(app, get_netbox_url(app))
set_netbox_token(app, get_netbox_token(app))


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html', **get_template_context(app))

@app.route('/get_configs')
def get_configs():
    """Render get-configs page with selected target source options."""
    target_source = normalize_target_source(request.args.get('target_source'))
    target_options = get_target_options(app, target_source)

    return render_template(
        'get_configs.html',
        config_options=get_config_options(app, 'get_configs'),
        inventory_hosts=target_options['inventory_hosts'],
        group_devices=target_options['group_devices'],
        target_source=target_options['source'],
        target_source_error=target_options.get('error', ''),
        **get_template_context(app)
    )

@app.route('/target_options')
def target_options():
    """Return target options (inventory or NetBox) in JSON."""
    target_source = normalize_target_source(request.args.get('source'))
    options = get_target_options(app, target_source)

    if options.get('error'):
        return jsonify(options), 400

    return jsonify(options)

@app.route('/netbox_status')
def netbox_status():
    """Return current NetBox connectivity status."""
    return jsonify(get_netbox_status(app))

@app.route('/browse_folders')
def browse_folders():
    """Browse directories and flag which folders contain inventory files."""
    requested_path = request.args.get('path') or get_inventory_directory(app)
    folder_path = Path(requested_path).expanduser()

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
    set_config_options(app, 'device_group', request.json.get('device_group_options'))
    return jsonify(success=True)

@app.route('/update_root_directory', methods=['POST'])
def update_root_directory():
    """Update root directory from UI and reload inventory handler."""
    set_root_directory(app, request.form.get('root_directory'))
    init_network_handler(app)
    return get_root_directory(app)

@app.route('/target_settings', methods=['POST'])
def target_settings():
    """Apply target settings from UI and refresh services when needed."""
    settings = request.get_json() or {}
    inventory_directory = settings.get('inventoryDirectory')
    netbox_url = settings.get('netboxUrl')
    netbox_token = settings.get('netboxToken')
    should_reinit_netbox = False

    if inventory_directory is not None and inventory_directory.strip():
        set_inventory_directory(app, inventory_directory.strip())
        init_network_handler(app)

    if netbox_url is not None:
        set_netbox_url(app, netbox_url)
        should_reinit_netbox = True

    if netbox_token is not None:
        set_netbox_token(app, netbox_token)
        should_reinit_netbox = True

    if should_reinit_netbox:
        init_netbox(app)

    return jsonify(success=True)


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

    network_handler = get_network_handler(app)
    nornir_filtered = network_handler.nornir.filter(nornir_target_filter)
    network_handler.nornir_get_configs(get_configs_info=get_configs_info, nornir_filtered=nornir_filtered)

    script_data = network_handler.nornir_generate_data_dict()
    network_handler.nornir_generate_config_parsed(script_data)
    
    print(f"{Colors.OK_GREEN}[>]{Colors.END} Execution time: {time.time() - start_time} seconds")
    return Response(status=204)


def main():
    """Application entrypoint."""

    init_config_options(app)
    init_network_handler(app)
    init_netbox(app)
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
