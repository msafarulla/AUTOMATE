from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Generator

from core.browser import BrowserManager
from core.connection_guard import ConnectionResetGuard
from core.logger import app_log
from core.orchestrator import AutomationOrchestrator
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from operations.inbound.receive import ReceiveOperation
from operations.outbound.loading import LoadingOperation
from ui.auth import AuthManager
from ui.navigation import NavigationManager
from ui.post_message import PostMessageManager
from ui.rf_menu import RFMenuManager


@dataclass
class OperationServices:
    screenshot_mgr: ScreenshotManager
    nav_mgr: NavigationManager
    orchestrator: AutomationOrchestrator
    run_login: Callable[[], None]
    run_change_warehouse: Callable[[], None]
    run_post_message: Callable[[str | None], bool]
    receive: Callable[..., bool]
    loading: Callable[..., bool]


class OperationRunner:
    def __init__(
        self,
        settings: Any,
        page: Any,
        page_mgr: PageManager,
        screenshot_mgr: ScreenshotManager,
        auth_mgr: AuthManager,
        nav_mgr: NavigationManager,
        post_message_mgr: PostMessageManager,
        rf_menu: RFMenuManager,
        conn_guard: ConnectionResetGuard,
    ):
        self.settings = settings
        self.page = page
        self.page_mgr = page_mgr
        self.screenshot_mgr = screenshot_mgr
        self.auth_mgr = auth_mgr
        self.nav_mgr = nav_mgr
        self.post_message_mgr = post_message_mgr
        self.rf_menu = rf_menu
        self.conn_guard = conn_guard
        self.receive = self._guarded(self._receive_impl)
        self.loading = self._guarded(self._loading_impl)
        self.run_login = self._guarded(self._run_login)
        self.run_change_warehouse = self._guarded(self._run_change_warehouse)
        self.run_post_message = self._guarded(self._run_post_message)
        self.run_tasks_ui = self._guarded(self._run_tasks_ui)

    def _guarded(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.conn_guard.guard(func, *args, **kwargs)

        return wrapper

    def _run_login(self) -> None:
        self.auth_mgr.login()

    def _run_change_warehouse(self) -> None:
        self.nav_mgr.change_warehouse(self.settings.app.change_warehouse)

    def _receive_impl(
        self,
        asn: str,
        item: str,
        quantity: int = 1,
        flow_hint: str | None = None,
        auto_handle: bool = False,
    ) -> bool:
        self.nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
        receive_op = ReceiveOperation(self.page, self.page_mgr, self.screenshot_mgr, self.rf_menu)
        return receive_op.execute(
            asn,
            item,
            quantity,
            flow_hint=flow_hint,
            auto_handle=auto_handle,
        )

    def _loading_impl(self, shipment: str, dock_door: str, bol: str) -> bool:
        self.nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
        load_op = LoadingOperation(self.page, self.page_mgr, self.screenshot_mgr, self.rf_menu)
        return load_op.execute(shipment, dock_door, bol)

    def _run_post_message(self, payload: str | None = None) -> bool:
        self.nav_mgr.open_menu_item("POST", "Post Message (Integration)")
        message = payload or self.settings.app.post_message_text
        if not message:
            app_log("⚠️ No post message payload supplied.")
            return False
        success, response_info = self.post_message_mgr.send_message(message)
        app_log(f"Response summary: {response_info['summary']}")
        if response_info.get("payload"):
            app_log(f"Response payload: {response_info['payload']}")
        if not success:
            app_log("⚠️ Post Message failed.")
            return False
        self.screenshot_mgr.capture_rf_window(
            self.page,
            "post_confirmation",
            f"Post succeeded ({payload or 'default'})"
        )
        return success

    def _run_tasks_ui(self, search_term: str = "tasks", match_text: str = "Tasks (Configuration)") -> bool:
        succeeded = self.nav_mgr.open_tasks_ui(search_term, match_text)
        if not succeeded:
            app_log("❌ Tasks UI navigation failed")
        return succeeded


@contextmanager
def create_operation_services(settings: Any) -> Generator[OperationServices, None, None]:
    with BrowserManager(settings) as browser_mgr:
        page = browser_mgr.new_page()
        screenshot_mgr = ScreenshotManager(
            settings.browser.screenshot_dir,
            image_format=settings.browser.screenshot_format,
            image_quality=settings.browser.screenshot_quality,
        )
        page_mgr = PageManager(page)
        auth_mgr = AuthManager(page, screenshot_mgr, settings)
        nav_mgr = NavigationManager(page, screenshot_mgr)
        post_message_mgr = PostMessageManager(page, screenshot_mgr)
        rf_menu = RFMenuManager(
            page,
            page_mgr,
            screenshot_mgr,
            verbose_logging=settings.app.rf_verbose_logging,
            auto_click_info_icon=settings.app.auto_click_info_icon,
            verify_tran_id_marker=settings.app.verify_tran_id_marker,
        )
        conn_guard = ConnectionResetGuard(page, screenshot_mgr)
        orchestrator = AutomationOrchestrator(settings)
        runner = OperationRunner(
            settings,
            page,
            page_mgr,
            screenshot_mgr,
            auth_mgr,
            nav_mgr,
            post_message_mgr,
            rf_menu,
            conn_guard,
        )
        services = OperationServices(
            screenshot_mgr=screenshot_mgr,
            nav_mgr=nav_mgr,
            orchestrator=orchestrator,
            run_login=runner.run_login,
            run_change_warehouse=runner.run_change_warehouse,
            run_post_message=runner.run_post_message,
            receive=runner.receive,
            loading=runner.loading,
        )
        yield services
