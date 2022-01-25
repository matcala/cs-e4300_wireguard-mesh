import json
import requests
import os
from exceptions import StartupError, DeviceRegistrationError, CannotAddToOverlay, OverlayRegistrationError
from dotenv import load_dotenv


class MeshManager:

    def __init__(self) -> None:
        try:
            load_dotenv()
            self.config = {}
            self._load_config_file()
            self.output_config = {}

            self.default_token_refresh_interval = 2
            self.default_config_update_interval = 2

            self.api_endpoint = self.config.get("mesh_api_endpoint")
            self.api_key = os.environ["API_KEY"]
            self.overlay_api_headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
        except Exception:
            raise StartupError("Error while creating ")

    ##########################   MESH    ##########################

    def _create_mesh(self):
        """
        Iterates through all the overlays names in the config file and
        calls the API to create each one of them.
        After creating the overlays, the respective devices are created and added.
        For each device, produce a config file that will be used by the device's service
        to bootstrap the Wireguard mesh.
        """
        for overlay in self.config.get('overlays'):
            overlay_devices = overlay.get('devices')
            overlay_object = {"overlay_name": overlay.get('overlay_name')}
            overlay_response = self._create_overlay(overlay_object)

            overlay.update(overlay_response.items())

            for device in overlay_devices:
                device_creation_response = self._create_device(device)
                device.update(device_creation_response.items())
                device_signup_response = self._add_device_to_overlay(
                    {"device_id": device['device_id']},
                    overlay['overlay_id']
                )

                interface_obj = self.output_config.get('interface')
                interface_obj['name'] = "wg-" + device["device_name"]
                interface_obj['overlay_id'] = overlay['overlay_id']
                interface_obj['device_id'] = device_creation_response['device_id']
                interface_obj['virtual_address'] = device_signup_response['tunnel_ip']
                interface_obj['listen_port'] = device_creation_response['listen_port']
                interface_obj['token'] = device_creation_response['token']

                self._dump_output_config(device['hostname'], self.output_config)

        print('\n[+++] Mesh creation completed.')

    def _destroy_mesh(self):
        """
        Deletes all devices and overlays present on the management API.
        """
        overlays_response = self._get_overlays()

        if "error" not in overlays_response:
            for overlay_id in overlays_response.get('overlays'):
                self._delete_overlay({"overlay_id": overlay_id})

        devices_response = self._get_devices()
        if "error" not in devices_response:
            for device_id in devices_response.get('devices'):
                self._delete_device({"device_id": device_id})

    ##########################   OVERLAYS    ##########################

    def _create_overlay(self, overlay: dict) -> dict:
        """
        Creates the overlay with the given name.
        Returns overlay object created by the API.
        """
        print(f"[+] Creating overlay: {overlay['overlay_name']}")
        body = json.dumps(overlay)
        response = requests.post(f"{self.api_endpoint}/overlays",
                                 data=body,
                                 headers=self.overlay_api_headers
                                 )

        if response.status_code == 200:
            return response.json()
        else:
            raise OverlayRegistrationError(f'Failed while creating overlay {overlay["overlay_name"]}')

    def _get_overlays(self) -> dict:
        """
        Returns all existing overlays.
        """
        response = requests.get(f"{self.api_endpoint}/overlays",
                                headers=self.overlay_api_headers
                                )

        return response.json()

    def _delete_overlay(self, overlay_id: dict):
        """
        Deletes the overlay with the given id, if present.
        """
        print(f"[-] Deleting overlay: {overlay_id['overlay_id']}")
        response = requests.delete(f"{self.api_endpoint}/overlays/{overlay_id['overlay_id']}",
                                   headers=self.overlay_api_headers
                                   )

    ##########################   DEVICES    ##########################

    def _create_device(self, device: dict) -> dict:
        """
        Creates the passed device object in the API.
        Returns device object created by the API.
        """
        print(f"[+] Creating device: {device['device_name']}")
        body = json.dumps(device)
        response = requests.post(f"{self.api_endpoint}/devices",
                                data=body,
                                headers=self.overlay_api_headers
                                )

        if response.status_code == 200:
            return response.json()
        else:
            raise DeviceRegistrationError(f'Failed while creating device {device["device_name"]}')

    def _get_devices(self) -> dict:
        """
        Returns all existing devices.
        """
        response = requests.get(f"{self.api_endpoint}/devices",
                                headers=self.overlay_api_headers
                                )

        return response.json()

    def _delete_device(self, device_id: dict):
        """
        Deletes the device with device_id, if present.
        """
        print(f"[-] Deleting device: {device_id['device_id']}")
        response = requests.delete(f"{self.api_endpoint}/devices/{device_id['device_id']}",
                                   headers=self.overlay_api_headers
                                   )

    def _add_device_to_overlay(self, device_id: dict, overlay_id: str) -> dict:
        """
        Add a single passed device to the specified overlay.

        device: dict with device full information;
        overlay_id: string of the overlay ID returned by the API during overlay creation.
        """
        print(f"[+] Adding device {device_id['device_id']} to overlay: {overlay_id}")
        body = json.dumps(device_id)
        response = requests.post(f"{self.api_endpoint}/overlays/{overlay_id}/devices",
                                 data=body,
                                 headers=self.overlay_api_headers
                                 )

        if response.status_code == 200:
            return response.json()
        else:
            raise DeviceRegistrationError(
                f'Failed while signing device {device_id["device_id"]} to overlay {overlay_id}')

    #######################################################################################

    def _load_config_file(self):
        with open("config.json", "r") as file:
            self.config = json.load(file)

    def _init_output_config(self):
        self.output_config['interface'] = {}
        self.output_config['manager_server_address'] = self.api_endpoint
        self.output_config['token_refresh_interval'] = self.default_token_refresh_interval
        self.output_config['config_update_interval'] = self.default_config_update_interval

    @staticmethod
    def _dump_output_config(base_filename: str, data: dict):
        with open(f"../wireguard_configs/{base_filename}.json", "w") as config:
            config.write(json.dumps(data))

    def start(self):
        print('[+++] Mesh manager starting...\n')
        self._init_output_config()
        self._destroy_mesh()
        self._create_mesh()


if __name__ == "__main__":
    manager = MeshManager()
    manager.start()
