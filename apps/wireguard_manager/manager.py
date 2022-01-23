import json
from threading import Thread, Event
from time import sleep

from timeloop import Timeloop
from timeloop.job import Job
import requests

from datetime import timedelta
import re
import hashlib
import os
import sys

from exceptions import StartupError


class InterfaceManager(Thread):
    CONFIG_FILE_PARAMETERS = ["interface", "manager_server_address", "token_refresh_interval", "config_update_interval"]
    INTERFACE_CONFIG_PARAMETERS = ["name", "overlay_id", "device_id", "virtual_address", "listen_port", "token"]

    def __init__(self, config_file_path):
        super().__init__()
        self.time_loop = Timeloop()
        self.daemon = True
        self.stop_event = Event()
        self.config = {}
        self.interface = None
        self.fail_reason = ""
        self.config_file_path = config_file_path

    def _is_config_valid(self, config: dict):
        config_keys = config.keys()
        for key in self.CONFIG_FILE_PARAMETERS:
            if key not in config_keys:
                self.fail_reason = f"{key} missing from the config file"
                return False

        interface_keys = config["interface"].keys()
        for key in self.INTERFACE_CONFIG_PARAMETERS:
            if key not in interface_keys:
                self.fail_reason = f"{key} missing from the interface config"
                return False

        return True

    def _setup_key_pair(self):
        private_key_path = f"/etc/wireguard/privatekey_{self.interface['name']}"
        public_key_path = f"/etc/wireguard/publickey_{self.interface['name']}"

        os.system("umask 077 /etc/wireguard")
        os.system(f"wg genkey | tee {private_key_path} | wg pubkey > {public_key_path}")

        with open(private_key_path, "r") as file:
            self.interface["private_key"] = file.read().strip()

        with open(public_key_path, "r") as file:
            updated_data = {
                "public_key": file.read().strip()
            }

        response = requests.put(f"{self.management_server_addr}/devices/{self.interface['device_id']}",
                                data=json.dumps(updated_data),
                                headers={
                                    "Authorization": f"Bearer {self.interface['token']}",
                                    "Content-Type": "application/json"
                                })

        if response:
            self.interface["private_key_path"] = private_key_path
            self.interface["public_key_path"] = public_key_path
        else:
            raise StartupError(f"Could not update {self.interface['name']}'s public key")

    def _load_config_file(self):
        try:
            with open(self.config_file_path, "r") as file:
                self.config = json.load(file)
        except FileNotFoundError:
            raise StartupError(f"No config file found in this path: {self.config_file_path}")

        if self._is_config_valid(self.config):
            self.interface = self.config["interface"]
            self.management_server_addr = self.config["manager_server_address"]
            self.time_loop.jobs.append(Job(timedelta(minutes=self.config["token_refresh_interval"]), self._renew_token))
            self.time_loop.jobs.append(
                Job(timedelta(minutes=self.config["config_update_interval"]), self._update_wireguard_config))

            with open("sample_config", "r") as file:
                sample = file.read()

            self._setup_key_pair()
            self.interface["config"] = sample.format(private_key=self.interface["private_key"],
                                                     virtual_address=self.interface["virtual_address"],
                                                     listen_port=self.interface["listen_port"])
        else:
            raise StartupError(message=self.fail_reason)

    def _renew_token(self):
        response = requests.get(f"{self.management_server_addr}/devices/{self.interface['device_id']}/token", headers={
            "Authorization": f"Bearer {self.interface['token']}",
            "Content-Type": "application/json"
        })

        if response:
            self.interface["token"] = response.json()["token"]
            self.interface["token_expiry_ts"] = response.json()["expiry_ts"]
        else:
            print(f"Error updating token of {self.interface['name']}")

    def _update_wireguard_config(self):
        response = requests.get(
            f"{self.management_server_addr}/overlays/{self.interface['overlay_id']}/devices/{self.interface['device_id']}/wgconfig",
            headers={
                "Authorization": f"Bearer {self.interface['token']}",
                "Content-Type": "application/json"
            })

        if response.status_code == 200:
            peer_config = response.content.decode().replace(": ", ":")
            peer_config = re.sub(r"Peer \d+", "Peer", peer_config)

            peer_config_hash = hashlib.sha256(peer_config.encode()).hexdigest()
            previous_hash = self.interface.get("config_hash")

            if previous_hash is None:
                with open(f"/etc/wireguard/{self.interface['name']}.conf", "w") as file:
                    file.write(self.interface["config"] + peer_config)

                os.system(f"systemctl enable wg-quick@{self.interface['name']}")
                os.system(f"systemctl start wg-quick@{self.interface['name']}")
                self.interface["config_hash"] = peer_config_hash

            elif previous_hash != peer_config_hash:
                with open(f"/etc/wireguard/{self.interface['name']}.conf", "w") as file:
                    file.write(self.interface["config"] + peer_config)

                os.system(f"systemctl restart wg-quick@{self.interface['name']}")
                self.interface["config_hash"] = peer_config_hash
        else:
            print(f"Error updating config file of {self.interface['name']}")

    def run(self):
        self._load_config_file()
        self._renew_token()
        self._update_wireguard_config()
        self.time_loop.start()
        self.stop_event.wait()
        print("Exiting...")


class WireguardManager:
    MANAGER_DIR = "wireguard_manager"
    DEFAULT_CONFIG_DIR = f"/etc/{MANAGER_DIR}/"

    def __init__(self, config_files_dir=DEFAULT_CONFIG_DIR):
        self.threads = {}
        if config_files_dir[-1] == "/":
            self.config_files_dir = config_files_dir
        else:
            self.config_files_dir = config_files_dir + "/"

    def _check_for_new_config(self):
        pass

    def run(self):
        while True:
            self._check_for_new_config()
            sleep(5 * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        manager = InterfaceManager(config_files_dir=sys.argv[1])
    else:
        manager = InterfaceManager("/etc/wireguard_manager/config.json")
    manager.run()
