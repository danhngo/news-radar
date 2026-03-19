"""YAML config loader with env overrides."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

_config: dict | None = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_config(path: Path | None = None) -> dict:
    global _config
    if _config is not None and path is None:
        return _config

    load_dotenv(PROJECT_ROOT / ".env")

    config_path = path or PROJECT_ROOT / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Env overrides
    cfg["db_path"] = os.getenv("RADAR_DB_PATH", "data/radar.db")
    cfg["briefings_dir"] = os.getenv("RADAR_BRIEFINGS_DIR", "briefings")

    if path is None:
        _config = cfg
    return cfg


def get_config() -> dict:
    return load_config()
