"""Config loading for the Order Service."""
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULTS: Dict[str, Any] = {
    "db_path": "orders.db",
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
        loaded = yaml.safe_load(f)

    if isinstance(loaded, dict):
        config.update(loaded)
    return config
