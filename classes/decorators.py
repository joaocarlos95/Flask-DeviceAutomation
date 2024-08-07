import json
import os
import re
import pandas as pd
from datetime import datetime
from .colors import Colors


def write_to_file(func):
    '''
    Decorator used to save data returned by the interaction with the network devices
    '''
    def wrapper(self, *args, **kwargs):
        output_data = func(self, *args, **kwargs)

        def save_file_excel_tabs(path, filename, data):

            os.makedirs(f"{path}", exist_ok=True)
            filename = re.sub(r'[\\/*?:"<>|]', '', filename)

            with pd.ExcelWriter(f"{path}/{filename}", engine='xlsxwriter') as writer:
                for command, details in data.items():
                    df = pd.DataFrame(details)
                    df.to_excel(writer, sheet_name=command[:31], index=False)

        def save_file(path, filename, data):
            '''
            Save the data in the corresponding file, using the appropriate method to do it
            '''

            # If there ir nothing to write in the file, exit this function
            if not data:
                print(f"{Colors.NOK_RED}[{self.device.ip_address}]{Colors.END} Output not saved due to lack of data")
                return
            # Create the folder where the file will be written, only if doesn't exist yet
            os.makedirs(f"{path}", exist_ok=True)

            # Remove special characters from the filename
            filename = re.sub(r'[\\/*?:"<>|]', '', filename)

            # Save .xlsx files using pandas
            if filename.endswith('.xlsx'):
                df = pd.DataFrame(data=data)
                df.to_excel(f"{path}/{filename}", index=False)
            # Save .grphml files
            elif filename.endswith('.graphml'):
                data.dump_file(filename=filename, folder=path)
            # Save remaining types of files, with opening a file with write permissions
            else:
                with open(f"{path}/{filename}", mode='w', encoding='utf-8') as file:
                    # Save .txt files
                    if filename.endswith('.txt'):
                        file.write(data)
                    # Save .json files
                    elif filename.endswith('.json'):
                        json.dump(data, file, indent=2)

        # Get current date and datetime for output organization purposes    
        current_date = datetime.now().strftime('%Y%m%d')
        current_datetime = datetime.now().strftime('%Y%m%d%H%M%S')

        # Create the filename for the command runned on the device or configuration generated
        if func.__qualname__ == 'GetConfigs.get_config':
            command = kwargs['command']
            path = f"{self.device.client.dir}/outputfiles/{func.__qualname__.split('.')[0]}/{self.info}/{current_date}/{command.replace(' ', '_')}"
            filename = f"[{current_datetime}] {self.device.hostname} ({self.device.ip_address}) - {command}.txt"
            print(f"{Colors.OK_GREEN}[{self.device.ip_address}]{Colors.END} Saving output: {command}")
            save_file(path, filename, output_data)
        elif func.__qualname__ == 'SetConfigs.render_template':
            path = f"{self.device.client.dir}/outputfiles/{func.__qualname__.split('.')[0]}/jinja2_config/{current_date}"
            filename = f"[{current_datetime}] {self.device.hostname} ({self.device.ip_address}) - jinja2_config.txt"
            print(f"{Colors.OK_GREEN}[{self.device.ip_address}]{Colors.END} Saving output: jinja2_config")
            save_file(path, filename, output_data)
        elif func.__qualname__ == 'SetConfigs.send_config':
            path = f"{self.device.client.dir}/outputfiles/{func.__qualname__.split('.')[0]}/jinja2_config_output/{current_date}"
            filename = f"[{current_datetime}] {self.device.hostname} ({self.device.ip_address}) - jinja2_config_output.txt"
            print(f"{Colors.OK_GREEN}[{self.device.ip_address}]{Colors.END} Saving output: jinja2_config_output")
            save_file(path, filename, output_data)

        # Create the filename for the JSON file with all the relevant data of the runned script
        elif func.__qualname__ == 'Client.generate_data_dict':
            path = f"{self.dir}/outputfiles/RAWData/"
            filename = f"[{current_datetime}] script_output.json"
            print(f"{Colors.OK_GREEN}[>]{Colors.END} Saving script output\n    Path: {path}\n    Filename: {filename}")
            save_file(path, filename, output_data)

        elif func.__qualname__ == 'Client.nornir_generate_data_dict':
            path = f"{self.dir}/outputfiles/RAWData/{current_date}"
            filename = f"[{current_datetime}] script_output.json"
            print(f"{Colors.OK_GREEN}[>]{Colors.END} Saving script output\n    Path: {path}\n    Filename: {filename}")
            save_file(path, filename, output_data)

        # Create the filename for the excel file with all merged TextFSM generated output
        elif func.__qualname__ == 'Client.generate_config_parsed':
            for config in output_data.keys():
                path = f"{self.dir}/outputfiles/GetConfigs/{config}/{current_date}"
                filename = f"[{current_datetime}] {config}.xlsx"
                print(f"{Colors.OK_GREEN}[>]{Colors.END} Saving data to excel - {config}")
                save_file(path, filename, output_data[config])

        elif func.__qualname__ == 'Client.nornir_generate_config_parsed':
            for config_info in output_data.keys():
                path = f"{self.dir}/outputfiles/GetConfigs/{config_info}/{current_date}"
                filename = f"[{current_datetime}] {config_info}.xlsx"
                print(f"{Colors.OK_GREEN}[>]{Colors.END} Saving data to excel\n    Path: {path}\n    Filename: {filename}")
                save_file_excel_tabs(path, filename, output_data[config_info])
        # Create network diagram
        elif func.__qualname__ == 'Client.generate_diagram':
            path = f"{self.dir}/outputfiles/GetConfigs/Network Diagram/{current_date}"
            filename = f"[{current_datetime}] Network Diagram.graphml"
            print(f"{Colors.OK_GREEN}[>]{Colors.END} Saving diagram")
            save_file(path, filename, output_data)

        return output_data
    return wrapper