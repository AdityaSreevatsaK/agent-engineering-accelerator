"""Run settings from a TOML file passed with --config: adapter, agent, input_map, output_map."""

import tomllib
from pathlib import Path

ADAPTERS = ("strands", "langgraph")
CONFIG_KEYS = ("adapter", "agent", "input_map", "output_map")
_REF_KEYS = ("agent", "input_map", "output_map")


class ConfigError(ValueError):
    """An unreadable or invalid config file; the message starts with the file path."""


def load_config(path: Path) -> dict[str, str]:
    """Reads and validates a flat config file; returns only the keys it sets."""
    shown = Path(path).as_posix()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"{shown}: file not found") from None
    except OSError as exc:
        raise ConfigError(f"{shown}: {exc.strerror or exc}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{shown}: {exc}") from None
    for key, value in data.items():
        if key not in CONFIG_KEYS:
            raise ConfigError(f"{shown}: unknown key {key!r}; allowed: {', '.join(CONFIG_KEYS)}")
        if not isinstance(value, str):
            raise ConfigError(f"{shown}: {key} must be a string, got {type(value).__name__}")
    if "adapter" in data and data["adapter"] not in ADAPTERS:
        raise ConfigError(f"{shown}: adapter must be one of {', '.join(ADAPTERS)}, got {data['adapter']!r}")
    for key in _REF_KEYS:
        if key in data and ":" not in data[key]:
            raise ConfigError(f"{shown}: {key} must be module:function, got {data[key]!r}")
    return dict(data)
