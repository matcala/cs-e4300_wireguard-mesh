import json

from timeloop import Timeloop
from timeloop.job import Job
import requests

from datetime import timedelta
import re

time_loop = Timeloop()


class WireguardManager:

    def __init__(self):
        self.config = {}
        self._load_config_file()
        self.management_server_addr = self.config.get("manager_server_address")

        time_loop.jobs.append(Job(timedelta(minutes=self.config["token_refresh_interval"]), self._renew_tokens))
        time_loop.jobs.append(
            Job(timedelta(minutes=self.config["config_update_interval"]), self._update_wireguard_config))

    def _load_config_file(self):
        with open("config.json", "r") as file:
            self.config = json.load(file)

        with open("sample_config", "r") as file:
            sample = file.read()

        for interface in self.config.get("interfaces"):
            with open(interface["private_key_filepath"], "r") as file:
                interface["private_key"] = file.read().strip()

            interface["config"] = sample.format(private_key=interface["private_key"],
                                                virtual_address=interface["virtual_address"],
                                                listen_port=interface["listen_port"])

    def _renew_tokens(self):
        for interface in self.config.get("interfaces"):
            response = requests.get(f"{self.management_server_addr}/devices/{interface['device_id']}/token", headers={
                "Authorization": f"Bearer {interface['token']}",
                "Content-Type": "application/json"
            })

            if response.status_code == 200:
                interface["token"] = response.json()["token"]
                interface["token_expiry_ts"] = response.json()["expiry_ts"]
            else:
                print(f"Error updating token of {interface['name']}")

        with open("config.json", "w") as file:
            file.write(json.dumps(self.config))

    def _update_wireguard_config(self):
        for interface in self.config.get("interfaces"):
            response = requests.get(
                f"{self.management_server_addr}/overlays/{interface['overlay_id']}/devices/{interface['device_id']}/wgconfig",
                headers={
                    "Authorization": f"Bearer {interface['token']}",
                    "Content-Type": "application/json"
                })

            if response.status_code == 200:
                peer_config = response.content.decode().replace(": ", ":")
                peer_config = re.sub(r"Peer \d+", "Peer", peer_config)
                peer_count = peer_config.count("[Peer]")  # TODO check if restart of the interface is required

                with open(f"/etc/wireguard/{interface['name']}.conf", "w") as file:
                    file.write(interface["config"] + peer_config)
            else:
                print(f"Error updating config file of {interface['name']}")

    def start(self):
        self._renew_tokens()
        self._update_wireguard_config()
        time_loop.start(block=True)


if __name__ == "__main__":
    manager = WireguardManager()
    manager.start()
