import os
import time
import uuid
import threading
import warnings
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from nornir.core.configuration import ConflictingConfigurationWarning

from services.config_options_service import get_config_options, init_config_options, set_config_options
from services.execution_service import build_nornir_target_filter
from services.get_configs_pipeline_service import run_get_configs_pipeline
from services.ntc_templates_service import build_ntc_templates_runtime
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
app.extensions["run_status"] = {}
app.extensions["run_status_lock"] = threading.Lock()


def format_elapsed_duration(total_seconds: float) -> str:
    """Format elapsed duration as seconds or minutes+seconds."""
    total_seconds_int = max(0, int(round(total_seconds)))
    if total_seconds_int < 60:
        return f"{total_seconds_int} second(s)"
    minutes, seconds = divmod(total_seconds_int, 60)
    return f"{minutes} minute(s) {seconds} second(s)"


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
    root_directory = settings.get('rootDirectory')
    inventory_directory = settings.get('inventoryDirectory')
    netbox_url = settings.get('netboxUrl')
    netbox_token = settings.get('netboxToken')
    should_reinit_network_handler = False
    should_reinit_netbox = False

    if root_directory is not None and root_directory.strip():
        set_root_directory(app, root_directory.strip())
        should_reinit_network_handler = True

    if inventory_directory is not None and inventory_directory.strip():
        set_inventory_directory(app, inventory_directory.strip())
        should_reinit_network_handler = True

    if should_reinit_network_handler:
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
    """Start get-configs run in background and return run id."""
    selected_data = request.get_json() or {}
    target_source = normalize_target_source(selected_data.get("targetSource"))
    get_configs_info = selected_data.get('informationDataSelected', [])
    selected_groups = selected_data.get('selectedDeviceGroups', []) or []
    selected_devices = selected_data.get('selectedDevices', []) or []
    excluded_devices = set(selected_data.get('excludedDevices', []) or [])

    # Resolve final target devices on backend using the same source map used by the UI.
    # This avoids frontend selection mismatches and guarantees group expansion.
    target_options = get_target_options(app, target_source)
    group_devices_map = target_options.get("group_devices", {}) or {}
    resolved_devices = set()
    for group in selected_groups:
        for device_name in group_devices_map.get(group, []):
            if device_name not in excluded_devices:
                resolved_devices.add(device_name)
    for device_name in selected_devices:
        if device_name not in excluded_devices:
            resolved_devices.add(device_name)

    resolved_devices = sorted(resolved_devices)
    nornir_target_filter = build_nornir_target_filter(
        selected_groups=[],
        selected_devices=resolved_devices
    )

    if not get_configs_info:
        return jsonify(error='No information data selected.'), 400

    if not nornir_target_filter:
        return jsonify(error='No device groups or devices selected.'), 400

    network_handler = get_network_handler(app)
    inventory_hostnames = set(network_handler.nornir.inventory.hosts.keys())
    missing_devices = [device for device in resolved_devices if device not in inventory_hostnames]
    present_devices = [device for device in resolved_devices if device in inventory_hostnames]

    if not present_devices:
        return jsonify(error='None of the selected devices exist in the current inventory source.'), 400

    nornir_filtered = network_handler.nornir.filter(nornir_target_filter)
    # Nornir keeps an internal failed-host cache between runs; reset it so previously
    # failed/unreachable devices are retried on every new execution.
    if hasattr(nornir_filtered, "reset_failed_hosts"):
        nornir_filtered.reset_failed_hosts()
    elif hasattr(nornir_filtered, "data") and hasattr(nornir_filtered.data, "reset_failed_hosts"):
        nornir_filtered.data.reset_failed_hosts()

    root_directory = get_root_directory(app)
    run_id = uuid.uuid4().hex

    log_dir = Path(root_directory) / "outputfiles" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"get_configs_{time.strftime('%Y%m%d')}.log"

    with app.extensions["run_status_lock"]:
        app.extensions["run_status"][run_id] = {
            "status": "running",
            "started_at": time.time(),
            "finished_at": None,
            "events": [],
            "failed_events": [],
            "stats": {"running": 0, "success": 0, "error": 0, "info": 0},
            "interrupt_requested": False,
            "error": "",
            "run_context": {
                "target_source": target_source,
                "information_data_selected": list(get_configs_info),
                "target_devices_selected": list(resolved_devices),
                "selected_groups": list(selected_groups),
            },
        }

    def append_event(event: dict):
        event_payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **event,
        }
        with app.extensions["run_status_lock"]:
            run_state = app.extensions["run_status"].get(run_id)
            if run_state is not None:
                run_state["events"].append(event_payload)
                run_state["events"] = run_state["events"][-1000:]
                status_key = (event_payload.get("status") or "info").lower()
                if status_key not in run_state["stats"]:
                    run_state["stats"][status_key] = 0
                run_state["stats"][status_key] += 1
                if status_key == "error":
                    run_state["failed_events"].append(event_payload)
                    run_state["failed_events"] = run_state["failed_events"][-500:]

        with log_file.open("a", encoding="utf-8") as handler:
            handler.write(
                f"[{event_payload['timestamp']}] "
                f"{event_payload.get('status', '').upper()} "
                f"{event_payload.get('device', '')} ({event_payload.get('ip', '')}) "
                f"{event_payload.get('config_info', '')} :: {event_payload.get('command', '')} "
                f"- {event_payload.get('message', '')}\n"
            )

    def run_worker():
        start_time = time.time()
        def should_stop():
            with app.extensions["run_status_lock"]:
                run_state = app.extensions["run_status"].get(run_id)
                return bool(run_state and run_state.get("interrupt_requested"))
        try:
            for missing_device in missing_devices:
                append_event({
                    "status": "error",
                    "device": missing_device,
                    "ip": "-",
                    "config_info": "target_resolution",
                    "command": "inventory_lookup",
                    "message": "Target not found in active inventory"
                })
            run_get_configs_pipeline(
                network_handler=network_handler,
                nornir_filtered=nornir_filtered,
                get_configs_info=get_configs_info,
                root_directory=root_directory,
                progress_callback=append_event,
                should_stop=should_stop,
            )
            was_interrupted = False
            with app.extensions["run_status_lock"]:
                run_state = app.extensions["run_status"].get(run_id)
                if run_state is not None:
                    was_interrupted = run_state.get("interrupt_requested") or run_state.get("status") == "interrupted"
                    if not was_interrupted:
                        run_state["status"] = "completed"
                        run_state["finished_at"] = time.time()
            if not was_interrupted:
                append_event({
                    "status": "success",
                    "device": "-",
                    "ip": "-",
                    "config_info": "run",
                    "command": "run_get_configs",
                    "message": f"Execution time: {format_elapsed_duration(time.time() - start_time)}"
                })
        except Exception as exception:
            with app.extensions["run_status_lock"]:
                run_state = app.extensions["run_status"].get(run_id)
                if run_state is not None:
                    run_state["status"] = "interrupted" if str(exception) == "Interrupted by user" else "failed"
                    run_state["finished_at"] = time.time()
                    run_state["error"] = str(exception)
            append_event({
                "status": "error",
                "device": "-",
                "ip": "-",
                "config_info": "run",
                "command": "run_get_configs",
                "message": str(exception)
            })

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify(runId=run_id)


@app.route('/run_get_configs_status/<run_id>', methods=['GET'])
def run_get_configs_status(run_id):
    with app.extensions["run_status_lock"]:
        run_state = app.extensions["run_status"].get(run_id)
        if not run_state:
            return jsonify(error="Run not found."), 404
        return jsonify(run_state)


@app.route('/run_get_configs_recent', methods=['GET'])
def run_get_configs_recent():
    """Return recent get-configs runs for quick navigation in the modal."""
    with app.extensions["run_status_lock"]:
        run_status = app.extensions["run_status"].copy()

    runs = []
    for run_id, run_state in run_status.items():
        runs.append({
            "runId": run_id,
            "status": run_state.get("status", "unknown"),
            "startedAt": run_state.get("started_at"),
            "finishedAt": run_state.get("finished_at"),
        })

    runs.sort(key=lambda item: item.get("startedAt") or 0, reverse=True)
    return jsonify(runs=runs[:12])


@app.route('/run_get_configs_interrupt/<run_id>', methods=['POST'])
def run_get_configs_interrupt(run_id):
    with app.extensions["run_status_lock"]:
        run_state = app.extensions["run_status"].get(run_id)
        if not run_state:
            return jsonify(error="Run not found."), 404
        run_state["interrupt_requested"] = True
        if run_state.get("status") == "running":
            run_state["status"] = "interrupted"
            run_state["finished_at"] = time.time()
    return jsonify(success=True)


def main():
    """Application entrypoint."""

    build_ntc_templates_runtime()
    init_config_options(app)
    init_network_handler(app)
    init_netbox(app)
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
