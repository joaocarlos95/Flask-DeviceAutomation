import json
import requests
import time

from src.classes.colors import Colors


class Netbox:

    def __init__(self, url, token):

        self.url = f"{url}/api"
        self.token = token

    def get_request(self, endpoint, params=None):

        headers = headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.token}' 
        }

        response = requests.get(f"{self.url}{endpoint}", headers=headers, params=params, verify=False)
        return self.handle_response(response)

    def post_request(self, endpoint, data=None):

        headers = headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.token}' 
        }

        response = requests.post(f"{self.url}{endpoint}", headers=headers, json=data, verify=False)
        return self.handle_response(response)
    
    def handle_response(self, response):

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 400:
                try:
                    error_details = response.json()
                    print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Bad Request")
                    print(json.dumps(error_details, indent=4))
                except json.JSONDecodeError:
                    print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Bad Request Response:", response.text)
            elif response.status_code == 401:
                print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Unauthorized")
            elif response.status_code == 403:
                print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Forbidden")
            elif response.status_code == 404:
                print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Not Found")
            elif response.status_code == 500:
                print(f"{Colors.NOK_RED}[Netbox]{Colors.END} Error {response.status_code}: Internal Server Error")
            else:
                print(f"Unhandled error: {response.text}")
        except Exception as err:
            print(f"Other error occurred: {err}")

    def add_device_type(self, manufacturer:str, model:str, u_height:int, is_full_depth:bool=None, platform:str=None):

        data = {
            "manufacturer": self.get_manufacturer_id(manufacturer),
            "model": model,
            "slug": f"{manufacturer}_{model}".replace(' ', '-').lower(),
            "part_number": model,
            "u_height": u_height,
            "is_full_depth": is_full_depth,
            "default_platform": platform
        }

        endpoint = '/dcim/device-types/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new device type: {data['model']}")
        response = self.post_request(endpoint, data)

    def add_device(self, role:str, model:str, site:str, hostname:str, serial_number:str, status:str='active'):

        data = {
            "name": hostname,
            "role": self.get_device_role_id(role),
            "device_type": self.get_device_type_id(model),
            "serial": serial_number,
            "site": self.get_site_id(site),
            "status": status,
        }

        endpoint = '/dcim/devices/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new device: {hostname}")
        response = self.post_request(endpoint, data)

    def get_manufacturer_id(self, name: str) -> int:

        endpoint = f"/dcim/manufacturers?name={name}"
        response = self.get_request(endpoint)
        manufacturer_id = response['results'][0]['id']
        return manufacturer_id
    
    def get_device_role_id(self, name: str) -> int:

        endpoint = f"/dcim/device-roles?name={name}"
        response = self.get_request(endpoint)
        device_role_id = response['results'][0]['id']
        return device_role_id

    def get_device_type_id(self, model: str) -> int:

        endpoint = f"/dcim/device-types?model={model}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device type doesn't exist: {model}")
        device_type_id = response['results'][0]['id']
        return device_type_id

    def get_site_id(self, name: str) -> int:

        endpoint = f"/dcim/sites?name={name}"
        response = self.get_request(endpoint)
        site_id = response['results'][0]['id']
        return site_id





# def get_device_type(id=None):

#     endpoint = 'dcim/device-types'
#     response = requests.get(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)
    
#     if response.status_code != 200:
#         print(f"Couldn't get information, status code: {response.status_code}")
#         return response.status_code, None
#     return response.status_code, response.json()['results']

# def get_manufacturer():

#     endpoint = 'dcim/device-types/?name={}'
#     search = '?name'
#     response = requests.get(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)
    
#     if response.status_code != 200:
#         print(f"Couldn't get information, status code: {response.status_code}")
#         return response.status_code, None
#     return response.status_code, response.json()['results']

# def set_device_type():

#     body = {
        
#     }

#     endpoint = 'dcim/device-types'
#     response = requests.post(f'{url}{endpoint}', headers={'Authorization': f'Token {token}', 'Accept': 'application/json'}, verify=False)

#     return response.status_code



if __name__ == '__main__':
    start_time = time.time()

    url = 'https://10.168.10.81:443'
    token = '4550ebdc9e1f2f5652fb77fa5a2b0def73cac0a7'

    netbox = Netbox(url, token)
    response = netbox.get_request('/device-types')
    print(response.json())