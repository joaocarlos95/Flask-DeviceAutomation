import os
import yaml
from datetime import datetime
from jinja2 import Environment, FileSystemLoader


with open(f"{os.path.dirname(os.path.abspath(__file__))}/../inputfiles/config.yaml") as file:
    CONFIG_DATA = yaml.safe_load(file)


class Templater:

    def __init__(self, vendor_os: str, config_blocks: list, comment_char: str=None) -> None:

        self.vendor_os = vendor_os
        self.config_blocks = config_blocks
        self.comment_char = CONFIG_DATA['comment_char'][vendor_os]

    def get_j2_template(self, filename: str=None):
        '''
        Define the directory of Jinja2 templates and specify the base template (skeleton), or a specific template to be loaded.
        In case of base template, it will be extended by the child templates, specified by the config_blocks variable passed in the constructor.
        '''

        # Set up the Jinja2 environment, specifying the directory where the base template is located
        base_dir = f"{os.path.dirname(os.path.abspath(__file__))}/.."
        env = Environment(
            loader=FileSystemLoader([base_dir]), 
            trim_blocks=True, 
            lstrip_blocks=True)
        
        # Load the Jinja2 template specified by the filename parameter or use the base_config.j2 template
        filename = filename if filename else 'base_config.j2'
        j2_template = env.get_template(filename)
        return j2_template

    def get_j2_data_from_file(self, filename: str=None):
        '''
        Get the data to be used in the jinja2 template, from a YAML file
        '''

        # Open the default config_data.yaml file and load the content to a variable
        with open(filename) as file:
            j2_data = yaml.safe_load(file)
        return j2_data

    def render_config(self, j2_template, j2_data, hostname: str=None) -> str:

        j2_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        j2_data['hostname'] = hostname
        j2_data['vendor_os'] = self.vendor_os
        j2_data['comment_char'] = self.comment_char
        j2_data['config_blocks'] = self.config_blocks

        config = j2_template.render(j2_data)
        # Remove all leading spaces in the rendered configuration
        result = '\n'.join([line.lstrip() for line in config.split('\n')])
        return result