/* ============================================
   KAMY CONTROL — GLOBAL JS v4
   Theme Toggle + Mobile Sidebar + Dashboard Customization
   ============================================ */

// === THEME TOGGLE ===
(function initTheme() {
    const saved = localStorage.getItem('kamy-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
})();

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('kamy-theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;
    const iconName = theme === 'dark' ? 'sun' : 'moon';
    btn.innerHTML = `<i data-lucide="${iconName}"></i>`;
    if (typeof lucide !== 'undefined') {
        lucide.createIcons({ nodes: [btn] });
    }
}

// === MOBILE SIDEBAR ===
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (!sidebar) return;
    
    const isOpen = sidebar.classList.contains('open');
    if (isOpen) {
        sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('visible');
    } else {
        sidebar.classList.add('open');
        if (overlay) overlay.classList.add('visible');
    }
}

function closeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
}

// Close sidebar on window resize to desktop
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
        closeSidebar();
    }
});

// === DASHBOARD WIDGET CUSTOMIZATION ===
const DASHBOARD_LAYOUT_KEY = 'kamy-dashboard-layout';

function getDashboardLayout() {
    try {
        const saved = localStorage.getItem(DASHBOARD_LAYOUT_KEY);
        return saved ? JSON.parse(saved) : null;
    } catch { return null; }
}

function saveDashboardLayout(layout) {
    localStorage.setItem(DASHBOARD_LAYOUT_KEY, JSON.stringify(layout));
}

function resetDashboardLayout() {
    localStorage.removeItem(DASHBOARD_LAYOUT_KEY);
    location.reload();
}

function initDashboardCustomization() {
    const container = document.getElementById('widgets-container');
    if (!container) return;

    const widgets = container.querySelectorAll('[data-widget-id]');
    const layout = getDashboardLayout();

    // Apply saved layout (order + visibility)
    if (layout) {
        // Sort by saved order
        const orderMap = {};
        layout.forEach((item, i) => { orderMap[item.id] = i; });
        
        const sorted = Array.from(widgets).sort((a, b) => {
            const aOrder = orderMap[a.dataset.widgetId] ?? 999;
            const bOrder = orderMap[b.dataset.widgetId] ?? 999;
            return aOrder - bOrder;
        });

        sorted.forEach(w => container.appendChild(w));

        // Apply visibility
        layout.forEach(item => {
            const el = container.querySelector(`[data-widget-id="${item.id}"]`);
            if (el && item.hidden) {
                el.style.display = 'none';
                el.dataset.hidden = 'true';
            }
        });
    }
}

function toggleEditMode() {
    const container = document.getElementById('widgets-container');
    if (!container) return;

    const isEditing = container.classList.toggle('editing');
    const btn = document.getElementById('customizeBtn');
    
    if (isEditing) {
        btn.innerHTML = '<i data-lucide="check"></i> Salvar Layout';
        btn.style.background = 'var(--success)';
        enableDragAndDrop(container);
    } else {
        btn.innerHTML = '<i data-lucide="layout-grid"></i> Personalizar';
        btn.style.background = '';
        saveCurrentLayout(container);
        disableDragAndDrop(container);
    }
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function enableDragAndDrop(container) {
    const widgets = container.querySelectorAll('[data-widget-id]');
    
    widgets.forEach(w => {
        w.setAttribute('draggable', 'true');
        
        // Add drag handle + toggle visibility button
        let controls = w.querySelector('.widget-controls');
        if (!controls) {
            controls = document.createElement('div');
            controls.className = 'widget-controls';
            controls.innerHTML = `
                <span class="drag-handle" title="Arraste para reordenar"><i data-lucide="grip-vertical"></i></span>
                <button class="visibility-toggle" title="Mostrar/Esconder" onclick="toggleWidgetVisibility(this)">
                    <i data-lucide="${w.dataset.hidden === 'true' ? 'eye-off' : 'eye'}"></i>
                </button>
            `;
            controls.style.cssText = 'position:absolute;top:10px;right:10px;display:flex;gap:6px;z-index:10;';
            controls.querySelector('.drag-handle').style.cssText = 'cursor:grab;color:var(--text-dim);display:flex;align-items:center;';
            controls.querySelector('.visibility-toggle').style.cssText = 'background:none;border:1px solid var(--border);color:var(--text-dim);width:30px;height:30px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;';
            w.style.position = 'relative';
            w.prepend(controls);
        }
        controls.style.display = 'flex';

        // Show hidden widgets with reduced opacity
        if (w.dataset.hidden === 'true') {
            w.style.display = '';
            w.style.opacity = '0.4';
        }
        
        // Add border for editing mode
        w.style.outline = '2px dashed var(--border)';
        w.style.outlineOffset = '4px';

        w.addEventListener('dragstart', handleDragStart);
        w.addEventListener('dragover', handleDragOver);
        w.addEventListener('drop', handleDrop);
        w.addEventListener('dragend', handleDragEnd);
    });
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function disableDragAndDrop(container) {
    const widgets = container.querySelectorAll('[data-widget-id]');
    widgets.forEach(w => {
        w.setAttribute('draggable', 'false');
        const controls = w.querySelector('.widget-controls');
        if (controls) controls.style.display = 'none';
        
        // Re-hide hidden widgets
        if (w.dataset.hidden === 'true') {
            w.style.display = 'none';
        }
        w.style.opacity = '';
        w.style.outline = '';
        w.style.outlineOffset = '';

        w.removeEventListener('dragstart', handleDragStart);
        w.removeEventListener('dragover', handleDragOver);
        w.removeEventListener('drop', handleDrop);
        w.removeEventListener('dragend', handleDragEnd);
    });
}

let dragSrcEl = null;

function handleDragStart(e) {
    dragSrcEl = this;
    this.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.dataset.widgetId);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    this.style.outline = '2px solid var(--primary)';
    this.style.outlineOffset = '4px';
}

function handleDrop(e) {
    e.preventDefault();
    if (dragSrcEl !== this) {
        const container = this.parentNode;
        const allWidgets = Array.from(container.querySelectorAll('[data-widget-id]'));
        const fromIndex = allWidgets.indexOf(dragSrcEl);
        const toIndex = allWidgets.indexOf(this);
        
        if (fromIndex < toIndex) {
            container.insertBefore(dragSrcEl, this.nextSibling);
        } else {
            container.insertBefore(dragSrcEl, this);
        }
    }
    this.style.outline = '2px dashed var(--border)';
}

function handleDragEnd() {
    this.style.opacity = this.dataset.hidden === 'true' ? '0.4' : '';
    const container = document.getElementById('widgets-container');
    container.querySelectorAll('[data-widget-id]').forEach(w => {
        w.style.outline = '2px dashed var(--border)';
        w.style.outlineOffset = '4px';
    });
}

function toggleWidgetVisibility(btn) {
    const widget = btn.closest('[data-widget-id]');
    const isHidden = widget.dataset.hidden === 'true';
    
    if (isHidden) {
        widget.dataset.hidden = 'false';
        widget.style.opacity = '';
        btn.innerHTML = '<i data-lucide="eye"></i>';
    } else {
        widget.dataset.hidden = 'true';
        widget.style.opacity = '0.4';
        btn.innerHTML = '<i data-lucide="eye-off"></i>';
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function saveDashboardLayout(layout) {
    // Save to localStorage immediately
    localStorage.setItem('dashboard_layout', JSON.stringify(layout));
    
    // Attempt to save to backend
    fetch('/api/dashboard/layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layout: JSON.stringify(layout) })
    }).then(res => res.json())
      .then(data => console.log('Layout saved to DB:', data))
      .catch(err => console.error('Failed to save layout to DB:', err));
}

async function loadDashboardLayout() {
    const container = document.getElementById('widgets-container');
    if (!container) return;

    let layout = null;

    // Try DB first
    try {
        const res = await fetch('/api/dashboard/layout');
        const data = await res.json();
        if (data.layout && data.layout !== '{}') {
            layout = JSON.parse(data.layout);
        }
    } catch (err) {
        console.error('Failed to load layout from DB:', err);
    }

    // Fallback to localStorage
    if (!layout) {
        const saved = localStorage.getItem('dashboard_layout');
        if (saved) layout = JSON.parse(saved);
    }

    if (layout) {
        // Apply layout: reorder and hide
        const widgets = Array.from(container.querySelectorAll('[data-widget-id]'));
        layout.forEach(item => {
            const w = widgets.find(w => w.dataset.widgetId === item.id);
            if (w) {
                w.dataset.hidden = item.hidden ? 'true' : 'false';
                w.style.display = item.hidden ? 'none' : '';
                container.appendChild(w);
            }
        });
    }
}

// Auto-init on load
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initMobileSidebar();
    if (document.getElementById('widgets-container')) {
        initDashboardCustomization();
        loadDashboardLayout();
    }
});
