from classes.templater import Templater

def main():

    j2_file = 'C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation/inputfiles/config_data.yaml'
    vendor_os = 'extreme_exos'
    config_blocks = ['general', 'vlan', 'device_management', 'port', 'tacacs', 'radius', 'snmp', 'cdp', 'lldp', 'syslog', 'spanning_tree']

    templater = Templater(vendor_os=vendor_os, config_blocks=config_blocks)
    j2_template = templater.get_j2_template()
    j2_data = templater.get_j2_data_from_file(j2_file)

    config = templater.render_config(j2_template, j2_data, hostname='LIS-T001-LAN-SA-LAB.A')

if __name__ == "__main__":
    main()