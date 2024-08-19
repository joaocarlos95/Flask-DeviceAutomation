from classes.templater import Templater

def main():

    template_file = 'roles/extreme_exos_access_switch.j2'
    j2_file = 'C:/Users/jlcosta/OneDrive - A2itwb Tecnologia S.A/01. Clientes/ANA Aeroportos/04. Automation/inputfiles/config_data.yaml'
    vendor_os = 'extreme_exos'
    config_blocks = ['snmp']
    comment_char = '#'

    j2_template = get_j2_template(template_file)
    j2_data = get_j2_data_from_file(j2_file)

    j2_data = j2_data[config_blocks[0]] 
    j2_data['config_blocks'] = config_blocks
    j2_data['vendor_os'] = vendor_os
    j2_data['comment_char'] = comment_char

    result = render_j2_template(j2_template, j2_data)
    print(result)
    return

if __name__ == "__main__":
    main()