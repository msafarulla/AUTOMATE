import os
from typing import Dict

_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


_channel_verbose: Dict[str, bool] = {
    "general": _env_bool("APP_VERBOSE_LOGGING"),
    "rf": _env_bool("RF_VERBOSE_LOGGING"),
}


def set_general_verbose(enabled: bool):
    _channel_verbose["general"] = bool(enabled)


def set_rf_verbose(enabled: bool):
    _channel_verbose["rf"] = bool(enabled)


def is_verbose(channel: str = "general") -> bool:
    return _channel_verbose.get(channel, False)


def _log(message: str, channel: str):
    if _channel_verbose.get(channel):
        print(message)


def app_log(message: str):
    _log(message, "general")


def rf_log(message: str):
    _log(message, "rf")
