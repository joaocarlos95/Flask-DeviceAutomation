import csv
import inspect
import json
import logging
import os
import re
import yaml
from collections import defaultdict
from datetime import datetime
from getpass import getpass
from jinja2 import Environment, FileSystemLoader
from N2G import yed_diagram
from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_netmiko import netmiko_send_command, netmiko_send_config, netmiko_multiline, netmiko_save_config
from nornir_salt.plugins.functions import ResultSerializer
from nornir_utils.plugins.tasks.files import write_file
from ntc_templates.parse import parse_output
from OuiLookup import OuiLookup
from typing import Literal

from .decorators import write_to_file
from .device import Device
from .colors import Colors


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    filename='PANDA.log', 
    filemode='w'
)


# Define environment variable for TextFSM, so that the package can get the correct templates
os.environ['NTC_TEMPLATES_DIR'] = os.path.join(os.path.dirname(__file__), '../dep/ntc-templates/ntc_templates/templates')

MAX_WORKERS = 40



class NetworkHandler:
    '''
    
    Class used to define client variables, which are used by other classes, and 
    to define the script main execution, namely import and export data.

    Attributes:
        dir (str): Main directory where the client is located
        name (str): Name of the client
        nornir (InitNornir): Nornir class to interact with the devices
    '''

    def __init__(self, netbox_url: str=None, netbox_token: str=None, host_file: str=None, group_file: str=None, defaults_file: str=None):

        if netbox_url and netbox_token:
            inventory = {
                "plugin": "NetBoxInventory2",
                "options": {
                    "nb_url": netbox_url,
                    "nb_token": netbox_token,
                    "ssl_verify": False,
                    "use_platform_slug": True
                }
            }
        else:
            host_file = os.path.join(os.path.dirname(__file__), '../inputfiles/inventory/hosts.yaml') if not host_file else host_file
            group_file = os.path.join(os.path.dirname(__file__), '../inputfiles/inventory/groups.yaml') if not group_file else group_file
            defaults_file = os.path.join(os.path.dirname(__file__), '../inputfiles/inventory/defaults.yaml') if not defaults_file else defaults_file

            inventory = {
                "plugin": "SimpleInventory",
                "options": {
                    "host_file": host_file,
                    "group_file": group_file,
                    "defaults_file": defaults_file
                }
            }

        # Define the inventory as a dictionary with the hosts, groups and defaults as its keys
        self.nornir = InitNornir(
            config_file=f"{os.path.dirname(__file__)}/../config.yaml",
            inventory=inventory
        )

    def get_j2_template(self):
        '''
        Define the directory of jinja2 templates and specify the base template (skeleton) to be loaded
        The base_config.j2 template will then be extended by the child templates, specified by the 
        config_blocks variable passed in the constructor
        '''

        # Load the base template and assign it to a variable for further usage
        env = Environment(
            loader=FileSystemLoader(f"{os.path.dirname(__file__)}/../jinja2_templates"), 
            trim_blocks=True, 
            lstrip_blocks=True)
        self.j2_template = env.get_template('base_config.j2')

    def get_j2_data(self):
        '''
        Get the data to be used in the jinja2 template, from a YAML file
        '''

        # Open the default config_data.yaml file and load the content to a variable
        with open(f"{self.dir}/inputfiles/config_data.yaml") as file:
            self.j2_data = yaml.safe_load(file)


    # def nornir_get_devices(self):
    #     '''
    #     Get device list from Nornir inventory and create a device object with the information
    #     collected from it
    #     '''

    #     for host, host_object in self.nornir.inventory.hosts.items():
    #         credentials = {
    #             'username': host_object.username,
    #             'password': host_object.password,
    #             'enable_secret': None
    #         }
    #         device = Device(self, host_object.platform, host_object.hostname, credentials)
    #         self.device_list.append(device)

    def get_devices_from_csv(self):
        '''
        Get device list from .csv file and create a device object with the information
        collected from it. If a keepass database is used to obtain device credentials, this function
        will call the get_kdbx_credentials function to get the credentials.
        '''

        # Load client devices information from .csv file present in the client directory
        if os.path.exists(f"{self.dir}/inputfiles/device_list.csv"):
            path = f"{self.dir}/inputfiles/device_list.csv"
        # If this file is not present in the client directory, open the default one 
        else:
            path = f"{os.path.dirname(__file__)}/../inputfiles/device_list.csv"

        with open(path, mode='r', encoding='utf-8') as file:
            for row in csv.DictReader(file, skipinitialspace=True,):
                
                # Ignore devices commented
                if row['vendor_os'].startswith('#'):
                    continue
                else:
                    # Credentials in .csv file have higher priority than in keepass database
                    if row['username'] != '' and row['password'] != '':
                        credentials = {
                            'username': row['username'],
                            'password': row['password'],
                            'enable_secret': row['enable_secret']
                        }                   
                    # Check if keepass has device credentials
                    elif self.kdbx_database:
                        try:
                            credentials = self.get_kdbx_credentials(self.kdbx_database, row['ip_address'])
                        except Exception as exception:
                            raise exception
                    # Couldn't find credentials neither in .csv file nor .kdbx file
                    else:
                        credentials = {
                            'username': None,
                            'password': None,
                            'enable_secret': None
                        }

                # Create a new Device object and append it to the list of devices
                device = Device(self, row['vendor_os'], row['ip_address'], credentials)
                self.device_list.append(device)

    def get_device_filtered_by_name(self, hostname: str=None):
        return self.nornir.filter(F(name__eq=hostname))
    
    def add_devices_credentials(self, nornir, username: str=None, password: str=None):
        for hostname, host_obj in nornir.inventory.hosts.items():
            host_obj.username = username
            host_obj.password = password

    def get_kdbx_database(self, filename):
        '''
        Get keepass database from .kdbx file. This database will be later iterated through to get the device credentials
        '''

        try:
            kdbx_password = getpass(f"{Colors.OK_YELLOW}[>]{Colors.END} Please insert your Keepass password: ")
            # Load .kdbx file, passing in the argument the filename and respective password
            kdbx_database = PyKeePass(filename, password=kdbx_password)
        except Exception as exception:
            if 'No such file or directory:' in str(exception):
                print(f"{Colors.NOK_RED}[!]{Colors.END} Error getting keepass database)")
                raise Exception(f"{Colors.NOK_RED}[!]{Colors.END} Error getting keepass database)")
            elif len(str(exception)) == 0:
                print(f"{Colors.NOK_RED}[!]{Colors.END} Wrong keepass password")
                raise Exception(f"{Colors.NOK_RED}[!]{Colors.END} Wrong keepass password")
            else:
                raise Exception(f"{Colors.NOK_RED}[!]{Colors.END} Error in {inspect.currentframe().f_code.co_name}", exception)
        
        return kdbx_database


    def get_kdbx_credentials(self, kdbx_database, ip_address):
        '''
        Get device credentials from keepass database, specifying the client name and device
        IP address.
        '''
    
        # Find client group within keepass, using its name
        group = kdbx_database.find_groups(name=self.name, first=True)
        if not group:
            print(f"{Colors.NOK_RED}[!]{Colors.END} Group {self.name} doesn't exist in keepass database")
            raise Exception(f"{Colors.NOK_RED}[!]{Colors.END} Group {self.name} doesn't exist in keepass database")

        # Find device credentials, using its IP address 
        entry = kdbx_database.find_entries(group=group, url=ip_address, tags=['SSH', 'Telnet'], recursive=True, first=True)
        if not entry:
            # Find device credentials, using common entry (usually credentials for all devices)
            entry = kdbx_database.find_entries(group=group, title='RADIUS', first=True)
            if not entry:
                print(f"{Colors.NOK_RED}[!]{Colors.END} Couldn't find credentials for device with IP: {ip_address}")
                raise Exception(f"{Colors.NOK_RED}[!]{Colors.END} Couldn't find credentials for device with IP: {ip_address}")

        return {'username': entry.username, 'password': entry.password, 'enable_secret': None}


    def get_commands(self):
        '''
        Get list of all supported commands of this script to be used in GetConfigs.
        '''
        with open(f"{os.path.dirname(__file__)}/../commands.json", 'r', encoding='utf-8') as cmds:
            self.command_list = json.load(cmds)


    def nornir_get_configs(self, get_configs_info: list, nornir_filtered) -> None:
        """
        Function used to interact with the devices in Nornir.

        Args:
            get_configs_info (list): List of config categories to be gathered from the devices
            nornir_filtered (Nornir): Nornir object with the devices to interact with
        """

        def run_get_configs(task: Task, config_info: str) -> Result:
            """
            Nornir task function to send commands to a device and save the output to
            a file.

            Args:
                task (Task): Nornir task object
                config_info (str): Name of the GetConfigs config info

            Returns:
                Result: Nornir result object
            """

            # Get the commands to be sent to the device, based on Netmiko host platform
            commands = self.nornir.config.user_defined['device_data'][config_info]['commands'][task.host.platform]

            # Adjust read_timeout value for potencial longer commands
            if 'read_timeout' in self.nornir.config.user_defined['device_data'][config_info]:
                read_timeout = self.nornir.config.user_defined['device_data'][config_info]['read_timeout']
            else:
                read_timeout = 10

            # Iterate over the commands and run them in the device, saving the output to a file
            for command in commands:
                print(f"{Colors.OK_GREEN}[{task.host.hostname}]{Colors.END} Running command: {command}")

                try:
                    # Get device prompt in order to use it as expect_string when running a command
                    connection = task.host.get_connection('netmiko', task.nornir.config)
                    prompt = connection.find_prompt()
                    # Run the command in the device
                    result = task.run(
                        name=command,
                        task=netmiko_send_command,
                        command_string=command,
                        expect_string=re.escape(prompt),
                        read_timeout=read_timeout
                    )
                except Exception as exception:
                    print(f"{Colors.NOK_RED}[{task.host.hostname}]{Colors.END} {str(exception)}")

                path = f"{self.dir}/outputfiles/GetConfigs/{config_info}/{datetime.now().strftime('%Y%m%d')}/{command.replace(' ', '_')}"
                filename = f"[{datetime.now().strftime('%Y%m%d%H%M%S')}] {task.host.name} ({task.host.hostname}) - {command}.txt"
                os.makedirs(f"{path}", exist_ok=True)

                task.run(
                    name="save_to_file",
                    task=write_file,
                    filename=f"{path}/{filename}",
                    content=result.result
                )

            return Result(host=task.host)

        # Get the results of the GetConfigs from each device, grouped by config category
        self.get_config_results = {}
        for config_info in get_configs_info:
            result = nornir_filtered.run(
                name=config_info,
                task=run_get_configs,
                config_info=config_info
            )
            self.get_config_results[config_info] = result

    def nornir_set_configs(self, nornir_filtered, device_config_list: dict) -> None:
        """
        """
           
        def run_set_configs(task: Task, device_config_list: dict) -> Result:
            '''
            '''

            try:
                
                # Temporary, since there is an issue with send_config for Enterasys
                if task.host.platform == 'enterasys':
                    # Get device prompt in order to use it as expect_string when running a command
                    connection = task.host.get_connection('netmiko', task.nornir.config)
                    prompt = connection.find_prompt()
                    result = task.run(
                        name="set_configs",
                        task=netmiko_multiline,
                        commands=device_config_list[task.host.hostname].split('\n'),
                        expect_string=re.escape(prompt),
                        read_timeout=10,
                    )
                    task.run(
                        name="save_config",
                        task=netmiko_send_command,
                        command_string="save config",
                        expect_string=re.escape(prompt),
                        read_timeout=10,
                    )
                else:
                    # Send the configuration to the device
                    result = task.run(
                        name="set_configs",
                        task=netmiko_send_config,
                        config_commands=device_config_list[task.host.hostname].split('\n')
                    )
                    task.run(
                        name="save_config",
                        task=netmiko_save_config
                    )

            except Exception as exception:
                print(f"{Colors.NOK_RED}[{task.host.hostname}]{Colors.END} {str(exception)}")

            return



            task.run(
                name="save_to_file",
                task=write_file,
                filename=f"{path}/{filename}",
                content=result.result
            )

            return Result(host=task.host)
        
        self.get_config_results = {}
        result = nornir_filtered.run(
            name="set_configs",
            task=run_set_configs,
            device_config_list=device_config_list
        )
        return


            
    @write_to_file
    def nornir_generate_data_dict(self) -> dict:
        '''
        Generate a data structured with all the data used to interact with the devices and the
        output of the interaction. Only the relevant data will be stored
        '''
       
        def update_mac_address_table(output_parsed):
            for i in output_parsed:
                try:
                    i['vendor'] = list(OuiLookup().query(i['mac_address'])[0].values())[0]                   
                except Exception as exception:
                    if 'could not be found' in str(exception):
                        i['vendor'] = ''
            return output_parsed

        script_data = {
            'client_dir': self.dir,
            'get_configs': {}
        }

        for config_info, config_info_result in self.get_config_results.items():
            if config_info not in script_data['get_configs']:
                script_data['get_configs'][config_info] = {}

            config_info_result_serialized = ResultSerializer(config_info_result, add_details=True)
            for host, host_result in config_info_result_serialized.items():
                del host_result[config_info]
                if 'save_to_file' in host_result.keys():
                    del host_result['save_to_file']
                hostname = f"{host} ({self.nornir.inventory.hosts[host].hostname})"

                command_result_dict = {}
                for command, command_result in host_result.items():

                    output_parsed = self.parse_command_result(
                        device_information=self.nornir.inventory.hosts[host],
                        config_info=config_info,
                        textfsm_args={
                            'data': command_result['result'],
                            'platform': self.nornir.inventory.hosts[host].platform,
                            'command': command
                        }   
                    )
                    
                    if f"update_{config_info}" in locals():
                        output_parsed = locals()[f"update_{config_info}"](output_parsed)

                    command_result_dict[command] = {
                        'output': command_result['result'],
                        'output_parsed': output_parsed,
                        'status': 'Failed' if command_result['failed'] else 'Success'
                    }
                
                script_data['get_configs'][config_info][hostname] = command_result_dict

        return script_data


    def parse_command_result(self, device_information, config_info, textfsm_args) -> list|None:
        '''
        Use TextFSM to parse the output of the command. The get_structured_data receives the raw
        output, device platform and command issued.
        '''
               
        try:
            print(f"{Colors.OK_GREEN}[{device_information.hostname}]{Colors.END} Parsing output: {textfsm_args['command']}")
            output_parsed = parse_output(**textfsm_args)
            # Delete output_parsed variable since output couldn't be converted
            if isinstance(output_parsed, str):
                print(f"{Colors.NOK_RED}[{device_information.hostname}]{Colors.END} Couldn't parse the output of the command: {textfsm_args['command']}")
                return None
            
            # For the extreme OS, consider all entries where the protocol is equal to CDP
            if device_information.platform == 'extreme' and config_info == 'CDP Neighbors':
                output_parsed_tmp = []
                for item in output_parsed:
                    if item.get('protocol') == 'ciscodp' or item.get('protocol') == 'Ci':
                        del item['protocol']
                        output_parsed_tmp.append(item)
                output_parsed = output_parsed_tmp
            # For the extreme OS, consider all entries where the protocol is equal to LLDP
            elif device_information.platform == 'extreme' and config_info == 'CDP Neighbors':
                output_parsed_tmp = []
                for item in output_parsed:
                    if item.get('protocol') == 'lldp' or item.get('protocol') == 'LL':
                        del item['protocol']
                        output_parsed_tmp.append(item)
                output_parsed = output_parsed_tmp
            
            # For the extreme EXOS, split the switch-stacks into multiple entries
            elif device_information.platform == 'extreme_exos' and config_info == 'Device Information':
                output_parsed_tmp = []
                # For each device in the stack, create a new entry
                for entry in output_parsed:
                    serial_numbers = entry['serial_number']
                    hardware_items = entry['hardware']
                    # Create a new entry for each combination of serial number and hardware item
                    for serial_number, hardware_item in zip(serial_numbers, hardware_items):
                        new_entry = {
                            'location': entry['location'],
                            'mac_addr': entry['mac_addr'],
                            'current_time': entry['current_time'],
                            'last_boot': entry['last_boot'],
                            'uptime': entry['uptime'],
                            'version': entry['version'],
                            'serial_number': serial_number,
                            'hardware': hardware_item,
                        }
                        output_parsed_tmp.append(new_entry)
                output_parsed = output_parsed_tmp

            return output_parsed

        except Exception as exception:
            print(f"{Colors.NOK_RED}[{device_information.hostname}]{Colors.END} Couldn't parse the output of the command: {textfsm_args['command']}")
            print(exception)
            return []

    @write_to_file
    def generate_data_dict(self) -> dict:
        '''
        Generate a data structured with all the data used to interact with the devices and the 
        output of the interaction. Only the relevant data will be stored
        '''

        print(f"{Colors.OK_GREEN}[>]{Colors.END} Generating script output")

        # Transform client object in dict and remove unnecessary key/values
        client_dict = self.__dict__.copy()
        del client_dict['kdbx_database']
        del client_dict['command_list']
        del client_dict['nornir']

        # Transform device objects in dict and remove unnecessary key/values
        device_list = []
        for device_obj in self.device_list:
            device_dict = device_obj.__dict__.copy()
            del device_dict['client']
            del device_dict['credentials']
            del device_dict['connection']

            # Transform config objects in dict and remove unnecessary key/values
            config_list = []
            for config_obj in device_obj.config_list:
                config_dict = config_obj.__dict__.copy()
                del config_dict['device']
                config_list.append(config_dict)

            # Replace the config object list by a config dict list
            device_dict['config_list'] = config_list
            device_list.append(device_dict)
        # Replace the device object list by a device dict list
        client_dict['device_list'] = device_list
        return client_dict

    @write_to_file
    def nornir_generate_config_parsed(self, script_data: dict) -> dict:
        
        output_parsed_dict = defaultdict(list)  # Using defaultdict to handle missing keys gracefully

        for config_info, config_info_result in script_data['get_configs'].items():
            output_parsed_dict[config_info] = defaultdict(list)
            for device, device_result in config_info_result.items():  # Handling missing 'device_list'
                merged_output = {
                    'device_hostname': device.split('(')[0].strip(),
                    'device_ip_address': device.split('(')[1].split(')')[0].strip()
                }
                for command, command_result in device_result.items():
                    if 'output_parsed' in command_result.keys() and command_result['output_parsed'] != None:
                        for output_parsed in command_result['output_parsed']:
                            output_parsed_dict[config_info][command.replace(' ', '_')].append({**merged_output, **output_parsed})
                    else:
                        output_parsed_dict[config_info][command.replace(' ', '_')].append(merged_output)

        return output_parsed_dict

    @write_to_file
    def generate_config_parsed(self, script_data: dict) -> dict:
        
        print(f"{Colors.OK_GREEN}[>]{Colors.END} Merging output parsed")
        output_parsed_dict = defaultdict(list)  # Using defaultdict to handle missing keys gracefully

        for device in script_data.get('device_list', []):  # Handling missing 'device_list'
            for config in device.get('config_list', []):  # Handling missing 'config_list'
                config_info = config.get('info')
                merged_output = {
                    'device_hostname': device['hostname'],
                    'device_ip_address': device['ip_address']
                }
                if 'output_parsed' in config:
                    for output_parsed in config['output_parsed']:
                        output_parsed_dict[config_info].append({**merged_output, **output_parsed})
                else:
                    output_parsed_dict[config_info].append(merged_output)

        return output_parsed_dict

    def generate_graph(self, output_parsed:dict, discovery_protocol:Literal['CDP', 'LLDP']) -> dict:
        '''
        Generate a dict variable representing network diagram based on neighbors adjancies
        '''

        if discovery_protocol == 'CDP':
            output_parsed = output_parsed['Network Diagram CDP']
        elif discovery_protocol == 'LLDP':
            output_parsed = output_parsed['Network Diagram LLDP']

        graph = {'nodes': [], 'links': []}
        for entry in output_parsed:
            device_ip_address = entry['device_ip_address'] if 'device_ip_address' in entry else ''
            device_hostname = entry['device_hostname'] if 'device_hostname' in entry else ''
            remote_ip_address = entry['remote_ip_address'] if 'remote_ip_address' in entry else ''
            remote_host = entry['remote_host'] if 'remote_host' in entry else ''
            local_port = entry['local_port'] if 'local_port' in entry else ''
            remote_port = entry['remote_port'] if 'remote_port' in entry else ''

            graph['nodes'].append({
                'id': remote_ip_address,
                'top_label': remote_host,
                'bottom_label': remote_ip_address
            })
            graph['links'].append({
                'source': device_ip_address, 
                'target': remote_ip_address,
                'src_label':local_port,
                'trgt_label': remote_port
            })
        graph['nodes'].append({
            'id': device_ip_address,
            'top_label': device_hostname,
            'bottom_label': device_ip_address
        })

        print(graph)
        return graph

    @write_to_file
    def generate_diagram(self, graph):
        '''
        Generate network diagram in drawio format, based on neighbors adjancies
        '''

        print(f"{Colors.OK_GREEN}[>]{Colors.END} Generating Network Diagram")
        diagram = yed_diagram()
        diagram.from_dict(graph)
        diagram.layout(algo='tree')

        return diagram












    def generate_config_report(self):
        ''' Generate report for commands executed on the device'''

        print('[>] Generating configuration report')
        report = []
        for device in self.report:
            # For each command runned on a device, create a new .csv row
            if device['command_list'] == []:
                report.append({
                    'device_hostname': device['hostname'],
                    'device_ip_address': device['ip_address'],
                    'info': '',
                    'command': '',
                    'status': device['status']
                })
            for command in device['command_list']:
                if command['status'] == None:
                    status = device['status']
                else:
                    status = command['status']
                report.append({
                    'device_hostname': device['hostname'],
                    'device_ip_address': device['ip_address'],
                    'info': command['info'],
                    'command': command['command'],
                    'status': status
                })

        self.write_csv(report, filename='Configuration Report')

    def generate_upgrade_report(self):
        ''' Generate report for devices upgrade process '''

        print('[>] Generating upgrade report')
        report = []
        for device in self.report:
            # For each command runned on the device, create a new .csv row
            for upgrade in device['upgrade_list']:

                # Authentication to the device failed
                if 'Authentication failed' in upgrade['status']:
                    current_release = None
                # Devices with success login
                else:
                    current_release = upgrade['current_release']['version']
                
                # Devices not in scope
                if upgrade['target_release'] == None:
                    target_release = None
                # Devices in scope
                else:
                    target_release = upgrade['target_release']['version']
                
                report.append({
                    'device_hostname': device['hostname'],
                    'device_ip_address': device['ip_address'],
                    'step': upgrade['step'],
                    'current_release': current_release,
                    'target_release': target_release,
                    'status': upgrade['status']
                })

        self.write_csv(report, filename='Upgrade Report')