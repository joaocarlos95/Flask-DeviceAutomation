
import inspect
from netmiko import ConnectHandler
from .colors import Colors
from .upgrade import Upgrade
from .configs import GetConfigs, SetConfigs


WITHOUT_ENABLE_SECRET = ['extreme', 'extreme_exos']
PAGING_DISABLE = {
    'extreme': {
        'enable': 'set length 40',
        'disable': 'set length 0'
    },
    'extreme_exos': {
        'enable': 'enable cli paging session',
        'disable': 'disable cli paging session'
    }
}

class Device():
    '''
    Class used to interact with the network devices using netmiko package
    '''

    def __init__(self, client, vendor_os, ip_address, credentials):
        '''
        Constructor used to initilize a new Device object, specifying its client, vendor_os (
        according to netmiko and textfsm packages), ip address and credentials for remote access.
        '''
        self.client = client
        self.vendor_os = vendor_os
        self.ip_address = ip_address
        self.credentials = credentials
        self.hostname = None
        self.connection = None
        self.config_list = []

    def clear_counters(self):
        ''' Clear device counters '''

        self.connection.send_command('clear counters', expect_string=r'confirm')
        self.connection.send_command('\n')

    def connect(self, method='ssh'):
        ''' Connect to the device in the following order: SSH, Telnet '''

        def ssh_connect():
            ''' Establish a SSH connection with the device '''

            self.connection = ConnectHandler(
                device_type = self.vendor_os,
                ip = self.ip_address, 
                username = self.credentials['username'],
                password = self.credentials['password'],
                banner_timeout = 10,
            )

        def telnet_connect():
            ''' Establish a Telnet connection with the device '''

            self.connection = ConnectHandler(
                device_type = f"{self.vendor_os}_telnet",
                ip = self.ip_address,
                username = self.credentials['username'],
                password = self.credentials['password'],
                banner_timeout = 10,
            )

        try:
            # Connect to the device through SSH
            if method == 'ssh': ssh_connect()
            # Connect to the device through Telnet
            else: telnet_connect()
            
            # Disable paging to specific devices
            if self.vendor_os in PAGING_DISABLE.keys():
                self.connection.send_command(PAGING_DISABLE[self.vendor_os]['disable'])

            # Method save_config doesn't work in extreme devices
            if self.vendor_os == 'extreme':
                pass
            else:
                self.connection.save_config()

        except Exception as exception:
            if 'No connection could be made because the target machine actively refused it' in str(exception) or \
                'Connection refused' in str(exception):
                # Connect to the device through Telnet
                if method == 'ssh':
                    print(f"{Colors.OK_YELLOW}[{self.ip_address}]{Colors.END} Couldn't connect via SSH, trying via Telnet")
                    self.connect('telnet')
                else:          
                    print(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} Connection refused by device")
                    self.status = 'Device refused connection'
                    return
            elif 'TCP connection to device failed' in str(exception) or 'Operation timed out' in str(exception):
                if method == 'ssh':
                    print(f"{Colors.OK_YELLOW}[{self.ip_address}]{Colors.END} Couldn't connect via SSH, trying via Telnet")
                    self.connect('telnet')
                else:
                    print(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} TCP connection failed")
                    self.status = 'TCP connection failed'
                    return
            elif 'Authentication to device failed' in str(exception) or 'Login failed' in str(exception):
                print(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} Authentication failed")
                self.status = 'Authentication failed'
                return
            elif 'must be exactly 1024, 2048, 3072, or 4096 bits long' in str(exception):
                if method == 'ssh':
                    print(f"{Colors.OK_YELLOW}[{self.ip_address}]{Colors.END} Couldn't connect via SSH, trying via Telnet")
                    self.connect('telnet')
                else:
                    print(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} Issue with the SSH keys")
                    self.status = 'Issue with the SSH keys'
                    return
            elif 'A connection attempt failed' in str(exception) or 'No existing session' in \
                str(exception) or "Unsupported 'device_type'" in str(exception) or \
                'An established connection was aborted by the software in your host machine' in str(exception):
                print(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} Couldn't connect")
                self.status = "Couldn't connect"
                return
            else:
                raise Exception(f"{Colors.NOK_RED}[{self.ip_address}]{Colors.END} Error in {inspect.currentframe().f_code.co_name}", exception, self.ip_address)

        # If no connection could be made exit
        if self.connection == None: return

        # If not in enable secret mode, enter the enable secret password 
        if not self.connection.check_enable_mode() and self.vendor_os not in WITHOUT_ENABLE_SECRET:
            self.connection.secret = self.credentials['enable_secret']
            self.connection.enable()

        # Get the hostname of the device 
        self.hostname = self.connection.find_prompt()[:-1]
        self.status = 'Connected'
        print(f"{Colors.OK_GREEN}[{self.ip_address}]{Colors.END} Connected")

    def delete_file(self, flash, file):
        ''' Delete file from deviice flash '''

        print(f"[>] Deleting file {file} from {flash}")      
        output = self.connection.send_command(command_string=f"delete /recursive {flash}{file}", \
            expect_string=r'Delete filename', strip_prompt=False, strip_command=False)
        if "Delete filename" in output:
            output += self.connection.send_command(command_string='\n', expect_string=r'confirm', \
                strip_prompt=False, strip_command=False)
        else:
            print(output)
        if "confirm" in output:
            output += self.connection.send_command(command_string='y', expect_string=r'#', \
                strip_prompt=False, strip_command=False)
                
        print(f"[>] File {file} deleted")

    def disconnect(self):
        ''' Disconnect from the device '''

        # Connection to the device couln't be mande
        if self.connection == None: return

        # Disable paging to specific devices
        if self.vendor_os in PAGING_DISABLE.keys():
            self.connection.send_command(PAGING_DISABLE[self.vendor_os]['enable'])

        # Disconnect from the device
        self.connection.disconnect()
        print(f"{Colors.OK_GREEN}[{self.ip_address}]{Colors.END} Disconnected")

    def flash_has_space(self, flash, needed_space):
        ''' Check if flash as enough space givena needed value '''
        
        # Flash has enough space
        if int(self.flash[flash]['free_space']) - needed_space > 0:
            return True
        # Flash does not have enough space
        else:
            return False
    
    def generate_report(self, report):
        ''' Get configs report for all commands issued '''

        print(f"[>] Generating report for {self.hostname} ({self.ip_address})")
        # Transform device object in dict and remove unnecessary key/values
        device_dict = self.__dict__.copy()
        del device_dict['client']
        del device_dict['credentials']
        del device_dict['connection']

        command_list = []
        for command in self.command_list:
            # Transform command object in dict and remove unnecessary key/values
            command_list_dict = command.__dict__.copy()
            del command_list_dict['device']
            command_list.append(command_list_dict)

        upgrade_list = []
        for step in self.upgrade_list:
            # Transform command object in dict and remove unnecessary key/values
            upgrade_list_dict = step.__dict__.copy()
            del upgrade_list_dict['device']
            upgrade_list.append(upgrade_list_dict)
        
        device_dict['command_list'] = command_list
        device_dict['upgrade_list'] = upgrade_list
        report.append(device_dict)

    # def get_serial_port():
    #     ''' Get serial port to connect to the device '''

    #     ports = serial.tools.list_ports.comports()
    #     for port, description, _ in sorted(ports):
    #         if "USB-to-Serial Comm Port" in description: return port
    #     raise Exception("[!] Serial port not identified")

    def md5_checksum(self, flash, file, md5sum):
        ''' Perform MD5 checksum over a file '''

        print(f"[>] Verifying integrity of file {file}")
        cmd = f"{COMMAND_LIST['MD5 Checksum']['commands'][self.vendor_os][0]} {flash}{file}"
        command = self.create_command('MD5 Checksum', cmd, COMMAND_LIST['MD5 Checksum']['textfsm'])
        command.run()

        if md5sum == command.output.split("= ")[1].strip():
            return True
        else:
            return False
    
    def run_set_configs(self, set_configs_info, report):
        ''' Initiate the process of acquire device information '''

        # Connect to the device
        self.connect()
        # Get the desired configurations
        self.set_configs(set_configs_info)
        # Disconnect from the device
        #self.disconnect()
        # Generate device report and append it to the shared variable
        #self.generate_report(report)           

    # TO BE DONE: Run the first validation commands only once
    def run_upgrade(self, upgrade_steps, report):
        ''' Initiate the uprade process of the device/stack devices. Upgrade steps have a specific
            order, defined in the upgrade.txt file (FIFO) '''

        # Connect to the device
        self.connect()
        # Information to be collected in advance
        for step in upgrade_steps:
            upgrade = Upgrade(self, step)
            self.upgrade_list.append(upgrade)
            upgrade.run()
        # Disconnect from the device
        self.disconnect()
        # Generate device report and append it to the shared variable
        self.generate_report(report)   

    def send_file(self, source, destination, file):
        ''' Copy file from source to destination '''

        try:
            print(f"[>] Copying file {file} to {destination}")
            output = self.connection.send_command(command_string=f"copy {source}{file} {destination}{file}", \
                expect_string=r'Destination filename', strip_prompt=False, strip_command=False)

            if 'Destination filename' in output:
                output += self.connection.send_command(command_string='\n', expect_string=r'#', \
                    strip_prompt=False, strip_command=False, delay_factor=20, read_timeout=1200)
            
            if 'Error' in output:
                print(f"[!] File {file} not copied to {destination}")
                raise Exception(output)
            
            print(f"[>] File {file} copied to {destination}")

        except Exception as exception:
            raise Exception(f"Error in {inspect.currentframe().f_code.co_name}", exception, self.ip_address)

    def set_configs(self, config_blocks: list, j2_data: dict=None, config: list=None) -> None:
        '''
        Connect to the device in order to generate and apply a set of configurations using 
        pre-defined templates and user data. The template is generated based on a list of 
        configuration blocks defined by the user.
        '''
        
        # jinja2 is the default generated in no other is provided in the function
        j2_data = self.client.j2_data if j2_data == None else j2_data

        # Connect to the device
        self.connect()
        # Couldn't connect to the device
        if not self.connection: return

        # Create a SetConfigs object, generate the configuration and send it to the device 
        set_config = SetConfigs(self)
        config = set_config.render_template(config_blocks, j2_data=j2_data) if config == None else config
        print(config)
        self.config_list.append(config)
        set_config.send_config(data=config)
        
        # Disconnect from the device
        self.disconnect()
    
    def generate_config(self, config_blocks: list, j2_data: dict=None, config: list=None) -> None:
        '''
        Generate a set of configurations using pre-defined templates and user data.
        The template is generated based on a list of configuration blocks defined by the user.
        '''
        
        # jinja2 is the default data if no other is provided in the function
        j2_data = self.client.j2_data if j2_data == None else j2_data

        # Create a SetConfigs object and generate the configuration 
        set_config = SetConfigs(self)
        config = set_config.render_template(config_blocks, j2_data=j2_data) if config == None else config
        print(config)
    
    def get_configs(self, get_configs_info: list) -> None:
        '''
        Connect to the device and get the information requested, command by command. For each
        command, a GetConfigs object is created and runned.
        '''

        # Connect to the device
        self.connect()

        for info in get_configs_info:
            # Get each command to be runned on the device
            for command in self.client.command_list[info]['commands'][self.vendor_os]:
                # Create a GetConfigs object and run the command on the device 
                config = GetConfigs(self, info=info)
                self.config_list.append(config)
                
                # If there is a connection to the device, execute the commands
                if self.connection:
                    if self.vendor_os == 'extreme_exos':
                        output = config.get_config(command=command, expect_string=self.connection.find_prompt())
                    else:
                        output = config.get_config(command=command)
                    # Parse the output of the command executed
                    output_parsed = config.parse_output(raw_output=output, platform=self.vendor_os, command=command)

                    # Append to the output_parsed, the vendor of the MAC address found on the port
                    if config.info == 'MAC Address Table':
                        for mac in output_parsed:
                            mac['vendor'] = config.get_mac_vendor(mac['destination_address'])

        # Disconnect from the device
        self.disconnect()

    # def serial_connect(self):

    #     serial_port = self.get_serial_port()
    #     serial_connection = ConnectHandler(
    #         device_type = f"{self.vendor_os}_serial",
    #         username = self.username,
    #         password = self.password,
    #         fast_cli = False,
    #         conn_timeout = 30,
    #         serial_settings = {
    #             "baudrate": serial.Serial.BAUDRATES[12],
    #             "bytesize": serial.EIGHTBITS,
    #             "parity": serial.PARITY_NONE,
    #             "stopbits": serial.STOPBITS_ONE,
    #             "port": serial_port,
    #         },
    #     )
    #     if not self.connection.check_enable_mode():
    #         self.connection.secret = self.enable_secret
    #         self.connection.enable()

    #     self.hostname = self.connection.find_prompt()[:-1]
    #     print(f"[>] Connected to: {self.hostname} (serial port)")
