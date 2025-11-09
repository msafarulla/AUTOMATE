from playwright.sync_api import Page, Frame
from typing import Optional


class PageManager:
    def __init__(self, page: Page):
        self.page = page
        self._setup_page()

    def _setup_page(self):
        """Setup page with click highlighter and other utilities"""
        self._inject_click_highlighter()
        self._disable_ext_animations()

    def _inject_click_highlighter(self):
        self.page.add_init_script("""
        document.addEventListener('click', function(e) {
            const dot = document.createElement('div');
            dot.style.width = '20px';
            dot.style.height = '20px';
            dot.style.border = '3px solid red';
            dot.style.borderRadius = '50%';
            dot.style.position = 'absolute';
            dot.style.top = (e.pageY - 10) + 'px';
            dot.style.left = (e.pageX - 10) + 'px';
            dot.style.zIndex = 999999;
            dot.style.opacity = 1;
            dot.style.pointerEvents = 'none';
            dot.style.transition = 'opacity 0.4s ease-out';
            document.body.appendChild(dot);
            setTimeout(() => { dot.style.opacity = 0; }, 50);
            setTimeout(() => { dot.remove(); }, 500);
        }, true);
        """)

    def _disable_ext_animations(self):
        """Mirror standalone script by disabling ExtJS window animations early."""
        self.page.add_init_script("""
        (() => {
            const disableFx = () => {
                if (!window.Ext || !Ext.onReady) {
                    return false;
                }

                const applyPatch = () => {
                    if (!window.Ext) {
                        return;
                    }
                    try {
                        Ext.enableFx = false;
                        if (Ext.fx && Ext.fx.Anim && Ext.fx.Anim.prototype) {
                            Ext.fx.Anim.prototype.duration = 1;
                            Ext.fx.Anim.prototype.easing = 'linear';
                        }
                        if (Ext.enableFx && Ext.core && Ext.core.Element && Ext.core.Element.prototype) {
                            Ext.core.Element.prototype.animate = Ext.emptyFn;
                        }
                        if (Ext.window && Ext.window.Window && Ext.window.Window.prototype) {
                            Ext.window.Window.prototype.animateTarget = null;
                            Ext.window.Window.prototype.expandOnShow = false;
                            Ext.window.Window.prototype.animCollapse = false;
                        }
                    } catch (err) {
                        console.warn("⚠️ Failed to disable Ext animations", err);
                    }
                };

                Ext.onReady(applyPatch);
                return true;
            };

            if (!disableFx()) {
                let attempts = 0;
                const timer = setInterval(() => {
                    if (disableFx() || attempts++ > 40) {
                        clearInterval(timer);
                    }
                }, 250);
            }

            // Additionally strip CSS transitions/animations in case Ext hooks miss something.
            const style = document.createElement('style');
            style.id = '__ext_disable_animations';
            style.innerHTML = `
                *, *::before, *::after {
                    animation: none !important;
                    transition: none !important;
                }
                .x-window, .x-panel, .x-mask {
                    animation: none !important;
                    transition: none !important;
                    transform: none !important;
                }
            `;
            document.documentElement.appendChild(style);
        })();
        """)

    def get_rf_iframe(self) -> Optional[Frame]:
        """Return the live RF Menu iframe, ignoring stale/detached frames."""
        def _live_frames():
            for frame in self.page.frames:
                try:
                    if frame.is_detached():
                        continue
                except Exception:
                    continue
                yield frame

        frames = list(_live_frames())

        # Prefer the newest frames first so recently opened RF windows are used.
        for frame in reversed(frames):
            try:
                if 'uxiframe' in frame.name and 'RFMenu' in frame.url:
                    return frame
            except Exception:
                continue

        # Fallback: any live uxiframe
        for frame in reversed(frames):
            try:
                if 'uxiframe' in frame.name:
                    return frame
            except Exception:
                continue

        # Final fallback: main frame
        return self.page.main_frame
