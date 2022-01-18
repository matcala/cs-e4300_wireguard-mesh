import json

from timeloop import Timeloop
from timeloop.job import Job
import requests

from datetime import timedelta
import re
import hashlib
import os
import sys

from exceptions import StartupError

time_loop = Timeloop()


class WireguardManager:
    MANAGER_DIR = "wireguard_manager"
    CONFIG_FILE_PARAMETERS = ["interfaces", "manager_server_address"]
    INTERFACE_CONFIG_PARAMETERS = ["name", "overlay_id", "device_id", "virtual_address", "listen_port", "token"]
    DEFAULT_CONFIG_PATH = f"/etc/{MANAGER_DIR}/config.json"

    def __init__(self, config_file_path=DEFAULT_CONFIG_PATH):
        self.config = {}
        self.fail_reason = ""
        os.system(f"mkdir /etc/{self.MANAGER_DIR}")
        self.config_file_path = config_file_path

    def _is_config_valid(self, config: dict):
        config_keys = config.keys()
        for key in self.CONFIG_FILE_PARAMETERS:
            if key not in config_keys:
                self.fail_reason = f"{key} missing from the config file"
                return False

        for interface in config["interfaces"]:
            interface_keys = interface.keys()
            for key in self.INTERFACE_CONFIG_PARAMETERS:
                if key not in interface_keys:
                    self.fail_reason = f"{key} missing from the interface config"
                    return False

        return True

    def _setup_key_pair(self, interface):
        private_key_path = f"/etc/wireguard/privatekey_{interface.get('name')}"
        public_key_path = f"/etc/wireguard/publickey_{interface.get('name')}"

        os.system("umask 077 /etc/wireguard")
        os.system(f"wg genkey | tee {private_key_path} | wg pubkey > {public_key_path}")

        with open(private_key_path, "r") as file:
            interface["private_key"] = file.read().strip()

        with open(public_key_path, "r") as file:
            updated_data = {
                "public_key": file.read().strip()
            }

        response = requests.put(f"{self.management_server_addr}/devices/{interface['device_id']}",
                                data=json.dumps(updated_data),
                                headers={
                                    "Authorization": f"Bearer {interface['token']}",
                                    "Content-Type": "application/json"
                                })

        if response:
            interface["private_key_path"] = private_key_path
            interface["public_key_path"] = public_key_path
        else:
            raise StartupError(f"Could not update {interface['name']}'s public key")

    def _load_config_file(self):
        try:
            with open(self.config_file_path, "r") as file:
                self.config = json.load(file)
        except FileNotFoundError:
            raise StartupError(f"No config file found in this path: {self.config_file_path}")

        if self._is_config_valid(self.config):
            self.management_server_addr = self.config["manager_server_address"]
            time_loop.jobs.append(Job(timedelta(minutes=self.config["token_refresh_interval"]), self._renew_tokens))
            time_loop.jobs.append(
                Job(timedelta(minutes=self.config["config_update_interval"]), self._update_wireguard_config))

            with open("sample_config", "r") as file:
                sample = file.read()

            for interface in self.config.get("interfaces"):
                self._setup_key_pair(interface)
                interface["config"] = sample.format(private_key=interface["private_key"],
                                                    virtual_address=interface["virtual_address"],
                                                    listen_port=interface["listen_port"])
        else:
            raise StartupError(message=self.fail_reason)

    def _renew_tokens(self):
        for interface in self.config.get("interfaces"):
            response = requests.get(f"{self.management_server_addr}/devices/{interface['device_id']}/token", headers={
                "Authorization": f"Bearer {interface['token']}",
                "Content-Type": "application/json"
            })

            if response:
                interface["token"] = response.json()["token"]
                interface["token_expiry_ts"] = response.json()["expiry_ts"]
            else:
                print(f"Error updating token of {interface['name']}")

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

                peer_config_hash = hashlib.sha256(peer_config.encode()).hexdigest()
                previous_hash = interface.get("config_hash")

                if previous_hash is None:
                    with open(f"/etc/wireguard/{interface['name']}.conf", "w") as file:
                        file.write(interface["config"] + peer_config)

                    os.system(f"systemctl enable wg-quick@{interface['name']}")
                    os.system(f"systemctl start wg-quick@{interface['name']}")
                    interface["config_hash"] = peer_config_hash

                elif previous_hash != peer_config_hash:
                    with open(f"/etc/wireguard/{interface['name']}.conf", "w") as file:
                        file.write(interface["config"] + peer_config)

                    os.system(f"systemctl restart wg-quick@{interface['name']}")
                    interface["config_hash"] = peer_config_hash
            else:
                print(f"Error updating config file of {interface['name']}")

    def start(self):
        self._load_config_file()
        self._renew_tokens()
        self._update_wireguard_config()
        time_loop.start(block=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        manager = WireguardManager(config_file_path=sys.argv[1])
    else:
        manager = WireguardManager()
    manager.start()