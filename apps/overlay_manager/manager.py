import json
from pydoc import resolve
import requests
import os
from exceptions import StartupError, DeviceRegistrationError, CannotAddToOverlay
from dotenv import load_dotenv

class MeshManager:

    def __init__(self) -> None:
        load_dotenv()
        self.config = {}
        self._load_config_file()

        self.output_config = {}
        self.api_endpoint = self.config.get("mesh_api_endpoint")
        self.api_key = os.environ.get("API_KEY")
        self.overlay_api_headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
                    }


    def _create_overlays(self):
        """
        Iterate through all the overlays names in the config file and
        calls the API to create each on of them.
        Saves all the responses to later produce the config file. 
        """
        for overlay in self.config.get("overlays"):
            body = json.dumps({"overlay_name": overlay['name']})
            response = requests.post(f"{self.api_endpoint}/overlays",
                                    data=body,
                                    headers=self.overlay_api_headers)

            if response.status_code == 200:
                self.output_config["overlays"] = []
                self.output_config.get("overlays").append(response.json()) 
            else:
                raise StartupError(f'Failed while creating overlay {overlay["name"]}')
                

    def _create_devices(self):
        """
        Iterate through the devices in the config files and sign them up
        on the API.
        For every device,
        """
        for device in self.config.get('devices'):
            body = json.dumps(device)
            response = requests.post(f"{self.api_endpoint}/devices",
                                    data=body,
                                    headers=self.overlay_api_headers)
            if response.status_code == 200:
                self.output_config["devices"] = []
                self.output_config.get("devices").append(response.json())
            else:    
                raise StartupError(f'Failed while creating overlay {device["device_name"]}')



    def _load_config_file(self):
        with open("config.json", "r") as file:
            self.config = json.load(file)

    def start(self):
        self.__init__()
        #self._create_overlays()
        self._create_devices()
    

if __name__ == "__main__":
    manager = MeshManager()
    manager.start()
