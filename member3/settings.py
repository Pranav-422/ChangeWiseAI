"""Settings and environment. Secrets come from the environment or .env, never from code."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "member3" / ".env")


@lru_cache
def load_settings():
    with open(ROOT / "member3" / "config" / "settings.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def database_path():
    return Path(os.environ.get("CHANGEWISE_DB") or ROOT / load_settings()["application"]["database"])
