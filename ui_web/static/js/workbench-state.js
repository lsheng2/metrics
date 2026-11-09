/*
 * Workbench state: remembers the last meaningful /workbench/ URL for the sidebar link,
 * refreshes the shell from toolbar and scope changes, answers AI Base host actions and
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

    function workbenchAiBaseOrigin() {
        const contextNode = document.getElementById('workbench-ai-context');
        if (!contextNode) {
            return '';
        }
        try {
            const context = JSON.parse(contextNode.textContent || '{}');
            const frontendUrl = context.ai_base && context.ai_base.frontend_url;
            return frontendUrl ? new URL(frontendUrl, window.location.origin).origin : '';
        } catch (error) {
            return '';
        }
    }

    function workbenchUrlFromHostAction(request) {
        const payload = request && request.payload ? request.payload : {};
        const explicitUrl = payload.workbenchUrl || request.fallbackUrl;
        const normalizedExplicitUrl = explicitUrl ? normalizedWorkbenchUrl(explicitUrl) : '';
        if (normalizedExplicitUrl) {
            return normalizedExplicitUrl;
        }
        const params = new URLSearchParams(window.location.search);
        ['chartId', 'panelId', 'dashboardUid'].forEach(key => {
            if (!payload[key]) {
                return;
            }
            const queryKey = key === 'chartId'
                ? 'chart_id'
                : key === 'panelId'
                    ? 'panel_id'
                    : 'dashboard_uid';
            params.set(queryKey, String(payload[key]));
        });
        return `${window.location.pathname}?${params.toString()}`;
    }

    function acknowledgeHostAction(event, request, status, result) {
        if (!event.source || !request) {
            return;
        }
        event.source.postMessage({
            type: 'ai-base.host-action.result',
            result: {
                sourceAppId: request.sourceAppId,
                bindingKey: request.bindingKey,
                sessionId: request.sessionId,
                requestId: request.requestId,
                artifactId: request.artifactId || null,
                correlationId: request.correlationId,
                idempotencyKey: request.idempotencyKey,
                status: status,
                result: result,
            },
        }, event.origin);
    }

    function handleWorkbenchHostAction(event, payload) {
        const aiBaseOrigin = workbenchAiBaseOrigin();
        if (!aiBaseOrigin || event.origin !== aiBaseOrigin) {
            return false;
        }
        const request = payload.request || {};
        if (request.sourceAppId !== 'metrics-dashboard' || request.actionKind !== 'metrics.openGrafanaChart') {
            acknowledgeHostAction(event, request, 'rejected', { reason: 'unsupported_action' });
            return true;
        }
        const url = workbenchUrlFromHostAction(request);
        if (!isMeaningfulWorkbenchUrl(url)) {
            acknowledgeHostAction(event, request, 'failed', { reason: 'invalid_workbench_url' });
            return true;
        }
        if (window.htmx) {
            htmx.ajax('GET', url, {
                target: '.workbench-shell',
                select: '.workbench-shell',
                swap: 'outerHTML'
            });
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
            acknowledgeHostAction(event, request, 'handled', { openedIn: 'metrics-workbench.chart', url: url });
        } else {
            window.location.assign(url);
        }
        return true;
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
                swap: 'outerHTML'
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
            if (payload.type === 'ai-base.host-action.request') {
                handleWorkbenchHostAction(event, payload);
                return;
            }
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
                    swap: 'outerHTML'
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
