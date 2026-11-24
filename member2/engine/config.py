"""Configuration and simulator loading."""
from importlib import import_module
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "optimization.yaml"


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_simulator(config):
    module_name, function_name = config["simulator"].split(":")
    return getattr(import_module(module_name), function_name)
