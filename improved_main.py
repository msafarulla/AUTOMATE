"""
Main entry point for warehouse automation.
Orchestrates operations with proper error handling and retry logic.
"""
from functools import wraps
from typing import Optional, Callable, Any
from dataclasses import dataclass

from operations.inbound.receive import ReceiveOperation
from operations.outbound.loading import LoadingOperation
from ui.rf_menu import RFMenuManager
from DB import DB
from config.settings import Settings
from core.browser import BrowserManager
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from core.connection_guard import ConnectionResetGuard, ConnectionResetDetected
from ui.auth import AuthManager
from ui.navigation import NavigationManager
from ui.post_message import PostMessageManager
from core.logger import app_log


@dataclass
class OperationResult:
    """Result of an operation execution"""
    success: bool
    operation: str
    error: Optional[str] = None
    retry_count: int = 0


class AutomationOrchestrator:
    """
    Orchestrates warehouse operations with retry logic and error handling.
    """
    
    def __init__(self, settings: Settings, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries
        self.results: list[OperationResult] = []
    
    def run_with_retry(
        self, 
        operation_func: Callable, 
        operation_name: str,
        *args,
        **kwargs
    ) -> OperationResult:
        """
        Execute an operation with automatic retry on failure.
        
        Args:
            operation_func: The operation function to execute
            operation_name: Name for logging
            *args, **kwargs: Arguments to pass to operation
            
        Returns:
            OperationResult with success status and details
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                app_log(f"{'🔄 Retry' if retry_count > 0 else '▶️ Starting'} {operation_name} (attempt {retry_count + 1}/{self.max_retries})")
                
                success = operation_func(*args, **kwargs)
                
                if success:
                    result = OperationResult(
                        success=True,
                        operation=operation_name,
                        retry_count=retry_count
                    )
                    app_log(f"✅ {operation_name} completed successfully")
                    self.results.append(result)
                    return result
                
                # Operation returned False
                last_error = "Operation returned False"
                retry_count += 1
                
                if retry_count < self.max_retries:
                    app_log(f"⚠️ {operation_name} failed, retrying...")
                
            except ConnectionResetDetected as e:
                # Connection issues should halt everything
                raise
                
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                app_log(f"❌ {operation_name} error: {e}")
                
                if retry_count < self.max_retries:
                    app_log(f"🔄 Retrying {operation_name}...")
        
        # All retries exhausted
        result = OperationResult(
            success=False,
            operation=operation_name,
            error=last_error,
            retry_count=retry_count
        )
        app_log(f"❌ {operation_name} failed after {retry_count} attempts")
        self.results.append(result)
        return result
    
    def print_summary(self):
        """Print summary of all operations"""
        app_log("\n" + "="*60)
        app_log("📊 OPERATION SUMMARY")
        app_log("="*60)
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful
        
        app_log(f"Total operations: {total}")
        app_log(f"✅ Successful: {successful}")
        app_log(f"❌ Failed: {failed}")
        
        if failed > 0:
            app_log("\nFailed operations:")
            for result in self.results:
                if not result.success:
                    app_log(f"  • {result.operation}: {result.error}")
        
        app_log("="*60 + "\n")


def main():
    """Main entry point with improved orchestration"""
    
    # Load configuration
    settings = Settings.from_env()
    
    # Load credentials
    with DB('qa') as c1:
        username = c1.app_server_user
        password = c1.app_server_pass
    
    # Initialize browser
    with BrowserManager(settings) as browser_mgr:
        page = browser_mgr.new_page()
        
        # Initialize managers
        screenshot_mgr = ScreenshotManager(
            settings.browser.screenshot_dir,
            image_format=settings.browser.screenshot_format,
            image_quality=settings.browser.screenshot_quality,
        )
        page_mgr = PageManager(page)
        auth_mgr = AuthManager(page, screenshot_mgr)
        nav_mgr = NavigationManager(page, screenshot_mgr)
        post_message_mgr = PostMessageManager(page, screenshot_mgr)
        rf_menu = RFMenuManager(
            page,
            page_mgr,
            screenshot_mgr,
            verbose_logging=settings.app.rf_verbose_logging,
        )
        conn_guard = ConnectionResetGuard(page, screenshot_mgr)
        
        # Create orchestrator
        orchestrator = AutomationOrchestrator(settings, max_retries=3)
        
        def guarded(func):
            """Decorator to run handlers inside connection guard"""
            @wraps(func)
            def wrapper(*args, **kwargs):
                return conn_guard.guard(func, *args, **kwargs)
            return wrapper
        
        @guarded
        def run_login():
            """Authenticate once per session"""
            auth_mgr.login(username, password, settings.app.base_url)
        
        @guarded
        def run_change_warehouse():
            """Switch warehouses safely"""
            nav_mgr.change_warehouse(settings.app.change_warehouse)
        
        @guarded
        def receive(asn: str, item: str, quantity: int = 1) -> bool:
            """Execute receive operation"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return receive_op.execute(asn, item, quantity)
        
        @guarded
        def loading(shipment: str, dock_door: str, bol: str) -> bool:
            """Execute loading operation"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            load_op = LoadingOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return load_op.execute(shipment, dock_door, bol)
        
        @guarded
        def run_post_cycle():
            """Send post message"""
            nav_mgr.open_menu_item("POST", "Post Message (Integration)")
            success, response_info = post_message_mgr.send_message(
                settings.app.post_message_text
            )
            app_log(f"Response summary: {response_info['summary']}")
            if response_info.get("payload"):
                app_log(f"Response payload: {response_info['payload']}")
            if not success:
                app_log("⚠️ Post Message failed; continuing with remaining flow.")
            return success
        
        try:
            # Initial setup
            app_log("🚀 Starting warehouse automation...")
            run_login()
            run_change_warehouse()
            
            # Define your workflow cycles
            workflows = [
                {
                    'asn': '23907432',
                    'item': 'J105SXC200TR',
                    'quantity': 1,
                    'shipment': '23907432',
                    'dock_door': 'J105SXC200TR',
                    'bol': 'MOH'
                },
                # Add more workflows as needed
            ]
            
            # Execute workflows
            for i, workflow in enumerate(workflows, 1):
                app_log(f"\n{'='*60}")
                app_log(f"📦 WORKFLOW {i}/{len(workflows)}")
                app_log(f"{'='*60}")
                
                # Execute receive
                receive_result = orchestrator.run_with_retry(
                    receive,
                    f"Receive (Workflow {i})",
                    asn=workflow['asn'],
                    item=workflow['item'],
                    quantity=workflow['quantity']
                )
                
                # Only proceed to loading if receive succeeded
                if receive_result.success:
                    orchestrator.run_with_retry(
                        loading,
                        f"Loading (Workflow {i})",
                        shipment=workflow['shipment'],
                        dock_door=workflow['dock_door'],
                        bol=workflow['bol']
                    )
                else:
                    app_log(f"⏭️ Skipping loading for workflow {i} due to receive failure")
            
            # Print summary
            orchestrator.print_summary()
            
            app_log("✅ Automation completed!")
            input("Press Enter to exit...")
            
        except ConnectionResetDetected as e:
            app_log(f"❌ Connection lost: {e}")
            orchestrator.print_summary()
            
        except KeyboardInterrupt:
            app_log("\n⚠️ Interrupted by user")
            orchestrator.print_summary()
            
        except Exception as e:
            app_log(f"❌ Fatal error in main flow: {e}")
            import traceback
            traceback.print_exc()
            orchestrator.print_summary()


if __name__ == "__main__":
    main()