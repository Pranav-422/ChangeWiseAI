"""Member 1 engine: validation, BOM impact, weekly Rev B / Rev C simulation, shortage, excess, severity."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
ENGINE_VERSION = CONFIG["engine_version"]
