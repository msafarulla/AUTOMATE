import os
from dataclasses import dataclass, field
import ctypes

from DB import DB
from core.logger import app_log, set_general_verbose, set_rf_verbose

# Sensible fallbacks when detection is unavailable (e.g. headless CI)
DEFAULT_SCREEN_WIDTH = 1920
DEFAULT_SCREEN_HEIGHT = 1080


def get_screen_size_safe():
    """Best-effort screen detection that works across desktop platforms."""
    width = height = None

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
    except Exception as e:
        app_log(f"⚠️ Screen size detection failed: {e}")

    width = width or DEFAULT_SCREEN_WIDTH
    height = height or DEFAULT_SCREEN_HEIGHT
    return width, height


def get_scale_factor():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        scaling = root.tk.call("tk", "scaling")
        root.destroy()
        return round(float(scaling), 2)
    except Exception as exc:
        app_log(f"⚠️ DPI detection failed: {exc}")
        return 1.0


_SCREEN_WIDTH, _SCREEN_HEIGHT = get_screen_size_safe()


def _env_flag(name: str, default: bool) -> bool:
    """Best-effort parsing of boolean env flags."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass
class StepNames:
    """Configurable stage identifiers used across workflows."""
    postMessage: str = "postMessage"
    runReceiving: str = "runReceiving"
    runLoading: str = "runLoading"
    OpenTasksUi: str = "OpenTasksUi"
    OpenIlpnUi: str = "OpenIlpnUi"


@dataclass
class BrowserConfig:
    width: int = field(default_factory=lambda: _SCREEN_WIDTH)
    height: int = field(default_factory=lambda: _SCREEN_HEIGHT)
    headless: bool = not True
    device_scale_factor: float = field(default_factory=get_scale_factor)
    screenshot_dir: str = "screenshots"
    screenshot_format: str = "jpeg"
    screenshot_quality: int = 70


@dataclass
class AppConfig:
    credentials_env: str = "dev"
    change_warehouse: str = "SDC"
    timeout_default: int = 6000
    check_interval: int = 200
    post_message_text: str = """place holder"""
    rf_verbose_logging: bool = True
    app_verbose_logging: bool = True
    requires_prod_confirmation: bool = False
    auto_accept_rf_messages: bool = True
    auto_click_info_icon: bool = False
    verify_tran_id_marker: bool = False
    auto_close_post_login_windows: bool = False
    app_server: str = ""
    app_server_user: str = ""
    app_server_pass: str = ""
    step_names: StepNames = field(default_factory=StepNames)


class Settings:
    browser = BrowserConfig()
    app = AppConfig()

    app_log(
        f"Detected screen: {browser.width}x{browser.height}, scale={browser.device_scale_factor}"
    )

    @classmethod
    def from_env(cls):
        """Load settings from environment variables"""
        cls.app.change_warehouse = os.getenv(
            "DEFAULT_WAREHOUSE", cls.app.change_warehouse
        )
        cls.app.post_message_text = os.getenv(
            "POST_MESSAGE_TEXT", cls.app.post_message_text
        )
        cls.app.app_verbose_logging = _env_flag(
            "APP_VERBOSE_LOGGING", cls.app.app_verbose_logging
        )
        cls.app.rf_verbose_logging = _env_flag(
            "RF_VERBOSE_LOGGING", cls.app.rf_verbose_logging
        )
        cls.app.auto_accept_rf_messages = _env_flag(
            "RF_AUTO_ACCEPT_MESSAGES", cls.app.auto_accept_rf_messages
        )
        cls.app.auto_click_info_icon = _env_flag(
            "RF_AUTO_CLICK_INFO_ICON", cls.app.auto_click_info_icon
        )
        cls.app.verify_tran_id_marker = _env_flag(
            "RF_VERIFY_TRAN_ID_MARKER", cls.app.verify_tran_id_marker
        )
        cls.app.auto_close_post_login_windows = _env_flag(
            "AUTO_CLOSE_POST_LOGIN_WINDOWS", cls.app.auto_close_post_login_windows
        )
        cls.app.credentials_env = os.getenv(
            "APP_CREDENTIALS_ENV", cls.app.credentials_env
        )
        set_general_verbose(cls.app.app_verbose_logging)
        set_rf_verbose(cls.app.rf_verbose_logging)
        try:
            credentials = DB.get_credentials(cls.app.credentials_env)
        except Exception as exc:
            app_log(
                f"⚠️ Failed to load App logon credentials "
                f"(env={cls.app.credentials_env}): {exc}"
            )
            credentials = {}
        cls.app.app_server = os.getenv(
            "APP_SERVER",
            credentials.get("app_server", cls.app.app_server),
        )
        cls.app.app_server_user = os.getenv(
            "APP_SERVER_USER",
            credentials.get("app_server_user", cls.app.app_server_user),
        )
        cls.app.app_server_pass = os.getenv(
            "APP_SERVER_PASS",
            credentials.get("app_server_pass", cls.app.app_server_pass),
        )
        app_server_lower = cls.app.app_server.lower()
        cls.app.requires_prod_confirmation = any(
            marker in app_server_lower for marker in ("prod", "prd")
        )
        return cls
