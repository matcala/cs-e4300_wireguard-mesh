import json

from timeloop import Timeloop
from timeloop.job import Job
import requests

from datetime import timedelta

time_loop = Timeloop()


class WireguardManager:

    def __init__(self):
        self.config = {}
        self._load_config_file()
        self.management_server_addr = self.config.get("manager_server_address")

        time_loop.jobs.append(Job(timedelta(minutes=1), self._renew_tokens))
        time_loop.jobs.append(Job(timedelta(minutes=2), self._update_wireguard_config))

    def _load_config_file(self):
        with open("config.json", "r") as file:
            self.config = json.load(file)

        with open("sample_config", "r") as file:
            sample = file.read()

        for interface in self.config.get("interfaces"):
            with open(interface["private_key_filepath"], "r") as file:
                interface["private_key"] = file.read()

            interface["config"] = sample.format(private_key=interface["private_key"],
                                                virtual_address=interface["virtual_address"],
                                                listen_port=interface["listen_port"])

    def _renew_tokens(self):
        for interface in self.config.get("interfaces"):
            response = requests.get(f"{self.management_server_addr}/devices/{interface['device_id']}/token", headers={
                "Authorization": f"Bearer {interface['token']}",
                "Content-Type": "application/json"
            })

            interface["token"] = response.json()["token"]
            interface["token_expiry_ts"] = response.json()["expiry_ts"]

    def _update_wireguard_config(self):
        pass

    def start(self):
        self._renew_tokens()
        self._update_wireguard_config()
        time_loop.start(block=True)


if __name__ == "__main__":
    manager = WireguardManager()
    manager.start()
