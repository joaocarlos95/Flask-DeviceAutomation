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

    def get_site_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/sites?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Site {name} doesn't exist")
        return response['results'][0]

    def get_manufacturer_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/manufacturers?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Manufacturer {name} doesn't exist")
        return response['results'][0]

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

    def get_device_type_by_model(self, model: str) -> dict:

        endpoint = f"/dcim/device-types?model={model}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device type doesn't exist: {model}")
        return response['results'][0]

    def get_device_role_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/device-roles?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device role {name} doesn't exist")
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
    
    def update_device(self, current_name: str, name):

        data = {
            'name': name
        }

        device = self.get_device_by_name(name=current_name)
        if not device:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device {current_name} doesn't exist")
        
        endpoint = f"/dcim/devices/{device['id']}/"
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Updating device {current_name}")
        response = self.patch_request(endpoint, data)

    def get_device_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/devices/?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Device {name} doesn't exist")
        return response['results'][0]

    def get_virtual_chassis_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/virtual-chassis/?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Virtual chassis {name} doesn't exist")
        return response['results'][0]

    def update_virtual_chassis(self, current_name: str, name: str=None):

        data = {
            'name': name
        }

        virtual_chassis = self.get_virtual_chassis_by_name(name=current_name)
        if not virtual_chassis:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Virtual Chassis {current_name} doesn't exist")
        
        endpoint = f"/dcim/virtual-chassis/{virtual_chassis['id']}/"
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Updating virtual chassis {current_name}")
        response = self.patch_request(endpoint, data)

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

    def get_interface_by_name(self, device: str, name: str) -> dict:

        device_id = self.get_device_by_name(device)['id']
        endpoint = f"/dcim/interfaces/?device_id={device_id}&name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Interface {name} in device {device} doesn't exist")
        return response['results'][0]

    def get_rearport_by_name(self, name: str) -> dict:

        endpoint = f"/dcim/rear-ports/?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Rear port {name} doesn't exist")
        return response['results'][0]
    
    def create_cables(self, term_a_object_type: str, term_a_object_id: int, term_b_object_type: str, term_b_object_id: int, status: str=None, tenant_id: int=None): 

        data = {
            "a_terminations": [{
                "object_type": term_a_object_type,
                "object_id": term_a_object_id
            }],
            "b_terminations": [{
                "object_type": term_b_object_type,
                "object_id": term_b_object_id
            }],
            "status": status,
            "tenant": tenant_id
        }

        endpoint = '/dcim/cables/'
        print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Creating new cable between {term_a_object_id} ({term_a_object_type}) and {term_b_object_id} ({term_b_object_type})")
        response = self.post_request(endpoint, data)
        
    # Circuits

    def get_provider_by_name(self, name: str) -> dict:

        endpoint = f"/circuits/providers?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Provider {name} doesn't exist")
        return response['results'][0]

    def get_provider_account_by_account_id(self, account_id: str) -> dict:

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

    def update_circuit(self, cid: str, status: str=None, custom_fields: dict=None):

            data = {
                "status": status,
                "custom_fields": custom_fields
            }

            circuit_id = self.get_circuit_by_cid(cid)["id"]

            endpoint = f"/circuits/circuits/{circuit_id}/"
            print(f"{Colors.OK_GREEN}[Netbox]{Colors.END} Updating circuit {cid}")
            response = self.patch_request(endpoint, data)

    def get_circuit_by_cid(self, cid: str) -> dict:

        endpoint = f"/circuits/circuits/?cid={cid}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Circuit {cid} doesn't exist")
        return response['results'][0]

    def get_circuit_type_by_name(self, name: str) -> dict:

        endpoint = f"/circuits/circuit-types?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Circuit Type {name} doesn't exist")
        return response['results'][0]

    def get_circuit_termination_by_cid_and_side(self, cid: str, side: str):

        if side not in ["A", "Z"]:
            raise ValueError("Termination Side must be either 'A' or 'Z'")

        circuit_id = self.get_circuit_by_cid(cid=cid)["id"]
        endpoint = f"/circuits/circuit-terminations/?circuit_id={circuit_id}&term_side={side}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Termination {side} of circuit {cid}doesn't exist")
        return response['results'][0]

    # Tenancy

    def get_tenant_by_name(self, name: str) -> dict:

        endpoint = f"/tenancy/tenants?name={name}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Tenant {name} doesn't exist")
        return response['results'][0]

    # IPAM

    def get_prefix_by_prefix(self, prefix: str) -> dict:

        endpoint = f"/ipam/prefixes/?prefix={prefix}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Prefix {prefix} doesn't exist")
        return response['results'][0]
    
    def get_ip_address_by_address(self, address: str) -> dict:

        endpoint = f"/ipam/ip-addresses/?address={address}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} Address {address} doesn't exist")
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
    
    def get_vlan_by_vid(self, vid: int) -> dict:

        endpoint = f"/ipam/vlans/?vid={vid}"
        response = self.get_request(endpoint)
        if response['count'] == 0:
            raise Exception(f"{Colors.NOK_RED}[Netbox]{Colors.END} VLAN {vid} doesn't exist")
        return response['results'][0]