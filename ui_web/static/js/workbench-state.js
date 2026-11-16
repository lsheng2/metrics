/*
 * Workbench state: remembers the last meaningful /workbench/ URL for the sidebar link,
 * refreshes the shell from toolbar and scope changes, answers
 * Grafana selection messages, and closes workbench menus on outside click or Escape.
 */

document.addEventListener('DOMContentLoaded', function() {
    const workbenchLastUrlKey = 'metricsWorkbench.lastUrl';
    const workbenchStateParams = [
        'scope_id',
        'range_mode',
        'begin',
        'end',
        'chart_id',
        'chart_version',
        'run',
        'snapshot',
        'bucket',
        'series',
    ];

    function normalizedWorkbenchUrl(rawUrl) {
        try {
            const url = new URL(rawUrl, window.location.origin);
            if (url.origin !== window.location.origin || url.pathname !== '/workbench/' || !url.search) {
                return '';
            }
            return `${url.pathname}${url.search}`;
        } catch (error) {
            return '';
        }
    }

    function isMeaningfulWorkbenchUrl(rawUrl) {
        const normalizedUrl = normalizedWorkbenchUrl(rawUrl);
        if (!normalizedUrl) {
            return false;
        }
        const url = new URL(normalizedUrl, window.location.origin);
        return workbenchStateParams.some(param => Boolean(url.searchParams.get(param)));
    }

    function storedWorkbenchUrl() {
        try {
            const storedUrl = window.localStorage.getItem(workbenchLastUrlKey);
            return isMeaningfulWorkbenchUrl(storedUrl) ? normalizedWorkbenchUrl(storedUrl) : '';
        } catch (error) {
            return '';
        }
    }

    function updateWorkbenchNavigationLinks() {
        const restoredUrl = storedWorkbenchUrl();
        document.querySelectorAll('[data-workbench-nav-link]').forEach(link => {
            link.href = restoredUrl || '/workbench/';
        });
    }

    function saveCurrentWorkbenchUrl() {
        const currentUrl = `${window.location.pathname}${window.location.search}`;
        if (!isMeaningfulWorkbenchUrl(currentUrl)) {
            updateWorkbenchNavigationLinks();
            return;
        }
        try {
            window.localStorage.setItem(workbenchLastUrlKey, normalizedWorkbenchUrl(currentUrl));
        } catch (error) {
            return;
        }
        updateWorkbenchNavigationLinks();
    }

    function workbenchToolbarUrl(form) {
        const action = form.getAttribute('hx-get') || form.getAttribute('action') || window.location.pathname;
        const url = new URL(action, window.location.origin);
        const params = new URLSearchParams(new FormData(form));
        url.search = params.toString();
        return `${url.pathname}${url.search}`;
    }

    function refreshWorkbenchFromToolbar(form) {
        const url = workbenchToolbarUrl(form);
        if (window.htmx) {
            htmx.ajax('GET', url, {
                target: '.workbench-shell',
                select: '.workbench-shell',
                swap: 'outerHTML ignoreTitle:true'
            });
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
            return;
        }
        window.location.assign(url);
    }

    function closeWorkbenchMenus(exceptMenu) {
        document.querySelectorAll('.workbench-menu[open]').forEach(menu => {
            if (menu !== exceptMenu) {
                menu.open = false;
            }
        });
    }

    function initializeDismissibleWorkbenchMenus() {
        if (document.body.dataset.workbenchMenuDismissInitialized === 'true') {
            return;
        }
        document.body.dataset.workbenchMenuDismissInitialized = 'true';
        document.addEventListener('click', event => {
            const clickedMenu = event.target.closest('.workbench-menu');
            if (clickedMenu) {
                closeWorkbenchMenus(clickedMenu);
                return;
            }
            closeWorkbenchMenus(null);
        });
        document.addEventListener('keydown', event => {
            if (event.key !== 'Escape') {
                return;
            }
            closeWorkbenchMenus(null);
        });
    }

    function initializeWorkbenchScopeSelect() {
        const scopeSelect = document.querySelector('[data-workbench-state-trigger="scope"]');
        if (scopeSelect && scopeSelect.dataset.workbenchScopeSyncInitialized !== 'true') {
            scopeSelect.dataset.workbenchScopeSyncInitialized = 'true';
            scopeSelect.addEventListener('change', function() {
                const selected = this.selectedOptions && this.selectedOptions.length ? this.selectedOptions[0] : null;
                const profileId = selected ? selected.dataset.profileId || '' : '';
                const providerId = selected ? selected.dataset.providerId || '' : '';
                const profileField = document.getElementById('workbench-profile');
                const providerField = document.getElementById('workbench-provider');
                if (profileField && profileId) {
                    profileField.value = profileId;
                }
                if (providerField) {
                    providerField.value = providerId;
                }
                const toolbar = this.closest('form');
                if (toolbar) {
                    refreshWorkbenchFromToolbar(toolbar);
                }
            });
        }
    }

    function registerWorkbenchMessageHandler() {
        if (window.metricsWorkbenchMessageHandlerRegistered) {
            return;
        }
        window.metricsWorkbenchMessageHandlerRegistered = true;
        window.addEventListener('message', event => {
            const payload = event.data || {};
            if (event.origin !== window.location.origin) {
                return;
            }
            if (payload.type !== 'metrics-workbench:grafana-selection') {
                return;
            }
            const params = new URLSearchParams(window.location.search);
            Object.entries(payload).forEach(([key, value]) => {
                if (key === 'type') {
                    return;
                }
                if (value) {
                    params.set(key, value);
                }
            });
            const url = `${window.location.pathname}?${params.toString()}`;
            if (window.htmx) {
                htmx.ajax('GET', url, {
                    target: '.workbench-shell',
                    select: '.workbench-shell',
                    swap: 'outerHTML ignoreTitle:true'
                });
            } else {
                window.location.assign(url);
                return;
            }
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
        });
    }

    function initializeWorkbenchState() {
        updateWorkbenchNavigationLinks();
        if (document.querySelector('.workbench-shell')) {
            saveCurrentWorkbenchUrl();
        }
        initializeWorkbenchScopeSelect();
        registerWorkbenchMessageHandler();
    }

    initializeDismissibleWorkbenchMenus();
    initializeWorkbenchState();
    document.body.addEventListener('htmx:afterSwap', initializeWorkbenchState);
    document.body.addEventListener('htmx:pushedIntoHistory', saveCurrentWorkbenchUrl);
});
