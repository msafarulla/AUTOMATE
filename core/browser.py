from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, ViewportSize
from config.settings import Settings
from typing import Optional, cast


class BrowserManager:
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self._create_browser()
        self.context = self._create_context()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _create_browser(self) -> Browser:
        cfg = self.settings.browser
        scale = max(cfg.device_scale_factor, 1.0)
        window_width = int(cfg.width / scale)
        window_height = int(cfg.height / scale)

        launch_args = [
            f"--window-size={window_width},{window_height}",
            "--window-position=0,0",
            "--allow-running-insecure-content",
            "--ignore-certificate-errors",
            "--unsafely-treat-insecure-origin-as-secure=http://soa430.subaru1.com:12000",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-blink-features=AutomationControlled",
        ]

        return self.playwright.chromium.launch(
            headless=cfg.headless,
            args=launch_args
        )

    def _create_context(self) -> BrowserContext:
        cfg = self.settings.browser
        # Keep viewport math aligned with working standalone script: provide CSS pixels,
        # let Playwright handle device_scale_factor instead of mixing both layers.
        scale = max(cfg.device_scale_factor, 1.0)
        viewport_width = int(cfg.width / scale)
        viewport_height = int((cfg.height - 300) / scale)
        print(
            f"[BrowserManager] viewport={viewport_width}x{viewport_height} "
            f"(raw={cfg.width}x{cfg.height}, scale={cfg.device_scale_factor})"
        )
        return self.browser.new_context(
            viewport=cast(ViewportSize, {"width": viewport_width, "height": viewport_height}),
            device_scale_factor=cfg.device_scale_factor,
            ignore_https_errors=True
        )

    def new_page(self) -> Page:
        return self.context.new_page()
