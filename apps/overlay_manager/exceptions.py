class StartupError(Exception):
    def __init__(self, message):
        self.message = message


class DeviceRegistrationError(Exception):
    def __init__(self, message):
        self.message = message


class CannotAddToOverlay(Exception):
    def __init__(self, message):
        self.message = message