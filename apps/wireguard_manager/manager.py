import json
from threading import Thread, Event
from time import sleep, time

from timeloop import Timeloop
from timeloop.job import Job
import requests

from datetime import timedelta
import re
import hashlib
from os import listdir, system
from os.path import isfile, join
import sys
import netifaces
import logging

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
        self.logger = None

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

        if not isfile(public_key_path):
            system("umask 077 /etc/wireguard")
            system(f"wg genkey | tee {private_key_path} | wg pubkey > {public_key_path}")

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
            self.logger.info(f"Public key setup, Success! {response.status_code} {json.dumps(updated_data)}")
        else:
            self.logger.info(f"Update public key failed:{response.status_code} {response.json()}")

    def _load_config_file(self):
        try:
            with open(self.config_file_path, "r") as file:
                self.config = json.load(file)
        except FileNotFoundError:
            raise StartupError(f"No config file found in this path: {self.config_file_path}")

        if self._is_config_valid(self.config):
            self.interface = self.config["interface"]
            self.logger = logging.getLogger(self.interface["name"])
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

            self.logger.info("Config loaded, Success!")
        else:
            self.logger.info(f"Config load failed: {self.fail_reason}")
            raise StartupError(message=self.fail_reason)

    def _renew_token(self):
        response = requests.get(f"{self.management_server_addr}/devices/{self.interface['device_id']}/token", headers={
            "Authorization": f"Bearer {self.interface['token']}",
            "Content-Type": "application/json"
        })

        if response:
            previous_token = self.interface["token"]
            self.interface["token"] = response.json()["token"]
            self.interface["token_expiry_ts"] = response.json()["expiry_ts"]
            self.logger.info(f"Token Renew, Success! {previous_token} => {self.interface['token']}")
        else:
            error_message = f"{response.status_code} {response.json()} {self.interface['token_expiry_ts']} {time()}"
            self.logger.info(f"Token Renew failed: {error_message} Failed Token: {self.interface['token']}")

    @staticmethod
    def _interface_exists(interface_name):
        return interface_name in netifaces.interfaces()

    def _update_wireguard_config(self):
        response = requests.get(
            f"{self.management_server_addr}/overlays/{self.interface['overlay_id']}/devices/{self.interface['device_id']}/wgconfig",
            headers={
                "Authorization": f"Bearer {self.interface['token']}",
                "Content-Type": "application/json"
            })

        if response:
            peer_config = response.content.decode().replace(": ", ":")
            peer_config = re.sub(r"Peer \d+", "Peer", peer_config)

            peer_config_hash = hashlib.sha256(peer_config.encode()).hexdigest()
            previous_hash = self.interface.get("config_hash")

            wg_config_path = f"/etc/wireguard/{self.interface['name']}.conf"

            if previous_hash is None and isfile(wg_config_path):
                with open(wg_config_path, "r") as file:
                    previous_hash = hashlib.sha256(file.read().encode()).hexdigest()

            if previous_hash != peer_config_hash:
                self.logger.info("Updating new config")
                with open(wg_config_path, "w") as file:
                    file.write(self.interface["config"] + peer_config)
                self.interface["config_hash"] = peer_config_hash

                if self._interface_exists(self.interface["name"]):
                    system(f"systemctl restart wg-quick@{self.interface['name']}")
                    self.logger.info("Interface restarted due to new config!")
                else:
                    system(f"systemctl enable wg-quick@{self.interface['name']}")
                    system(f"systemctl start wg-quick@{self.interface['name']}")
                    self.logger.info("Interface created!")

            self.logger.info("Update config, Success!")
        else:
            self.logger.info(f"Update config fail: {response.status_code} {response.json()}")

    def run(self):
        self._load_config_file()
        self.logger.info("Starting...")
        self._renew_token()
        self._update_wireguard_config()
        self.time_loop.start()
        self.stop_event.wait()
        system(f"systemctl stop wg-quick@{self.interface['name']}")
        self.logger.info("Exting...")

    def stop(self):
        self.stop_event.set()


class WireguardManager:
    MANAGER_DIR = "wireguard_manager"
    DEFAULT_CONFIG_DIR = f"/etc/{MANAGER_DIR}/"
    LOG_FILE_PATH = "/var/log/"

    def __init__(self, config_files_dir=DEFAULT_CONFIG_DIR):
        self.threads = {}
        if config_files_dir[-1] == "/":
            self.config_files_dir = config_files_dir
        else:
            self.config_files_dir = config_files_dir + "/"

    def _check_for_new_config(self):
        current_config_files = [join(self.config_files_dir, file_name) for file_name in listdir(self.config_files_dir)
                                if isfile(join(self.config_files_dir, file_name))]

        for file in current_config_files:
            if file not in self.threads:
                self.threads[file] = InterfaceManager(file)
                self.threads[file].start()
                logging.info(f"Thread for {file} started")

        for key in self.threads.keys():
            if key not in current_config_files:
                self.threads[key].stop()
                logging.info(f"Thread for {key} stopped")

        logging.info("Config Dir Traversed")

    def run(self):
        logging.info("Manager Started")
        while True:
            self._check_for_new_config()
            sleep(5 * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, handlers=[
        logging.FileHandler(join(WireguardManager.LOG_FILE_PATH, "wg_manager.log")),
        logging.StreamHandler()
    ])
    if len(sys.argv) > 1:
        manager = WireguardManager(config_files_dir=sys.argv[1])
    else:
        manager = WireguardManager()
    manager.run()
