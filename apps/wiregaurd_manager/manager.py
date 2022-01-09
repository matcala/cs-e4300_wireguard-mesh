from dotenv import load_dotenv
import requests
import os


class OverlayManager:
    DEFAULT_LISTEN_PORT = 51830

    def __init__(self, overlay_id, api_key, management_server_addr, **kwargs):
        self.overlay_id = overlay_id
        self.api_key = api_key
        self.management_server_addr = management_server_addr

        self.device_id = None
        self.virtual_address = None
        self.public_address = None
        self.listen_port = kwargs.get("listen_port") if kwargs.get("listen_port") else self.DEFAULT_LISTEN_PORT
        self.token = None

    def _subscribe_device(self):
        pass

    def _request_token(self):
        response = requests.get(f"{self.management_server_addr}/devices/{self.device_id}/token")
        self.token = {
            "token": response.json()["token"],
            "expiry_ts": response.json()["expiry_ts"]
        }

    def _add_device_to_overlay(self):
        pass

    def _save_wiregaurd_config(self):
        pass

    def start(self):
        self._subscribe_device()
        self._request_token()
        self._add_device_to_overlay()
        self._save_wiregaurd_config()


if __name__ == "__main__":
    load_dotenv()
    if os.environ.get("OVERLAY_ID") and os.environ.get("API_KEY") and os.environ.get("SERVER_ADDR"):
        manager = OverlayManager(
            overlay_id=os.environ["OVERLAY_ID"],
            api_key=os.environ["API_KEY"],
            management_server_addr=os.environ["SERVER_ADDR"]
        )
        manager.start()
    else:
        raise Exception("OVERLAY_ID, API_KEY, and SERVER_ADDR environment variables should be declared")
