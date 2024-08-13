import os
import pathlib
import time
import yaml
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, Response
from nornir.core.filter import F

from dep.panda.classes.network_handler import NetworkHandler
from dep.panda.classes.colors import Colors
from dep.panda.classes.netbox import Netbox


ROOT_DIRECTORY = "C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation"
#ROOT_DIRECTORY = f"{pathlib.Path(__file__).parent.resolve()}"
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


app = Flask(__name__, template_folder='web/templates', static_folder='dep/')

@app.route('/')
def index():
    template_context = {}
    template_context['root_directory'] = ROOT_DIRECTORY
    return render_template('index.html', **template_context)

@app.route('/get_configs')
def get_configs():
    template_context = {}
    template_context['root_directory'] = ROOT_DIRECTORY
    return render_template('get_configs.html', config_options=CONFIG_OPTIONS['get_configs'], device_groups=NETWORK_HANDLER.nornir.inventory.groups, **template_context)

@app.route('/set_configs')
def set_configs():
    template_context = {}
    template_context['root_directory'] = ROOT_DIRECTORY
    return render_template('set_configs.html', config_options=CONFIG_OPTIONS['set_configs'], **template_context)

@app.route('/generate_configs')
def generate_configs():
    template_context = {}
    template_context['root_directory'] = ROOT_DIRECTORY
    return render_template('generate_configs.html', config_options=CONFIG_OPTIONS['set_configs'], **template_context)

@app.route('/update_netbox')
def update_netbox():
    template_context = {}
    template_context['root_directory'] = ROOT_DIRECTORY
    return render_template('update_netbox.html', config_options=CONFIG_OPTIONS['upd_netbox'], device_groups=NETWORK_HANDLER.nornir.inventory.groups, **template_context)

@app.route('/update_device_group_options', methods=['POST'])
def update_device_group_options():
    global CONFIG_OPTIONS
    CONFIG_OPTIONS['device_group'] = request.json.get('device_group_options')
    return jsonify(success=True)

@app.route('/update_root_directory', methods=['POST'])
def update_root_directory():
    global ROOT_DIRECTORY
    ROOT_DIRECTORY = request.form.get('root_directory')
    return ROOT_DIRECTORY


def get_checked_options(method: str):
    checked_options = []
    for category, options in CONFIG_OPTIONS[method].items():
        for option in options:
            if option['status'] == 'checked' and method == 'get_configs':
                checked_options.append(option['id'])
            elif option['status'] == 'checked' and method == 'set_configs':
                checked_options.append(option['id'])

    return checked_options


@app.route('/run_get_configs', methods=['POST'])
def run_get_configs():
    start_time = time.time()

    selected_data = request.get_json()
    get_configs_info = selected_data['informationDataSelected']

    selected_groups = selected_data['selectedDeviceGroups']
    nornir_group_filter = F(groups__contains=selected_groups[0])
    for group in selected_groups[1:]:
        nornir_group_filter |= F(groups__contains=group)

    nornir_filtered = NETWORK_HANDLER.nornir.filter(nornir_group_filter)
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


@app.route('/run_set_configs', methods=['POST'])
def run_set_configs():
    start_time = time.time()

    config_blocks = get_checked_options(method='set_configs')

    # Create a new NETWORK_HANDLER object and initialize all data (command list)
    NETWORK_HANDLER = NETWORK_HANDLER(ROOT_DIRECTORY)
    NETWORK_HANDLER.get_devices_from_csv()
    NETWORK_HANDLER.get_j2_template()
    NETWORK_HANDLER.get_j2_data()

    # Get device information for each information requested
    NETWORK_HANDLER.set_concurrent_configs(config_blocks=config_blocks)

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
        for key, value in config['user_defined']['Netbox_data'].items():
            # Append the current option to the corresponding group
            upd_netbox[value['group']].append({
                'id': key,
                'name': key,
                'label': value['label'],
                'status': value['status'],
                'get_configs': value['PANDA_reference']
            })

    CONFIG_OPTIONS['get_configs'] = dict(get_configs)
    CONFIG_OPTIONS['upd_netbox'] = dict(upd_netbox)


def init_network_handler() -> None:
    ''' '''
    global NETWORK_HANDLER

    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/hosts.yaml"):
        hosts = f"{ROOT_DIRECTORY}/inputfiles/inventory/hosts.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/groups.yaml"):
        groups = f"{ROOT_DIRECTORY}/inputfiles/inventory/groups.yaml"
    if os.path.exists(f"{ROOT_DIRECTORY}/inputfiles/inventory/defaults.yaml"):
        defaults = f"{ROOT_DIRECTORY}/inputfiles/inventory/defaults.yaml"

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

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)


if __name__ == "__main__":
    main()