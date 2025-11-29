# Bulletproof Tab Clicking Methods

## Current Implementation ✅
The code now uses these strategies in order:
1. **ExtJS Native API** (`setActiveTab`)
2. **DOM Event Simulation** (mousedown/mouseup/click with coordinates)
3. **Parent Element Climbing** (clicks ancestors too)
4. **Exponential Backoff Retry** (3 attempts with increasing delays)
5. **Tab Panel Readiness Wait** (ensures ExtJS is ready)

## Additional Methods if Still Flaky

### Method 1: Force Visible + Wait for Animation
```python
# Add to _click_single_tab before clicking
page_target.evaluate("""
    (tabName) => {
        const el = Array.from(document.querySelectorAll('*'))
            .find(e => e.textContent?.trim() === tabName);
        if (el) {
            // Force visible
            el.style.display = 'block';
            el.style.visibility = 'visible';
            el.style.opacity = '1';
            el.style.pointerEvents = 'auto';

            // Disable animations temporarily
            el.style.transition = 'none';
            const parent = el.parentElement;
            if (parent) parent.style.transition = 'none';
        }
    }
""", tab_name)
time.sleep(0.3)  # Wait for styles to apply
```

### Method 2: Use Playwright's Native Tab Role Locator
```python
# More reliable than text search for ARIA tabs
try:
    tab = page_target.get_by_role("tab", name=tab_name, exact=True)
    tab.wait_for(state="visible", timeout=3000)
    tab.click(force=True, timeout=2000)
    return True
except:
    pass
```

### Method 3: XPath with Multiple Predicates
```python
# More precise than CSS selectors
xpath = f"""
    //span[@class='x-tab-strip-text' and normalize-space(text())='{tab_name}']
    | //*[@role='tab' and normalize-space(text())='{tab_name}']
    | //li[contains(@class,'x-tab') and .//span[normalize-space(text())='{tab_name}']]
"""
try:
    el = page_target.locator(f"xpath={xpath}").first
    el.click(force=True, timeout=2000)
    return True
except:
    pass
```

### Method 4: Wait for Network Idle Before Clicking
```python
# Ensure all AJAX calls have completed
def click_detail_tabs(target, config: TabClickConfig) -> bool:
    use_page = getattr(target, "page", None) or target

    # Wait for network to be quiet
    try:
        use_page.wait_for_load_state("networkidle", timeout=5000)
    except:
        pass

    # Continue with existing logic...
```

### Method 5: Screenshot-Based Validation
```python
# Verify the tab actually changed by comparing screenshots
def _verify_tab_changed(target, tab_name: str) -> bool:
    """Take screenshot before/after to verify tab changed."""
    before = target.screenshot()

    # Click logic here...

    time.sleep(0.5)
    after = target.screenshot()

    # Compare images (simple pixel diff)
    from PIL import Image
    import io
    img1 = Image.open(io.BytesIO(before))
    img2 = Image.open(io.BytesIO(after))

    # If images are identical, click failed
    return img1 != img2
```

### Method 6: JavaScript Mutation Observer
```python
# Wait for DOM changes after click to confirm success
TAB_CLICK_WITH_VERIFICATION = """
(tabName) => {
    return new Promise((resolve) => {
        const observer = new MutationObserver((mutations) => {
            // Tab change usually triggers DOM mutations
            if (mutations.length > 0) {
                observer.disconnect();
                resolve({ success: true, mutations: mutations.length });
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true
        });

        // Perform click...
        const el = /* find tab element */;
        el?.click();

        // Timeout after 2 seconds
        setTimeout(() => {
            observer.disconnect();
            resolve({ success: false, reason: 'no-dom-change' });
        }, 2000);
    });
}
"""
```

### Method 7: Focus + Keyboard Navigation
```python
# Sometimes keyboard is more reliable than mouse
def _try_keyboard_navigation(target, tab_name: str) -> bool:
    """Use keyboard to navigate to tab."""
    try:
        # Focus first tab
        target.evaluate("""
            () => {
                const tabs = document.querySelectorAll('[role="tab"]');
                tabs[0]?.focus();
            }
        """)

        # Find tab index
        tab_texts = target.evaluate("""
            () => Array.from(document.querySelectorAll('[role="tab"]'))
                       .map(t => t.textContent?.trim())
        """)

        if tab_name in tab_texts:
            idx = tab_texts.index(tab_name)

            # Arrow right to target tab
            for _ in range(idx):
                target.keyboard.press("ArrowRight")
                time.sleep(0.1)

            # Activate with Space or Enter
            target.keyboard.press("Space")
            return True
    except:
        pass
    return False
```

### Method 8: Poll for Active Tab State
```python
# Continuously verify until tab becomes active
def _wait_until_tab_active(target, tab_name: str, timeout_ms: int = 5000) -> bool:
    """Keep trying until the tab is actually active."""
    deadline = time.time() + timeout_ms / 1000

    while time.time() < deadline:
        # Check if tab is active
        is_active = target.evaluate("""
            (tabName) => {
                if (!window.Ext?.ComponentQuery) return false;

                const panels = Ext.ComponentQuery.query('tabpanel');
                for (const panel of panels) {
                    const active = panel.getActiveTab?.();
                    const title = active?.title || active?.tab?.text || '';
                    if (title === tabName) return true;
                }
                return false;
            }
        """, tab_name)

        if is_active:
            return True

        # Try clicking again
        _try_js_click(target, tab_name)
        time.sleep(0.2)

    return False
```

## Recommended Testing Approach

1. **Enable verbose logging** to see which strategy succeeds
2. **Add screenshots** before/after each tab click
3. **Monitor for patterns**: Which tabs fail? Same frame? Timing?
4. **Test in isolation**: Try clicking tabs in a minimal test script
5. **Check ExtJS version**: Some ExtJS versions have different APIs

## Nuclear Option: CDP Protocol Direct Injection

If all else fails, use Chrome DevTools Protocol to directly manipulate the ExtJS state:

```python
# Bypass all DOM and directly set the tab via CDP
def _nuclear_tab_switch(page, tab_name: str):
    """Use CDP to directly call ExtJS methods."""
    cdp = page.context.new_cdp_session(page)

    result = cdp.send('Runtime.evaluate', {
        'expression': f"""
            (function() {{
                const panels = Ext.ComponentQuery.query('tabpanel');
                for (const panel of panels) {{
                    const item = panel.items.items.find(i =>
                        (i.title || i.tab?.text || '') === '{tab_name}'
                    );
                    if (item) {{
                        panel.setActiveTab(item);
                        return true;
                    }}
                }}
                return false;
            }})()
        """,
        'returnByValue': True
    })

    return result.get('result', {}).get('value', False)
```

## Debugging Checklist

- [ ] Tabs are in iframes? (check frames_to_try)
- [ ] ExtJS version compatibility? (check Ext.version)
- [ ] Tabs dynamically loaded? (wait for readiness)
- [ ] Click events captured by parent? (event bubbling)
- [ ] CSS animations blocking? (disable transitions)
- [ ] Tab already active? (check before clicking)
- [ ] Multiple tab panels? (clicking wrong one)
- [ ] Shadow DOM? (need piercing selectors)

## Success Indicators to Log

```python
# After successful click, verify these:
- Tab has class 'x-tab-strip-active' or 'active'
- aria-selected="true" attribute
- Tab content panel is visible
- ExtJS panel.getActiveTab() returns correct item
- DOM mutation occurred
- Screenshot changed
```
