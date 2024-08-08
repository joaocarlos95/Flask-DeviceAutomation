import copy
import csv
import inspect
import re
import os
from datetime import date


COMMAND_LIST = None
OS_IMAGE_LIST = None


class Upgrade():

    def __init__(self, device, step):
        self.device = device
        self.step = step
        self.current_release = None
        self.target_release = None
        self.image_integrity = None
        self.status = None

        # Couldn't connect to the device
        if 'Authentication failed' in self.device.status:
            self.status = self.device.status
            return

        self.get_current_release_info()
        self.get_target_release_info()
        self.get_directories_info()

    def get_current_release_info(self):
        ''' Get current release information and device related information (flash(es) memories 
            and device(s) models '''

        get_configs_info = ['Device Information', 'File System']
        self.device.get_configs(get_configs_info)
           
        for command in self.device.command_list:
            # Get current release information and device hardware model(s)
            if command.info == 'Device Information':
                self.current_release = {
                    'version': command.output_parsed[0]['version'],
                    'image': command.output_parsed[0]['running_image'],
                    'mode': 'Bundle' if command.output_parsed[0]['running_image'].endswith('bin')
                        else 'Install'
                }
                self.device.hardware = command.output_parsed[0]['hardware']

            # Get all memory flashes from the device (1 for standlone device; X for stack devices)
            elif command.info == 'File System':
                for flash in command.output.split('\n'):
                    # Memory flash designation for cisco_ios and cisco_nxos
                    if self.device.vendor_os == 'cisco_ios' or self.device.vendor_os == 'cisco_nxos':
                        # Search for the following patterns in the file system
                        flash_id = re.search('flash:|flash-\d:|flash\d:', flash)
                        if flash_id:
                            self.device.flash[flash_id.group()] = {
                                'free_space': None,
                                'files': []
                            }
                    else:
                        raise Exception(f"Error in {inspect.currentframe().f_code.co_name}",
                            self.vendor_os)

    def get_directories_info(self):
        ''' Get free space from all memory flashes '''

        for flash in self.device.flash.keys():
            # Get the information (free space and files/dirs) for each flash of the device
            cmd = f"{COMMAND_LIST['Device Directory']['commands'][self.device.vendor_os][0]} {flash}"
            command = self.device.create_command('Device Directory', cmd, \
                COMMAND_LIST['Device Directory']['textfsm'])
            command.run()

            file_list = []
            # Append in a list all files/dirs for the flash
            for file in command.output_parsed:
                file_list.append(file['name'])
            
            # Update device flash information
            self.device.flash[flash]['free_space'] = file['total_free']
            self.device.flash[flash]['files'] = file_list
                            
    def get_target_release_info(self):
        ''' Get target release image information '''

        # Get client target software information
        if os.path.exists(f"{self.device.client.dir}/inputfiles/upgrade_list.csv"):
            path = f"{self.device.client.dir}/inputfiles/upgrade_list.csv"
        else:
            path = f"{os.path.dirname(__file__)}/inputfiles/upgrade_list.csv"

        with open(path, mode='r', encoding='utf-8') as file:
            for row in csv.DictReader(file, skipinitialspace=True):
                if row['model'] in self.device.hardware:
                    self.target_release = {
                        'version': row['target_release'],
                        'mode': self.current_release['mode']
                    }
                    self.target_release.update(OS_IMAGE_LIST[self.device.vendor_os]
                        [self.device.hardware[0]][row['target_release']])

        if self.target_release == None:
            print(f"[!] Device model {self.device.hardware} not in scope")
            self.status = 'Device model not in scope'

    def validations(self, validation):
        ''' Run pre validations '''

        # Get client target software information
        if os.path.exists(f"{self.device.client.dir}/inputfiles/command_list.txt"):
            path = f"{self.device.client.dir}/inputfiles/command_list.txt"
        else:
            path = f"{os.path.dirname(__file__)}/inputfiles/command_list.txt"

        # Save current configuration
        self.device.connection.save_config()

        validation_output = ''
        with open(path, mode='r', encoding='utf-8') as file:
            # For each command in command list file, run it and append the output in a variable
            for row in file:
                command = self.device.create_command(f"{validation}", \
                    row.strip(), textfsm=False)
                command.run()
                validation_output += f"{self.device.hostname}# {row.strip()}\n{command.output}\n"
        
        current_datetime = date.today().strftime('%Y%m%d')
        filename = f"[{current_datetime}] {self.device.hostname} ({self.device.ip_address}) - {validation}.txt"
        path = path.replace('/inputfiles/command_list.txt', f"/outputfiles/{validation}/{filename}")
        # Save the command list output in a file
        with open(path, mode='w+', encoding='utf-8') as file:
            file.write(validation_output)

    def release_flash_memory(self, flash):
        ''' Delete old images that are not being used '''

        # Remove old files in Bundle mode
        if self.current_release['mode'] == 'Bundle':
            for file in self.device.flash[flash]['files']:
                # Remove .bin files that are not the running image nor the target image
                if self.target_release == None:
                    return
                if file != (self.current_release['image'] or self.target_release['image']) and \
                    file.endswith('.bin'):
                    self.device.delete_file(flash, file)
        # Remove old files in Install mode
        else:
            # Get version of the inactive files
            output = self.device.connection.send_command(command_string=f"show install active")
            for line in output.split('\n'):
                if 'IMG' in line:
                    # Get the version of the inactive files
                    version = '.'.join(line.split()[-1].split('.')[:-2])
                    for file in self.device.flash[flash]['files']:
                        # Delete file if it's not the running version, nor the package.conf
                        if ('.bin' in file or '.pkg' in file or '.conf' in file) and \
                            version not in file and 'packages.conf' not in file:
                            self.device.delete_file(flash, file)

    def run(self):
        ''' Perform all upgrade steps, in the correct order '''

        # Copy target image to the device
        if self.step == 'Transfer Image' and self.target_release != None:
            self.transfer_image()

        # Check target image integrity
        elif self.step == 'Verify MD5' and self.target_release != None:
           self.verify_image_integrity()

        elif self.step == 'Pre-Validations' or self.step == 'Post-Validations':
            self.validations(self.step)
        
    #     # print(f"[>] Changing boot variable: {file_system}{filename}")
    #     # self.run_command('no boot system', config_mode=True)
    #     # self.run_command(f"boot system {file_system}{filename}", config_mode=True)
        
    #     # boot_path = self.run_command('show boot', textfsm=True)[0]['boot_path']
    #     # if not boot_path == f"{file_system}{filename}":
    #     #     print(f"[!] Boot variable inconsistance: {boot_path}")


    #     # print('[>] Saving configuration')
    #     # self.connection.save_config()

    #     # print('[>] Rebooting')
    #     # self.connection.send_command('reload', expect_string=r'confirm')
    #     # self.connection.send_command('\n')

    # TO BE DONE: Merge if/elif condition for C2960 models (standalone and stack image copy)
    # TO BE DONE: Split stack from non-stack devices
    # TO BE DONE: Use only 1 for cycle to go over all flashes and perform the necessary steps
    def transfer_image(self):
        ''' Transfer image to device flash '''

        '''
            STRUCTURE:
                1. Standalone + Bundle
                2. Standalone + Install
                3. Stack + Bundle
                4. Stack + Install (merge with 2. ???) 
        '''

        # Check if current image is the running image of the device
        if self.current_release['version'] in self.target_release['version']:
            print(f"[!] Device {self.device.hostname} ({self.device.ip_address}) already upgraded to {self.target_release['version']}")
            self.status = 'Already upgraded'
            return
       
        # Get the list of flashes that doesn't have the image on it
        flash_without_target_image = copy.deepcopy(self.device.flash)
        for flash, flash_data in self.device.flash.items():
            # Ignore flashes that already have the image
            if self.target_release['image'] in flash_data['files']:
                # flash_list_copy contains all flashes that doesn't have the target image
                del flash_without_target_image[flash]

        # Target image already present in switch/switch stack
        if len(flash_without_target_image) == 0:
            print(f"[>] Image {self.target_release['image']} already in {' '.join(self.device.flash.keys())}")
            self.status = 'Done'
            return

        # Upload image to standalone switch
        if len(self.device.hardware) == 1:
            flash = list(self.device.flash.keys())[0]
            self.upload_image(flash)
        # Upload image to switch stack
        else:
            print("NEEDS TO BE DONE - TRANSFER IMAGE FOR STACK DEVICES")
            # Process to transfer image to all members in cisco_os models 2960
            if self.device.vendor_os == 'cisco_ios' and any('2960' in model for model in \
                self.device.hardware):
                for flash in flash_without_target_image:
                     self.upload_image(flash)
            # Process to transfer image to remaining switch/models
            else:
                # PASSAR IMAGEM SÓ PARA A FLASH PRINCIPAL FLASH: OR BOOTFLASH:
                pass
        
        # Update status of image transfer
        if self.status == None: self.status = 'Done'

    def upload_image(self, flash):
        ''' Upload target image to the switch, performing all necessary validations in advance ''' 

        try:
            # Delete old images before copy target image to device flash 
            #self.release_flash_memory(flash)
            # Update information of device flash
            self.get_directories_info()
            if self.device.flash_has_space(flash, self.target_release['space']):
                # Copy target image to device flash
                self.device.send_file(self.device.client.ftp_server, flash, \
                    self.target_release['image'])
            else:
                print("[!] Couldn't free up some space for the target image")
                self.status = "Couldn't free up some space for the target image"
                    
        except Exception as exception:
            if 'Error opening' in str(exception):
                self.status = f"Couln't copy image {self.target_release['image']} to {flash}"  
                return

            raise Exception(f"Error in {inspect.currentframe().f_code.co_name}", exception)

    # TO BE DONE: Validations on stack devices
    def verify_image_integrity(self):
        ''' Check MD5 integrity of target images '''

        # For Bundle and Install mode, verify image integrity on device flash/flashes
        for flash, flash_data in self.device.flash.items():
            if self.target_release['image'] not in flash_data['files']:
                # Target image is not in device flash
                print(f"[!] Image {self.target_release['image']} not in {flash}")
                self.status = f"Image {self.target_release['image']} not in {flash}"
                return
            else:
                # Run MD5 checksum of the target image
                md5 = self.device.md5_checksum(flash, self.target_release['image'], \
                    self.target_release['md5'])
                if not md5:
                # File compromised
                    print(f"[!] MD5 NOk for image {flash}{self.target_release['image']}")
                    self.status = 'MD5 NOk'
                    return
                else:
                    # MD5 validated
                    print(f"[>] MD5 Ok for image {flash}{self.target_release['image']}")
                    self.status = 'Done'