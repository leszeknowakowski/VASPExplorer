import json
import os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")


class AppConfig:
    dir = None
    potcar_dir = None
    last_open_file = None
    theme = "light"

    @classmethod
    def load(cls):
        if not os.path.exists(CONFIG_FILE):
            return

        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        for key, value in data.items():
            setattr(cls, key, value)

    @classmethod
    def save(cls):
        data = {}

        for key, value in cls.__dict__.items():
            # skip private + methods/descriptors
            if key.startswith("_"):
                continue

            if isinstance(value, (classmethod, staticmethod)):
                continue

            if callable(value):
                continue

            data[key] = value

        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)