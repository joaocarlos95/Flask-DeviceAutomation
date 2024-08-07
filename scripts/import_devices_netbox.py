import os
import requests
import time

from classes.network_handler import NetworkHandler


url = 'https://10.168.10.81:443/api/'
token = '8dcca19d59ab1d017825532c9a9404843329334d'

def get_device_type(id=None):

    endpoint = 'dcim/device-types'
    response = requests.get(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)
    
    if response.status_code != 200:
        print(f"Couldn't get information, status code: {response.status_code}")
        return response.status_code, None
    return response.status_code, response.json()['results']

def get_manufacturer():

    endpoint = 'dcim/device-types/?name={}'
    search = '?name'
    response = requests.get(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)
    
    if response.status_code != 200:
        print(f"Couldn't get information, status code: {response.status_code}")
        return response.status_code, None
    return response.status_code, response.json()['results']

def set_device_type():



    body = {
        
    }

    endpoint = 'dcim/device-types'
    response = requests.post(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)

    return response.status_code

if __name__ == '__main__':
    start_time = time.time()
    validations = {'yes': True, 'y': True, 'no': False, 'n': False}

    root_dir = "C:/Users/jlcosta/Desktop/Documents/01. Clientes/ANA Aeroportos/03. Automation"
    client_name = "ANA Aeroportos"
    kdbx_filename = "C:/Users/jlcosta/Desktop/Documents/Credentials.kdbx"

    response_status_code, response_data = get_device_type()
    print(response)

    # Create a new client object
    #client = NC(root_dir, client_name, kdbx_filename=kdbx_filename)
    #print(client.device_list)