import json
import requests
import time

from .colors import Colors


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

    def patch_request(self, endpoint, data=None):

        headers = headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.token}' 
        }

        response = requests.patch(f"{self.url}{endpoint}", headers=headers, json=data, verify=False)
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

    # DCIM

    def create_device_type(self, manufacturer:str, model:str, u_height:int, is_full_depth:bool=None, platform:str=None):

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

    def get_device_type_by_model(self, model: str) -> int:

        endpoint = f"/dcim/device-types?model={model}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device type doesn't exist: {model}")
        return response['results'][0]

    def create_device(self, role:str, model:str, site:str, hostname:str, serial_number:str, status:str='active'):

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

    def get_device_by_name(self, name: str) -> int:

        endpoint = f"/dcim/devices/?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device {name} doesn't exist")
        return response['results'][0]

    def create_interface(self, hostname, name, port_type, enabled, mode=None, tagged_vlan: list=[], untagged_vlan: int=None):

        data = {
            'device': self.get_device_by_name(hostname)['id'],
            'name': name,
            'type': port_type,
            'enabled': enabled,
            'mode': mode,
            'tagged_vlans': tagged_vlan,
            'untagged_vlan': untagged_vlan
        }

        endpoint = '/dcim/interfaces/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new interface {name} in device {hostname}")
        response = self.post_request(endpoint, data)

    def update_interface(self, device: str, name: str, port_type: str=None, enabled: bool=None, mode: str=None, tagged_vlan: list=[], untagged_vlan: int=None):

        data = {
            'type': port_type,
            'enabled': enabled,
            'mode': mode,
            'tagged_vlans': tagged_vlan,
            'untagged_vlan': untagged_vlan
        }

        interface = self.get_interface_by_name(device, name)
        if not interface:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Interface {name} in device {device} doesn't exist")
        
        endpoint = f"/dcim/interfaces/{interface['id']}/"
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Updating interface {name} in device {device}")
        response = self.patch_request(endpoint, data)

    def get_interface_by_name(self, device: str, name: str) -> int:

        device_id = self.get_device_by_name(device)['id']
        endpoint = f"/dcim/interfaces/?device_id={device_id}&name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Interface {name} in device {device} doesn't exist")
        return response['results'][0]

    def get_manufacturer_by_name(self, name: str) -> int:

        endpoint = f"/dcim/manufacturers?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Manufacturer {name} doesn't exist")
        return response['results'][0]
    
    def get_device_role_by_name(self, name: str) -> int:

        endpoint = f"/dcim/device-roles?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device role {name} doesn't exist")
        return response['results'][0]

    def get_site_by_name(self, name: str) -> int:

        endpoint = f"/dcim/sites?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Site {name} doesn't exist")
        return response['results'][0]

    # Circuits

    def get_provider_by_name(self, name: str) -> int:

        endpoint = f"/circuits/providers?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Provider {name} doesn't exist")
        return response['results'][0]

    def get_provider_account_by_account_id(self, account_id: str) -> int:

        endpoint = f"/circuits/provider-accounts?account={account_id}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Provider Account with ID {account_id} doesn't exist")
        return response['results'][0]

    def create_circuit(self, cid: str, provider: str, type: str, status: str, provider_account: str=None, tenant: str=None, commit_rate: str=None, description: str=None, custom_fields: dict=None):

        data = {
            "cid": cid,
            "provider": self.get_provider_by_name(provider)["id"],
            "type": self.get_circuit_type_by_name(type)["id"],
            "status": status,
            "provider_account": self.get_provider_account_by_account_id(provider_account)["id"],
            "tenant": self.get_tenant_by_name(tenant)["id"],
            "commit_rate": commit_rate,
            "description": description,
            "custom_fields": custom_fields
        }
        
        endpoint = '/circuits/circuits/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new circuit {cid}")
        response = self.post_request(endpoint, data)

    def get_circuit_type_by_name(self, name: str) -> int:

        endpoint = f"/circuits/circuit-types?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Circuit Type {name} doesn't exist")
        return response['results'][0]

    # Tenancy

    def get_tenant_by_name(self, name: str) -> int:

        endpoint = f"/tenancy/tenants?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Tenant {name} doesn't exist")
        return response['results'][0]

    # IPAM

    def get_prefix_by_prefix(self, prefix: str) -> int:

        endpoint = f"/ipam/prefixes/?prefix={prefix}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Prefix {prefix} doesn't exist")
        return response['results'][0]

    def create_vlan(self, vid: int, name: str, status):

        data = {
            'vid': vid,
            'name': name,
            'status': status
        }

        endpoint = '/ipam/vlans/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new VLAN: {name} ({vid})")
        response = self.post_request(endpoint, data)
    
    def get_vlan_by_vid(self, vid: int) -> int:

        endpoint = f"/ipam/vlans/?vid={vid}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} VLAN {vid} doesn't exist")
        return response['results'][0]