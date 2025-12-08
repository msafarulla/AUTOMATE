from playwright.sync_api import (
    sync_playwright,
    ViewportSize,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
import threading
import configparser
from DB import DB
import ctypes
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import sys
import select
import queue
from typing import cast, Optional
from utils.wait_utils import WaitUtils

c1 = DB('dev')
config = configparser.ConfigParser()
config.read_string(c1.clean_content)

# which warehouse?
whse = 'LPM'

_snap_counters = {}

username = config['dev']['app_server_user']

# Environment mapping: Name -> (URL, password)
environments = {
    "DEV":  (config['dev']['app_server'], config['dev']['app_server_pass']),
    "QA": (config['qa']['app_server'], config['qa']['app_server_pass']),
    "PROD": (config['prod']['app_server'], config['prod']['app_server_pass']),
}


def get_screen_size_safe():
    try:
        # Windows
        if os.name == 'nt':
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            return width, height

        # macOS / Linux
        else:
            import subprocess
            output = subprocess.check_output(['stty', 'size'], stderr=subprocess.DEVNULL).split()
            rows, cols = map(int, output)
            return cols, rows

    except Exception as e:
        print(f"⚠️ Screen size detection failed: {e}")
        return None, None


def get_scale_factor():
    try:
        user32 = ctypes.windll.user32
        dc = user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        user32.ReleaseDC(0, dc)
        return round(dpi / 96.0, 2)
    except:
        return 1.0


width, height = get_screen_size_safe()


# Screenshot helper
def snap(page, label, env):
    # Track sequential numbering per environment
    count = _snap_counters.get(env, 0) + 1
    _snap_counters[env] = count

    os.makedirs("screenshots", exist_ok=True)
    filename = f"screenshots/{count}_{env}_{label}.png"

    try:
        # Wait a moment for any animations/rendering to complete
        WaitUtils.wait_brief(page)

        # Inject a bright cyan pulsating cursor at current mouse position
        page.evaluate("""
            () => {
                // Remove any existing cursor overlay
                const existing = document.getElementById('__screenshot_cursor');
                if (existing) existing.remove();

                // Create cursor dot at current mouse position
                const cursor = document.createElement('div');
                cursor.id = '__screenshot_cursor';
                cursor.style.cssText = `
                    position: fixed;
                    width: 14px;
                    height: 14px;
                    background: cyan;               /* Bright cyan fill */
                    border: 2px solid white;        /* White outline for contrast */
                    border-radius: 50%;
                    pointer-events: none;
                    z-index: 99999999;
                    box-shadow: 0 0 12px rgba(0, 255, 255, 0.9); /* Cyan glow */
                `;

                // Position at last known mouse coordinates
                if (window.__lastMouseX !== undefined && window.__lastMouseY !== undefined) {
                    cursor.style.left = (window.__lastMouseX - 7) + 'px';
                    cursor.style.top = (window.__lastMouseY - 7) + 'px';
                    document.body.appendChild(cursor);

                    // Add a quick pulsing animation
                    cursor.animate(
                        [
                            { transform: 'scale(1)', opacity: 1 },
                            { transform: 'scale(1.35)', opacity: 0.85 },
                            { transform: 'scale(1)', opacity: 1 }
                        ],
                        { duration: 600, iterations: 1, easing: 'ease-in-out' }
                    );
                }
            }
        """)

        # Small delay to ensure cursor is rendered
        WaitUtils.wait_brief(page)

        # Disable animations for cleaner screenshot
        page.evaluate("""
            () => {
                const style = document.createElement('style');
                style.innerHTML = '* { animation: none !important; transition: none !important; }';
                document.head.appendChild(style);
            }
        """)

        # Full page screenshot to capture everything
        page.screenshot(path=filename, full_page=False, animations="disabled")

        # Clean up cursor overlay
        page.evaluate("() => document.getElementById('__screenshot_cursor')?.remove()")

        print(f"📸 Screenshot saved: {filename}")
    except Exception as e:
        print(f"⚠️ Screenshot warning for {env}: {e}")
        # Fallback to basic screenshot
        try:
            page.screenshot(path=filename)
            print(f"📸 Screenshot saved (fallback): {filename}")
        except Exception as e2:
            print(f"❌ Screenshot failed for {env}: {e2}")


def close_visible_windows_dom(page: Page, env_name: Optional[str] = None):
    """Close visible popup windows using DOM selectors and keyboard shortcuts"""
    label = f"[{env_name}] " if env_name else ""
    closed = 0

    try:
        # Wait a bit to see if windows appear
        try:
            page.wait_for_selector("div.x-window:visible", timeout=4000)
        except PlaywrightTimeoutError:
            print(f"ℹ️ {label}No visible windows detected")
            return False

        # Try closing windows multiple times
        for attempt in range(5):
            windows = page.locator("div.x-window:visible")
            count = windows.count()

            if count == 0:
                break

            print(f"⚠️ {count} {'windows' if count > 1 else 'widow'} found. Atteming to close now")

            # Try clicking close button on first visible window
            try:
                close_btn = windows.first.locator(".x-tool-close").first
                if close_btn.is_visible():
                    close_btn.click()
                    closed += 1
                    WaitUtils.wait_brief(page)
                    continue
            except Exception:
                pass

            # Fallback: press Escape
            try:
                page.keyboard.press("Escape")
                closed += 1
                WaitUtils.wait_brief(page)
            except Exception:
                break

        if closed:
            print(f"✅ {label}Closed {closed} {'windows' if count > 1 else 'window'}")
        else:
            print(f"ℹ️ {label}No windows needed closing")

        return closed > 0

    except Exception as exc:
        print(f"⚠️ {label}Failed to close windows: {exc}")
        return False


def select_facility(page: Page, env_name: str, warehouse: str):
    """Select warehouse facility using DOM selectors"""
    try:
        # Click the facility dropdown (look for "- SOA" text)
        dropdown = page.locator(":text-matches('- SOA')").first
        dropdown.click()
        print(f"✅ [{env_name}] Clicked facility dropdown")

        # Click the input field and wait for options to appear
        warehouse_input = page.locator("input[type='text']:visible").first
        warehouse_input.click()
        page.wait_for_selector("ul.x-list-plain li", timeout=2000)

        # Select the warehouse from the list
        page.locator(f"ul.x-list-plain li:has-text('{warehouse}')").click()
        print(f"✅ [{env_name}] Selected warehouse: {warehouse}")

        # Click Apply button
        page.get_by_text("Apply", exact=True).click()
        WaitUtils.wait_brief(page)

        # Wait for UI to be ready
        page.locator("a.x-btn").first.wait_for(timeout=1000)
        print(f"✅ [{env_name}] Facility selection complete")

    except Exception as e:
        raise RuntimeError(f"Failed to select facility: {e}")


# HTTP Server for screenshot button
screenshot_queue = queue.Queue()


class ScreenshotHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/screenshot'):
            query = parse_qs(urlparse(self.path).query)
            env = query.get('env', ['unknown'])[0]
            screenshot_queue.put(env)  # thread-safe put
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs


def run_server():
    server = HTTPServer(('localhost', 8765), ScreenshotHandler)
    server.serve_forever()


# Per-tab logic
def login_and_setup_tab(context, env_name, url, password):
    page = context.new_page()
    print(f"🌐 Opening {env_name}...")

    warehouse_reapply_state = {"ready": False, "busy": False}

    def reapply_warehouse_on_load():
        if not warehouse_reapply_state["ready"] or warehouse_reapply_state["busy"]:
            return

        warehouse_reapply_state["busy"] = True
        try:
            print(f"🔁 [{env_name}] Refresh detected, reapplying warehouse {whse}")
            try:
                close_visible_windows_dom(page, env_name)
            except Exception as exc:
                print(f"⚠️ [{env_name}] Error closing popups before reload reapply: {exc}")

            page.wait_for_timeout(1500)
            select_facility(page, env_name, whse)
            facility_label = page.evaluate(
                """(warehouse) => document.querySelector('[class*="facility"]')?.textContent || ''""",
                whse,
            )
            if whse and whse not in facility_label:
                print(f"⚠️ [{env_name}] Warehouse label still missing after reapply: {facility_label}")
        except Exception as exc:
            print(f"⚠️ [{env_name}] Reload reapply failed: {exc}")
        finally:
            warehouse_reapply_state["busy"] = False

    page.on("load", lambda _: reapply_warehouse_on_load())

    # Add cyan click dot animation + track mouse position
    page.add_init_script("""
    // Track mouse position globally
    window.__lastMouseX = 0;
    window.__lastMouseY = 0;

    document.addEventListener('mousemove', function(e) {
        window.__lastMouseX = e.clientX;
        window.__lastMouseY = e.clientY;
    }, true);

    document.addEventListener('click', function(e) {
        if (e.shiftKey) {
            e.preventDefault();

            const disableSelect = document.createElement('style');
            disableSelect.innerHTML = '* { user-select: none !important; }';
            disableSelect.id = '__clickblock';
            document.head.appendChild(disableSelect);

            if (window.getSelection) {
                const sel = window.getSelection();
                if (sel && sel.removeAllRanges) sel.removeAllRanges();
            }
        }

        const dot = document.createElement('div');
        dot.style.width = '20px';
        dot.style.height = '20px';
        dot.style.border = '3px solid cyan';
        dot.style.borderRadius = '50%';
        dot.style.position = 'absolute';
        dot.style.top = (e.pageY - 10) + 'px';
        dot.style.left = (e.pageX - 10) + 'px';
        dot.style.zIndex = 999999;
        dot.style.opacity = 1;
        dot.style.pointerEvents = 'none';
        dot.style.transition = 'opacity 0.4s ease-out';
        document.body.appendChild(dot);

        const delay = e.shiftKey ? 2500 : 50;
        setTimeout(() => { dot.style.opacity = 0; }, delay);
        setTimeout(() => { dot.remove(); }, delay + 5000);

        if (e.shiftKey) {
            setTimeout(() => {
                const el = document.getElementById('__clickblock');
                if (el) el.remove();
            }, delay + 500);
        }
    }, true);
    """)

    # 📸 Add keyboard shortcut for screenshot
    page.add_init_script(f"""
        (() => {{
            document.addEventListener('keydown', (e) => {{
                if (e.key === '~') {{
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();

                    // Flash the cursor dot briefly as feedback
                    if (window.__lastMouseX !== undefined && window.__lastMouseY !== undefined) {{
                        const flash = document.createElement('div');
                        flash.style.cssText = `
                            position: fixed;
                            left: ${{window.__lastMouseX - 8}}px;
                            top: ${{window.__lastMouseY - 8}}px;
                            width: 16px;
                            height: 16px;
                            background: rgba(0, 255, 157, 0.9);
                            border: 2px solid rgba(255, 255, 255, 0.9);
                            border-radius: 50%;
                            pointer-events: none;
                            z-index: 99999999;
                            box-shadow: 0 0 15px rgba(0, 255, 157, 0.8);
                            animation: pulse 0.3s ease-out;
                        `;

                        const style = document.createElement('style');
                        style.innerHTML = `
                            @keyframes pulse {{
                                0% {{ transform: scale(1); opacity: 1; }}
                                50% {{ transform: scale(1.5); opacity: 0.8; }}
                                100% {{ transform: scale(1); opacity: 0; }}
                            }}
                        `;
                        document.head.appendChild(style);
                        document.body.appendChild(flash);

                        setTimeout(() => flash.remove(), 300);
                        setTimeout(() => style.remove(), 300);
                    }}

                    // Trigger screenshot
                    fetch('http://localhost:8765/screenshot?env={env_name}')
                        .catch(err => console.error('Screenshot failed:', err));
                }}
            }});
        }})();
    """)

    # Go to env URL
    page.goto(url, wait_until="networkidle")

    # Login
    page.fill('#username', username)
    page.fill('#password', password)
    page.dispatch_event('#username', 'input')
    page.dispatch_event('#password', 'input')
    page.dispatch_event('#username', 'keyup')
    page.dispatch_event('#password', 'keyup')
    page.wait_for_function("!document.getElementById('loginButton').disabled")
    with page.expect_navigation(wait_until="networkidle"):
        page.click('#loginButton')

    # Set the title after login
    page.evaluate(f"document.title = '{env_name} - WMS'")

    # Lock title across refreshes
    page.add_init_script(f"""
    (() => {{
        const desiredTitle = "{env_name} - WMS";
        const lockTitle = () => {{
            if (document.title !== desiredTitle) {{
                document.title = desiredTitle;
            }}
        }};
        window.addEventListener('load', lockTitle);
        const observer = new MutationObserver(lockTitle);
        const titleEl = document.querySelector('title');
        if (titleEl) observer.observe(titleEl, {{ childList: true, subtree: true }});
        lockTitle();
    }})();
    """)

    # Lock warehouse selection across refreshes
    page.add_init_script(f"""
    (() => {{
        const targetWarehouse = "{whse}";

        async function ensureWarehouse() {{
            try {{
                // Wait for the page to be ready
                await new Promise(resolve => {{
                    if (document.readyState === 'complete') {{
                        resolve();
                    }} else {{
                        window.addEventListener('load', resolve);
                    }}
                }});

                // Give the app a moment to initialize
                await new Promise(resolve => setTimeout(resolve, 2000));

                // Check if we need to change warehouse (look for "- SOA" text)
                const facilityText = document.querySelector('[class*="facility"]')?.textContent;
                if (facilityText && !facilityText.includes(targetWarehouse)) {{
                    console.log('🏭 Warehouse mismatch detected, reapplying:', targetWarehouse);

                    // Click the facility dropdown
                    const dropdown = Array.from(document.querySelectorAll('*'))
                        .find(el => el.textContent?.includes('- SOA'));
                    if (dropdown) {{
                        dropdown.click();
                        await new Promise(resolve => setTimeout(resolve, 500));

                        // Click the input field
                        const input = document.querySelector("input[type='text']:not([style*='display: none'])");
                        if (input) {{
                            input.click();
                            await new Promise(resolve => setTimeout(resolve, 500));

                            // Select the warehouse from list
                            const option = Array.from(document.querySelectorAll('ul.x-list-plain li'))
                                .find(li => li.textContent.includes(targetWarehouse));
                            if (option) {{
                                option.click();
                                await new Promise(resolve => setTimeout(resolve, 500));

                                // Click Apply button
                                const applyBtn = Array.from(document.querySelectorAll('*'))
                                    .find(el => el.textContent === 'Apply' && el.tagName !== 'DIV');
                                if (applyBtn) {{
                                    applyBtn.click();
                                    console.log('✅ Warehouse reapplied:', targetWarehouse);
                                }}
                            }}
                        }}
                    }}
                }}
            }} catch (err) {{
                console.warn('⚠️ Warehouse persistence check failed:', err);
            }}
        }}

        // Run on every load
        window.addEventListener('load', ensureWarehouse);
        ensureWarehouse();
    }})();
    """)

    # Close any popup windows
    close_visible_windows_dom(page, env_name)

    # Select warehouse
    try:
        select_facility(page, env_name, whse)
        warehouse_reapply_state["ready"] = True
    except Exception as e:
        print(f"❌ [{env_name}] Facility selection failed: {e}")
        return

    # Auto-click after 5 minutes of inactivity
    page.add_init_script("""
        (() => {
            let inactivityTimer;

            function simulateClick() {
                console.log('🖱️ Auto-clicking after 5 min of inactivity...');
                const el = document.querySelector('button, a.x-btn, [role="button"]');
                if (el) {
                    el.click();
                    console.log('✅ Clicked element:', el);
                } else {
                    console.warn('⚠️ No clickable element found for auto-click.');
                }
            }

            function resetInactivityTimer() {
                clearTimeout(inactivityTimer);
                inactivityTimer = setTimeout(simulateClick, 5 * 60 * 1000);
            }

            ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(evt => {
                document.addEventListener(evt, resetInactivityTimer, true);
            });

            resetInactivityTimer();
        })();
    """)

    return page


# Entry point
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=False,
        args=[
            "--start-fullscreen",
            "--window-position=0,0",
            "--unsafely-treat-insecure-origin-as-secure=http://soa430.subaru1.com:12000",
            "--allow-running-insecure-content",
            "--ignore-certificate-errors",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-blink-features=AutomationControlled"
        ]
    )

    scale = get_scale_factor()
    print(f"Detected screen: {width}x{height}, scale={scale}")

    # Correct the viewport by dividing by scale
    viewport_width = int(width / scale)
    viewport_height = int((height - 300) / scale)

    context = browser.new_context(
        viewport=cast(ViewportSize, {"width": viewport_width, "height": viewport_height}),
        device_scale_factor=scale,
        ignore_https_errors=True
    )

    # Start HTTP server in background
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    tabs = []
    for env, (url, password) in environments.items():
        page = login_and_setup_tab(context, env, url, password)
        if page:
            tabs.append(page)

    print("📸 Press ~ (tilde/Shift+`) in browser to capture screenshots")
    print("   Type 'x' + Enter in terminal to exit")


    # Non-blocking input check
    def input_available():
        if os.name == 'nt':
            import msvcrt
            return msvcrt.kbhit()
        else:
            return sys.stdin in select.select([sys.stdin], [], [], 0)[0]


    while True:
        try:
            env = screenshot_queue.get(timeout=1)

            found = False
            for page in tabs:
                env_name = page.title().split(" - ")[0]
                if env_name.upper() == env.upper():
                    print(f"📸 Capturing tab: {env_name}")
                    snap(page, "button_capture", env_name)
                    found = True
                    break

            if not found:
                print(f"⚠️ No open tab found for environment '{env}'")

            screenshot_queue.task_done()

        except queue.Empty:
            pass
