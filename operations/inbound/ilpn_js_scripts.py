"""
JavaScript templates for iLPN filter operations.
Extracted for readability and potential reuse.
"""

# DOM search script for finding and clicking iLPN rows
DOM_OPEN_ILPN_ROW_SCRIPT = """
(ilpn) => {
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const digits = (s) => (s || '').replace(/\\D+/g, '');
    const containsIlpn = (txt) => {
        const t = norm(txt);
        if (!t) return false;
        return t.includes(ilpn) || digits(t).includes(digits(ilpn));
    };

    const seenDocs = new Set();
    const docsToScan = [];

    const pushDoc = (doc) => {
        if (doc && !seenDocs.has(doc)) {
            seenDocs.add(doc);
            docsToScan.push(doc);
        }
    };

    pushDoc(document);
    Array.from(document.querySelectorAll('iframe')).forEach(ifr => {
        try { pushDoc(ifr.contentDocument); } catch (e) {}
    });

    let hit = null;
    let scannedTables = 0;
    let lastIframeId = null;
    let lastIframeSrc = null;

    // Phase 1: Table row search
    for (const doc of docsToScan) {
        const ownerFrame = doc.defaultView?.frameElement;
        lastIframeId = ownerFrame?.id || null;
        lastIframeSrc = ownerFrame?.src || null;

        const tables = Array.from(doc.querySelectorAll('table'));
        scannedTables += tables.length;

        for (let tIdx = 0; tIdx < tables.length; tIdx++) {
            const rows = Array.from(tables[tIdx].querySelectorAll('tr'));
            for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                const row = rows[rIdx];
                const txt = norm(row.innerText);
                if (containsIlpn(txt)) {
                    hit = {
                        tableIdx: tIdx,
                        rowIdx: rIdx,
                        text: txt.slice(0, 200),
                        iframeId: ownerFrame?.id || null,
                        iframeSrc: ownerFrame?.src || null,
                    };
                    const targetEl = row.querySelector('a, button') || row;
                    try { targetEl.scrollIntoView({ block: 'center' }); } catch (e) {}
                    
                    const checkbox = row.querySelector('input[type="checkbox"], .x-grid-row-checker');
                    try { checkbox?.click?.(); } catch (e) {}
                    
                    try { 
                        targetEl.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 })); 
                    } catch (e) {}
                    try { 
                        targetEl.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 })); 
                    } catch (e) {}
                    
                    try {
                        const buttons = Array.from((ownerFrame?.contentDocument || doc).querySelectorAll('button, a'));
                        const viewBtn = buttons.find(b => /view/i.test(b.textContent || ''));
                        viewBtn?.click?.();
                    } catch (e) {}
                    
                    return { ok: true, ...hit, tablesScanned: scannedTables };
                }
            }
        }
    }

    // Phase 2: Broader text search fallback
    for (const doc of docsToScan) {
        const ownerFrame = doc.defaultView?.frameElement;
        const elems = Array.from(doc.querySelectorAll('tr, td, span, div, a, button, li, [role="row"]'));
        
        for (const el of elems) {
            const txt = norm(el.innerText);
            if (!txt || !containsIlpn(txt)) continue;
            
            const targetEl = el.closest('tr, .x-grid-row, .x-grid-item, [role="row"], a, button') || el;
            try { targetEl.scrollIntoView({ block: 'center' }); } catch (e) {}
            
            const checkbox = targetEl.querySelector?.('input[type="checkbox"], .x-grid-row-checker');
            try { checkbox?.click?.(); } catch (e) {}
            try { 
                targetEl.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 })); 
            } catch (e) {}
            try { 
                targetEl.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 })); 
            } catch (e) {}
            
            try {
                const buttons = Array.from((ownerFrame?.contentDocument || doc).querySelectorAll('button, a'));
                const viewBtn = buttons.find(b => /view/i.test(b.textContent || ''));
                viewBtn?.click?.();
            } catch (e) {}
            
            return {
                ok: true,
                reason: 'text_search',
                iframeId: ownerFrame?.id || null,
                iframeSrc: ownerFrame?.src || null,
                text: txt.slice(0, 200),
                tablesScanned: scannedTables
            };
        }
    }

    return {
        ok: false,
        reason: 'no_match',
        iframeId: lastIframeId,
        iframeSrc: lastIframeSrc,
        tables: scannedTables
    };
}
"""

# ExtJS store count retrieval
EXT_STORE_COUNT_SCRIPT = """
() => {
    if (!window.Ext?.ComponentQuery) return null;
    const grids = Ext.ComponentQuery.query('grid') || [];
    for (let i = grids.length - 1; i >= 0; i -= 1) {
        const g = grids[i];
        try {
            if (g.isHidden?.() || g.isDestroyed?.()) continue;
            const cnt = g.getStore?.()?.getCount?.();
            if (typeof cnt === 'number') return cnt;
        } catch (e) {}
    }
    return null;
}
"""

# ExtJS first row opener
EXT_OPEN_FIRST_ROW_SCRIPT = """
() => {
    if (!window.Ext?.ComponentQuery) return false;
    const grids = Ext.ComponentQuery.query('grid') || [];
    for (let i = grids.length - 1; i >= 0; i -= 1) {
        const g = grids[i];
        try {
            if (g.isHidden?.() || g.isDestroyed?.()) continue;
            const store = g.getStore?.();
            if (!store || store.getCount?.() !== 1) continue;
            const rec = store.getAt?.(0);
            if (!rec) continue;

            const sel = g.getSelectionModel?.();
            sel?.select(rec);

            const view = g.getView?.();
            const row = view?.getRow?.(rec) || view?.getNode?.(0);
            if (row) {
                row.scrollIntoView({ block: 'center' });
                row.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 }));
                row.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }));
                return true;
            }
        } catch (e) {}
    }
    return false;
}
"""

# Hidden input fill fallback
HIDDEN_INPUT_FILL_SCRIPT = """
(ilpn) => {
    const val = String(ilpn);
    const inputs = Array.from(document.querySelectorAll('input'));
    if (!inputs.length) return false;

    const score = (el) => {
        const txt = [
            el.name || '',
            el.id || '',
            el.placeholder || '',
            el.getAttribute('aria-label') || ''
        ].join(' ').toLowerCase();
        let s = 0;
        if (txt.includes('lpn')) s += 3;
        if (txt.includes('filter')) s += 2;
        if (el.type === 'hidden') s += 1;
        return s;
    };

    const ranked = inputs
        .map(el => ({ el, s: score(el) }))
        .filter(entry => entry.s > 0)
        .sort((a, b) => b.s - a.s);

    if (!ranked.length) return false;

    const el = ranked[0].el;
    try {
        el.removeAttribute('disabled');
        el.style.display = '';
        el.style.visibility = 'visible';
        el.style.opacity = '1';
    } catch (e) {}

    try { el.focus?.(); } catch (e) {}
    el.value = val;
    
    ['input', 'change', 'keyup', 'keydown', 'keypress'].forEach(evt => {
        try { 
            el.dispatchEvent(new Event(evt, { bubbles: true, cancelable: true })); 
        } catch (e) {}
    });
    
    return true;
}
"""

# Tab diagnostic script
TAB_DIAGNOSTIC_SCRIPT = """
() => {
    const allElements = Array.from(document.querySelectorAll('*'));
    const potentialTabs = [];
    
    for (const el of allElements) {
        const text = (el.textContent || '').trim();
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        
        if (text && rect.width > 20 && rect.height > 10 && rect.width < 500 && rect.height < 150) {
            const role = el.getAttribute('role') || '';
            const cls = el.className || '';
            if (role.includes('tab') || cls.toLowerCase().includes('tab')) {
                potentialTabs.push({
                    text: text,
                    cls: cls,
                    role: role,
                    tag: el.tagName,
                    visible: style.display !== 'none' && style.visibility !== 'hidden',
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                });
            }
        }
    }

    return {
        potentialTabs: potentialTabs,
        totalElements: allElements.length
    };
}
"""

# Tab click via JS
TAB_CLICK_SCRIPT = """
(tabName) => {
    const allElements = Array.from(document.querySelectorAll('*'));

    for (const el of allElements) {
        const text = (el.textContent || '').trim();
        if (text !== tabName) continue;
        
        try {
            el.scrollIntoView({ block: 'center' });
            el.click();
            return { success: true, tag: el.tagName, text: text };
        } catch (e) {
            el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            return { success: true, tag: el.tagName, text: text, method: 'dispatch' };
        }
    }

    return { success: false, reason: 'not found' };
}
"""