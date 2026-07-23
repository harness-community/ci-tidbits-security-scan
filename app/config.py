"""Config loading for the Order Service.

Reads settings from a YAML file on disk. Falls back to sensible defaults
if the file is missing.
"""
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULTS: Dict[str, Any] = {
    "db_path": "orders.db",
    "backup_dir": "/var/backups/orders",
    "default_country": "US",
    "session_timeout_minutes": 30,
}


def load_config(path: str | Path = "config.yaml") -> Dict[str, Any]:
    """Load app config from a YAML file, layered over the defaults."""
    config = dict(DEFAULTS)
    p = Path(path)
    if not p.exists():
        return config

    with p.open() as f:
        # Semgrep flags: yaml.load without a SafeLoader can execute
        # arbitrary Python objects encoded in the YAML. Use yaml.safe_load.
        # Rule: python.lang.security.audit.dangerous-yaml-load
        loaded = yaml.load(f)

    if isinstance(loaded, dict):
        config.update(loaded)
    return config
