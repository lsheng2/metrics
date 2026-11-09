/*
 * Meridian shell behaviour: theme preference, collapsible sidebar rail, mobile navigation drawer,
 * breadcrumb sync after htmx navigation and popovers. window.DashboardShell is the only way other
 * scripts (command-palette.js) change shell state. Page features live in the FEATURE_SCRIPTS
 * modules registered in ui_web/static_assets.py; chart theming lives in charts.js.
 */
(function () {
    'use strict';

    const THEME_STORAGE_KEY = 'dashboard-theme';
    const SIDEBAR_STORAGE_KEY = 'metricsDashboard.sidebarCollapsed';
    const THEME_PREFERENCES = ['light', 'dark', 'system'];
    const APP_TITLE = 'Metrics';
    const root = document.documentElement;
    const darkQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    const drawerQuery = window.matchMedia ? window.matchMedia('(max-width: 768px)') : null;

    function readStorage(key) {
        try {
            return window.localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function writeStorage(key, value) {
        try {
            if (value === null) {
                window.localStorage.removeItem(key);
            } else {
                window.localStorage.setItem(key, value);
            }
        } catch (error) {
            // Storage may be unavailable (private mode, quota); the in-page state still applies.
        }
    }

    /* ------------------------------------------------------------------ theme */

    function storedThemePreference() {
        const stored = readStorage(THEME_STORAGE_KEY);
        return THEME_PREFERENCES.includes(stored) ? stored : 'system';
    }

    function resolveTheme(preference) {
        if (preference === 'light' || preference === 'dark') {
            return preference;
        }
        return darkQuery && darkQuery.matches ? 'dark' : 'light';
    }

    function syncThemeControls(preference) {
        const systemTheme = resolveTheme('system');
        document.querySelectorAll('[data-theme-choice]').forEach(option => {
            const selected = option.dataset.themeChoice === preference;
            option.setAttribute('aria-checked', String(selected));
            option.tabIndex = selected ? 0 : -1;
            // "System" follows the OS app appearance, not the clock; say which one it detects.
            const hint = systemTheme === 'dark' ? option.dataset.themeHintDark : option.dataset.themeHintLight;
            if (hint) {
                option.title = hint;
            }
        });
    }

    function applyTheme(preference, persist) {
        const normalized = THEME_PREFERENCES.includes(preference) ? preference : 'system';
        const resolved = resolveTheme(normalized);
        const switching = root.dataset.theme !== resolved;
        if (switching) {
            root.dataset.themeSwitching = '';
        }
        root.dataset.theme = resolved;
        root.dataset.themePreference = normalized;
        if (persist) {
            writeStorage(THEME_STORAGE_KEY, normalized);
        }
        syncThemeControls(normalized);
        if (switching) {
            // Flush styles while transitions are suspended so every surface flips in one frame.
            window.getComputedStyle(root).getPropertyValue('color');
            window.setTimeout(() => delete root.dataset.themeSwitching, 0);
            document.dispatchEvent(new CustomEvent('dashboard:themechange', {
                detail: { theme: resolved, preference: normalized },
            }));
        }
    }

    function initThemeSwitch() {
        applyTheme(storedThemePreference(), false);
        document.addEventListener('click', event => {
            const option = event.target.closest('[data-theme-choice]');
            if (option) {
                applyTheme(option.dataset.themeChoice, true);
            }
        });
        document.querySelectorAll('[data-theme-switch]').forEach(group => {
            group.addEventListener('keydown', event => {
                const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
                if (!step) {
                    return;
                }
                event.preventDefault();
                const options = Array.from(group.querySelectorAll('[data-theme-choice]'));
                const current = Math.max(0, options.indexOf(document.activeElement));
                const next = options[(current + step + options.length) % options.length];
                applyTheme(next.dataset.themeChoice, true);
                next.focus();
            });
        });
        if (darkQuery) {
            darkQuery.addEventListener('change', () => {
                applyTheme(root.dataset.themePreference, false);
            });
        }
        window.addEventListener('storage', event => {
            if (event.key === THEME_STORAGE_KEY) {
                applyTheme(storedThemePreference(), false);
            }
        });
    }

    /* --------------------------------------------------------- sidebar rail */

    function isSidebarCollapsed() {
        return root.dataset.sidebar === 'collapsed';
    }

    function syncCollapseControls() {
        const expanded = String(!isSidebarCollapsed());
        document.querySelectorAll('[data-shell-collapse]').forEach(button => {
            button.setAttribute('aria-expanded', expanded);
        });
    }

    function setSidebarCollapsed(collapsed) {
        if (collapsed) {
            root.dataset.sidebar = 'collapsed';
        } else {
            delete root.dataset.sidebar;
        }
        writeStorage(SIDEBAR_STORAGE_KEY, collapsed ? 'true' : null);
        syncCollapseControls();
    }

    function initSidebarCollapse() {
        syncCollapseControls();
        document.querySelectorAll('[data-shell-collapse]').forEach(button => {
            button.addEventListener('click', () => setSidebarCollapsed(!isSidebarCollapsed()));
        });
        document.addEventListener('keydown', event => {
            if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key === '\\') {
                event.preventDefault();
                setSidebarCollapsed(!isSidebarCollapsed());
            }
        });
    }

    /* --------------------------------------------------------- mobile drawer */

    const drawer = {
        sidebar: null,
        main: null,
        scrim: null,
        openers: [],
        returnFocus: null,
    };

    function isDrawerOpen() {
        return root.dataset.drawer === 'open';
    }

    function setDrawerOpen(open, restoreFocus) {
        if (!drawer.sidebar || open === isDrawerOpen()) {
            return;
        }
        if (open) {
            drawer.returnFocus = document.activeElement;
            root.dataset.drawer = 'open';
        } else if (drawerQuery && drawerQuery.matches) {
            // "closing" keeps the slide-out transition alive; the resting state has none (shell/responsive.css).
            root.dataset.drawer = 'closing';
            const seconds = parseFloat(getComputedStyle(drawer.sidebar).transitionDuration) || 0;
            window.setTimeout(() => {
                if (root.dataset.drawer === 'closing') {
                    delete root.dataset.drawer;
                }
            }, seconds * 1000 + 50);
        } else {
            delete root.dataset.drawer;
        }
        if (drawer.scrim) {
            drawer.scrim.hidden = !open;
        }
        if (drawer.main) {
            drawer.main.inert = open;
        }
        drawer.openers.forEach(button => button.setAttribute('aria-expanded', String(open)));
        if (open) {
            const target = drawer.sidebar.querySelector('.app-nav a.is-active') || drawer.sidebar.querySelector('a[href], button');
            if (target) {
                target.focus({ preventScroll: true });
            }
        } else if (restoreFocus && drawer.returnFocus && typeof drawer.returnFocus.focus === 'function') {
            drawer.returnFocus.focus({ preventScroll: true });
        }
    }

    function initDrawer() {
        drawer.sidebar = document.getElementById('app-sidebar');
        drawer.main = document.querySelector('.app-main');
        drawer.scrim = document.querySelector('[data-shell-scrim]');
        drawer.openers = Array.from(document.querySelectorAll('[data-shell-drawer-open]'));
        if (!drawer.sidebar || drawer.openers.length === 0) {
            return;
        }
        drawer.openers.forEach(button => {
            button.addEventListener('click', () => setDrawerOpen(!isDrawerOpen(), true));
        });
        if (drawer.scrim) {
            drawer.scrim.addEventListener('click', () => setDrawerOpen(false, true));
        }
        drawer.sidebar.addEventListener('click', event => {
            if (isDrawerOpen() && event.target.closest('a[href]')) {
                setDrawerOpen(false, false);
            }
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && isDrawerOpen()) {
                setDrawerOpen(false, true);
            }
        });
        if (drawerQuery) {
            drawerQuery.addEventListener('change', event => {
                if (!event.matches) {
                    setDrawerOpen(false, false);
                }
            });
        }
    }

    /* ------------------------------------------- navigation state after swaps */

    function activeNavigationLink() {
        return document.querySelector('.app-nav__submenu a.is-active') || document.querySelector('.app-nav a.is-active');
    }

    function syncNavigationState() {
        const active = activeNavigationLink();
        document.querySelectorAll('.app-nav a[aria-current]').forEach(link => {
            if (link !== active) {
                link.removeAttribute('aria-current');
            }
        });
        if (!active) {
            return;
        }
        active.setAttribute('aria-current', 'page');
        const label = active.dataset.navLabel || active.textContent.trim();
        const groupLabel = active.dataset.navGroupLabel || '';
        const page = document.querySelector('[data-shell-crumb-page]');
        const trail = document.querySelector('[data-shell-crumb-trail]');
        if (page) {
            page.textContent = label;
        }
        if (trail) {
            // Sidebar swaps always land on a top-level destination, so any page-specific
            // ancestor trail from the previous full render no longer applies.
            const group = document.createElement('span');
            group.className = 'app-crumbs__group';
            group.textContent = groupLabel;
            trail.replaceChildren(...(groupLabel ? [group] : []));
        }
        document.title = `${label} · ${APP_TITLE}`;
    }

    function initNavigationSync() {
        document.body.addEventListener('htmx:afterSettle', event => {
            const target = event.detail && event.detail.target;
            if (target && target.id === 'main-content') {
                syncNavigationState();
            }
        });
    }

    /* ------------------------------------------------------------- popovers */

    function closePopovers(except, restoreFocus) {
        document.querySelectorAll('details.popover[open]').forEach(popover => {
            if (popover === except) {
                return;
            }
            const hadFocus = popover.contains(document.activeElement);
            popover.open = false;
            if (restoreFocus && hadFocus) {
                popover.querySelector('summary').focus();
            }
        });
    }

    function initPopovers() {
        document.addEventListener('click', event => {
            closePopovers(event.target.closest('details.popover'), false);
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                closePopovers(null, true);
            }
        });
    }

    function init() {
        initThemeSwitch();
        initSidebarCollapse();
        initDrawer();
        initNavigationSync();
        initPopovers();
    }

    window.DashboardShell = {
        applyTheme(preference) {
            applyTheme(preference, true);
        },
        setSidebarCollapsed,
        closeDrawer() {
            setDrawerOpen(false, false);
        },
        // The sidebar shortcut opens the drawer on narrow screens and collapses the rail otherwise.
        toggleNavigation() {
            if (drawerQuery && drawerQuery.matches) {
                setDrawerOpen(!isDrawerOpen(), true);
            } else {
                setSidebarCollapsed(!isSidebarCollapsed());
            }
        },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
