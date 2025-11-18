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
        if os.name == "nt":
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        else:
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
        if os.name == "nt":  # Windows
            ctypes.windll.user32.SetProcessDPIAware()
            user32 = ctypes.windll.user32
            dc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, dc)
            return round(dpi / 96.0, 2)
        else:
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
    base_url: str = "https://wmqa.subaru1.com/manh/index.html?i=102"
    change_warehouse: str = "ONT"
    timeout_default: int = 5000
    check_interval: int = 200
    post_message_text: str = """place holder"""
    rf_verbose_logging: bool = True
    app_verbose_logging: bool = True
    requires_prod_confirmation: bool = False
    auto_accept_rf_messages: bool = True
    auto_click_info_icon: bool = False
    verify_tran_id_marker: bool = False
    app_server_user: str = ""
    app_server_pass: str = ""


class Settings:
    browser = BrowserConfig()
    app = AppConfig()

    app_log(
        f"Detected screen: {browser.width}x{browser.height}, scale={browser.device_scale_factor}"
    )

    @classmethod
    def from_env(cls):
        """Load settings from environment variables"""
        cls.app.base_url = os.getenv("APP_URL", cls.app.base_url)
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
        set_general_verbose(cls.app.app_verbose_logging)
        set_rf_verbose(cls.app.rf_verbose_logging)
        base_url_lower = cls.app.base_url.lower()
        cls.app.requires_prod_confirmation = any(
            marker in base_url_lower for marker in ("prod", "prd")
        )
        try:
            credentials = DB.get_credentials("qa")
        except Exception as exc:
            app_log(f"⚠️ Failed to load App logon credentials from config in dev: {exc}")
            credentials = {}
        cls.app.app_server_user = os.getenv(
            "APP_SERVER_USER",
            credentials.get("app_server_user", cls.app.app_server_user),
        )
        cls.app.app_server_pass = os.getenv(
            "APP_SERVER_PASS",
            credentials.get("app_server_pass", cls.app.app_server_pass),
        )
        return cls
