function initializeTaskForecastToggles() {
    document.querySelectorAll('.task-toggle').forEach(button => {
        button.addEventListener('click', function() {
            const parentLevel = parseInt(this.getAttribute('data-parent-level'));
            const parentRow = this.closest('tr');
            const icon = this.querySelector('i[class*="iconoir"]');
            
            let currentRow = parentRow.nextElementSibling;
            const childRows = [];
            
            while (currentRow) {
                const rowLevel = parseInt(currentRow.getAttribute('data-level'));
                
                if (rowLevel <= parentLevel) {
                    break;
                }
                
                if (rowLevel > parentLevel) {
                    childRows.push(currentRow);
                }
                
                currentRow = currentRow.nextElementSibling;
            }
            
            const isExpanded = icon.classList.contains('iconoir-nav-arrow-down');
            
            childRows.forEach(row => {
                if (isExpanded) {
                    row.classList.add('is-hidden');
                    const childToggle = row.querySelector('.task-toggle i[class*="iconoir"]');
                    if (childToggle && childToggle.classList.contains('iconoir-nav-arrow-down')) {
                        childToggle.className = 'iconoir-nav-arrow-right';
                    }
                } else {
                    const rowLevel = parseInt(row.getAttribute('data-level'));
                    if (rowLevel === parentLevel + 1) {
                        row.classList.remove('is-hidden');
                    }
                }
            });
            
            if (icon) {
                icon.className = isExpanded ? 'iconoir-nav-arrow-right' : 'iconoir-nav-arrow-down';
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    
    function handleMenuToggle(e) {
        e.preventDefault();
        
        const targetId = this.getAttribute('data-target');
        const submenu = document.getElementById(targetId);
        
        if (submenu) {
            const isHidden = submenu.classList.contains('is-hidden');
            
            if (isHidden) {
                submenu.classList.remove('is-hidden');
                this.setAttribute('aria-expanded', 'true');
            } else {
                submenu.classList.add('is-hidden');
                this.setAttribute('aria-expanded', 'false');
            }
        }
    }
    
    function setActiveMenuItem(clickedElement) {
        if (!clickedElement || clickedElement.tagName !== 'A' || !clickedElement.closest('.menu-list')) {
            return;
        }
        
        document.querySelectorAll('.menu-list .is-active').forEach(item => {
            item.classList.remove('is-active');
        });
        
        clickedElement.classList.add('is-active');
        
        const parentSubmenu = clickedElement.closest('.menu-submenu');
        if (parentSubmenu) {
            parentSubmenu.classList.remove('is-hidden');
            
            const submenuId = parentSubmenu.getAttribute('id');
            const toggle = document.querySelector(`[data-target="${submenuId}"]`);
            if (toggle) {
                toggle.classList.add('is-active');
                toggle.setAttribute('aria-expanded', 'true');
            }
        }
    }
    
    function expandInitialActiveMenus() {
        const activeMenus = document.querySelectorAll('.menu-list .is-active');
        activeMenus.forEach(activeItem => {
            const parentSubmenu = activeItem.closest('.menu-submenu');
            if (parentSubmenu) {
                parentSubmenu.classList.remove('is-hidden');
                
                const submenuId = parentSubmenu.getAttribute('id');
                const toggle = document.querySelector(`[data-target="${submenuId}"]`);
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'true');
                }
            }
        });
    }

    function initializeDirtyForms() {
        document.querySelectorAll('[data-dirty-form]').forEach(form => {
            const banner = form.querySelector('[data-dirty-banner]');
            const fields = Array.from(form.querySelectorAll('input[name], textarea[name], select[name]'))
                .filter(field => field.type !== 'hidden' && field.type !== 'submit');

            fields.forEach(field => {
                field.dataset.initialValue = field.type === 'checkbox' ? String(field.checked) : field.value;
            });

            function markDirtyFields() {
                let formIsDirty = false;
                fields.forEach(field => {
                    const currentValue = field.type === 'checkbox' ? String(field.checked) : field.value;
                    const fieldIsDirty = currentValue !== field.dataset.initialValue;
                    formIsDirty = formIsDirty || fieldIsDirty;
                    const label = field.id ? form.querySelector(`label[for="${field.id}"]`) : null;
                    if (!label) {
                        return;
                    }
                    let marker = label.querySelector('[data-dirty-marker]');
                    if (fieldIsDirty && !marker) {
                        marker = document.createElement('span');
                        marker.className = 'tag is-warning is-light ml-2';
                        marker.dataset.dirtyMarker = 'true';
                        marker.textContent = 'Modified';
                        label.appendChild(marker);
                    }
                    if (!fieldIsDirty && marker) {
                        marker.remove();
                    }
                });
                if (banner) {
                    banner.classList.toggle('is-hidden', !formIsDirty);
                }
                form.dataset.dirty = String(formIsDirty);
            }

            fields.forEach(field => {
                field.addEventListener('input', markDirtyFields);
                field.addEventListener('change', markDirtyFields);
            });

            form.querySelectorAll('[data-dirty-guard]').forEach(link => {
                link.addEventListener('click', event => {
                    if (form.dataset.dirty === 'true' && !window.confirm('Discard unsaved changes?')) {
                        event.preventDefault();
                    }
                });
            });
        });
    }

    function initializeConfirmForms() {
        document.querySelectorAll('form[data-confirm]').forEach(form => {
            form.addEventListener('submit', event => {
                const message = form.dataset.confirm;
                if (message && !window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });
    }

    const workbenchLastUrlKey = 'metricsWorkbench.lastUrl';
    const workbenchStateParams = [
        'scope_id',
        'profile_id',
        'provider_id',
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
        ['profileId', 'providerId', 'chartId', 'panelId', 'dashboardUid'].forEach(key => {
            if (!payload[key]) {
                return;
            }
            const queryKey = key === 'profileId'
                ? 'profile_id'
                : key === 'providerId'
                    ? 'provider_id'
                    : key === 'chartId'
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

    function initializeDashboardSidebarSplitter() {
        const layout = document.querySelector('[data-dashboard-layout]');
        const sidebar = document.querySelector('[data-dashboard-sidebar]');
        const splitter = document.querySelector('[data-dashboard-sidebar-splitter]');
        if (!layout || !sidebar || !splitter || splitter.dataset.dashboardSidebarInitialized === 'true') {
            return;
        }
        splitter.dataset.dashboardSidebarInitialized = 'true';
        const storageKey = 'metricsDashboard.sidebarWidth';
        const minWidth = 168;
        const maxWidth = 360;

        function applySidebarWidth(width) {
            const next = Math.max(minWidth, Math.min(maxWidth, width));
            layout.style.setProperty('--dashboard-sidebar-width', `${next}px`);
            try {
                window.localStorage.setItem(storageKey, `${next}px`);
            } catch (error) {
                return;
            }
        }

        try {
            const savedWidth = parseInt(window.localStorage.getItem(storageKey));
            if (savedWidth) {
                applySidebarWidth(savedWidth);
            }
        } catch (error) {
            return;
        }

        splitter.addEventListener('dblclick', function() {
            layout.style.removeProperty('--dashboard-sidebar-width');
            try {
                window.localStorage.removeItem(storageKey);
            } catch (error) {
                return;
            }
        });
        splitter.addEventListener('keydown', function(event) {
            if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) {
                return;
            }
            event.preventDefault();
            const current = Math.round(sidebar.getBoundingClientRect().width) || 248;
            applySidebarWidth(current + (event.key === 'ArrowLeft' ? -16 : 16));
        });
        splitter.addEventListener('pointerdown', function(event) {
            event.preventDefault();
            const onPointerMove = moveEvent => {
                const layoutRect = layout.getBoundingClientRect();
                applySidebarWidth(Math.round(moveEvent.clientX - layoutRect.left));
            };
            const onPointerUp = () => {
                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
            };
            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', onPointerUp, { once: true });
        });
    }

    function initializeWorkbenchShell() {
        updateWorkbenchNavigationLinks();
        initializeDashboardSidebarSplitter();
        if (document.querySelector('.workbench-shell')) {
            saveCurrentWorkbenchUrl();
        }

        const workbenchGrid = document.getElementById('workbench-grid');
        if (workbenchGrid && workbenchGrid.dataset.workbenchLayoutInitialized !== 'true') {
            workbenchGrid.dataset.workbenchLayoutInitialized = 'true';
            const savedAiWidth = window.localStorage.getItem('metricsWorkbench.aiWidth');
            const savedChartHeight = window.localStorage.getItem('metricsWorkbench.chartHeight');
            if (savedAiWidth) {
                workbenchGrid.style.setProperty('--workbench-ai-width', savedAiWidth);
                workbenchGrid.classList.toggle('is-ai-collapsed', savedAiWidth === '44px');
            }
            if (savedChartHeight) {
                workbenchGrid.style.setProperty('--workbench-chart-height', savedChartHeight);
                workbenchGrid.classList.toggle('is-chart-collapsed', savedChartHeight === '3.15rem');
            }
        }

        if (document.querySelector('.workbench-shell') && !window.metricsWorkbenchInitialScrollGuardRegistered) {
            window.metricsWorkbenchInitialScrollGuardRegistered = true;
            let userMovedViewport = false;
            ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(eventName => {
                window.addEventListener(eventName, function() {
                    userMovedViewport = true;
                }, { once: true, passive: true });
            });
            [0, 250, 750, 1500, 3000].forEach(delay => {
                window.setTimeout(function() {
                    if (!userMovedViewport && window.scrollY > 8 && window.scrollY < 480) {
                        window.scrollTo(window.scrollX, 0);
                    }
                }, delay);
            });
        }

        document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
            if (frame.dataset.workbenchScrollGuardInitialized === 'true') {
                return;
            }
            frame.dataset.workbenchScrollGuardInitialized = 'true';
            const initialScrollY = window.scrollY;
            frame.addEventListener('load', function() {
                frame.dataset.workbenchAiLoaded = 'true';
                if (initialScrollY <= 8 && window.scrollY > 8 && window.scrollY < 480) {
                    window.scrollTo(window.scrollX, initialScrollY);
                }
            });
        });

        document.querySelectorAll('[data-workbench-splitter]').forEach(splitter => {
            if (splitter.dataset.workbenchInitialized === 'true') {
                return;
            }
            splitter.dataset.workbenchInitialized = 'true';
            splitter.addEventListener('dblclick', function() {
                if (this.dataset.workbenchSplitter === 'main-ai' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-ai-width');
                    workbenchGrid.classList.remove('is-ai-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.aiWidth');
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-chart-height');
                    workbenchGrid.classList.remove('is-chart-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.chartHeight');
                }
            });
            splitter.addEventListener('keydown', function(event) {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
                    return;
                }
                event.preventDefault();
                if (!workbenchGrid) {
                    return;
                }
                const gridRect = workbenchGrid.getBoundingClientRect();
                if (this.dataset.workbenchSplitter === 'main-ai') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-ai-width')) || 340;
                    const delta = event.key === 'ArrowLeft' ? 16 : event.key === 'ArrowRight' ? -16 : 0;
                    const next = Math.max(44, Math.min(600, current + delta));
                    workbenchGrid.style.setProperty('--workbench-ai-width', `${next}px`);
                    workbenchGrid.classList.toggle('is-ai-collapsed', next <= 44);
                    window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-chart-height')) || Math.round(gridRect.height * 0.55);
                    const delta = event.key === 'ArrowUp' ? -16 : event.key === 'ArrowDown' ? 16 : 0;
                    const next = Math.max(50, Math.min(gridRect.height - 240, current + delta));
                    workbenchGrid.style.setProperty('--workbench-chart-height', `${next}px`);
                    workbenchGrid.classList.toggle('is-chart-collapsed', next <= 52);
                    window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                }
            });
            splitter.addEventListener('pointerdown', function(event) {
                if (!workbenchGrid) {
                    return;
                }
                event.preventDefault();
                const splitterKind = this.dataset.workbenchSplitter;
                const gridRect = workbenchGrid.getBoundingClientRect();
                const evidenceLayout = this.closest('[data-workbench-evidence-layout]');
                const evidenceRect = evidenceLayout ? evidenceLayout.getBoundingClientRect() : null;
                const onPointerMove = moveEvent => {
                    if (splitterKind === 'main-ai') {
                        const next = Math.max(44, Math.min(600, Math.round(gridRect.right - moveEvent.clientX)));
                        workbenchGrid.style.setProperty('--workbench-ai-width', `${next}px`);
                        workbenchGrid.classList.toggle('is-ai-collapsed', next <= 44);
                        window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                    }
                    if (splitterKind === 'chart-evidence') {
                        const next = Math.max(50, Math.min(gridRect.height - 240, Math.round(moveEvent.clientY - gridRect.top)));
                        workbenchGrid.style.setProperty('--workbench-chart-height', `${next}px`);
                        workbenchGrid.classList.toggle('is-chart-collapsed', next <= 52);
                        window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                    }
                    if (splitterKind === 'ticket-detail' && evidenceLayout && evidenceRect) {
                        const next = Math.max(180, Math.min(360, Math.round(evidenceRect.right - moveEvent.clientX)));
                        evidenceLayout.style.setProperty('--workbench-ticket-detail-width', `${next}px`);
                    }
                };
                const onPointerUp = () => {
                    window.removeEventListener('pointermove', onPointerMove);
                    window.removeEventListener('pointerup', onPointerUp);
                };
                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp, { once: true });
            });
        });

        document.querySelectorAll('[data-workbench-collapse]').forEach(button => {
            if (button.dataset.workbenchInitialized === 'true') {
                return;
            }
            button.dataset.workbenchInitialized = 'true';
            button.addEventListener('click', function() {
                const pane = document.querySelector(`[data-workbench-pane="${this.dataset.workbenchCollapse}"]`);
                if (!pane) {
                    return;
                }
                const isCollapsed = pane.classList.toggle('is-collapsed');
                if (workbenchGrid && this.dataset.workbenchCollapse === 'ai-assistant') {
                    workbenchGrid.classList.toggle('is-ai-collapsed', isCollapsed);
                    workbenchGrid.style.setProperty('--workbench-ai-width', isCollapsed ? '44px' : '340px');
                    window.localStorage.setItem('metricsWorkbench.aiWidth', isCollapsed ? '44px' : '340px');
                }
                if (workbenchGrid && this.dataset.workbenchCollapse === 'chart') {
                    workbenchGrid.classList.toggle('is-chart-collapsed', isCollapsed);
                    workbenchGrid.style.setProperty('--workbench-chart-height', isCollapsed ? '3.15rem' : '42vh');
                    window.localStorage.setItem('metricsWorkbench.chartHeight', isCollapsed ? '3.15rem' : '42vh');
                }
                this.setAttribute('aria-expanded', String(!isCollapsed));
                this.textContent = isCollapsed ? 'Expand' : 'Collapse';
            });
        });

        const scopeSelect = document.getElementById('workbench-scope');
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
            });
        }

        document.querySelectorAll('[data-workbench-evidence-workspace]').forEach(workspace => {
            if (workspace.dataset.workbenchInitialized === 'true') {
                return;
            }
            workspace.dataset.workbenchInitialized = 'true';
            const table = workspace.querySelector('[data-workbench-evidence-table]');
            const selectedCount = workspace.querySelector('[data-workbench-ticket-selected-count]');
            const selectAll = workspace.querySelector('[data-workbench-ticket-select-all]');
            const ticketBoxes = Array.from(workspace.querySelectorAll('[data-workbench-ticket-checkbox]'));
            const detail = workspace.querySelector('[data-workbench-ticket-detail]');
            const detailEmpty = workspace.querySelector('[data-ticket-detail-empty]');
            const detailContent = workspace.querySelector('[data-ticket-detail-content]');
            const layout = workspace.querySelector('[data-workbench-evidence-layout]');
            function setDetailText(selector, value) {
                const node = workspace.querySelector(selector);
                if (node) {
                    node.textContent = value || '-';
                }
            }
            function openDetail() {
                if (layout) {
                    layout.classList.remove('is-detail-collapsed');
                }
                if (detailEmpty) {
                    detailEmpty.classList.add('is-hidden');
                }
                if (detailContent) {
                    detailContent.classList.remove('is-hidden');
                }
            }
            function selectedTicketPayloads() {
                return ticketBoxes
                    .filter(box => box.checked)
                    .map(box => box.closest('[data-workbench-ticket-row]'))
                    .filter(row => row)
                    .map(row => ({
                        issueKey: row.dataset.issueKey || '',
                        summary: row.dataset.summary || '',
                        series: row.dataset.series || '',
                        status: row.dataset.status || '',
                        severity: row.dataset.severity || '',
                        owner: row.dataset.owner || '',
                        component: row.dataset.component || '',
                        created: row.dataset.created || '',
                        updated: row.dataset.updated || '',
                    }));
            }
            function notifyAiSelectedTickets() {
                const selectedTickets = selectedTicketPayloads();
                const payload = {
                    selectedTicketCount: selectedTickets.length,
                    truncated: selectedTickets.length > 50,
                    tickets: selectedTickets.slice(0, 50),
                };
                window.metricsWorkbenchSelectedTickets = payload;
                document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
                    if (!frame.contentWindow || !frame.src) {
                        return;
                    }
                    if (frame.dataset.workbenchAiLoaded !== 'true') {
                        return;
                    }
                    let targetOrigin = window.location.origin;
                    try {
                        targetOrigin = new URL(frame.src).origin;
                    } catch (error) {
                        targetOrigin = window.location.origin;
                    }
                    frame.contentWindow.postMessage({
                        type: 'metrics-workbench:selected-tickets',
                        source: 'metrics-workbench',
                        selectedTicketCount: payload.selectedTicketCount,
                        truncated: payload.truncated,
                        selectedTickets: payload.tickets,
                    }, targetOrigin);
                });
            }
            document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
                if (frame.dataset.workbenchTicketNotifyInitialized === 'true') {
                    return;
                }
                frame.dataset.workbenchTicketNotifyInitialized = 'true';
                frame.addEventListener('load', notifyAiSelectedTickets);
            });
            function updateSelectedCount() {
                const count = ticketBoxes.filter(box => box.checked).length;
                if (selectedCount) {
                    selectedCount.textContent = `${count} selected`;
                }
                if (selectAll) {
                    selectAll.checked = count > 0 && count === ticketBoxes.length;
                    selectAll.indeterminate = count > 0 && count < ticketBoxes.length;
                }
                notifyAiSelectedTickets();
            }
            if (selectAll) {
                selectAll.addEventListener('change', function() {
                    ticketBoxes.forEach(box => {
                        box.checked = this.checked;
                    });
                    updateSelectedCount();
                });
            }
            ticketBoxes.forEach(box => {
                box.addEventListener('change', updateSelectedCount);
            });
            workspace.querySelectorAll('[data-workbench-column-toggle]').forEach(toggle => {
                toggle.addEventListener('change', function() {
                    const field = this.dataset.workbenchColumnToggle;
                    workspace.querySelectorAll(`[data-workbench-field="${field}"]`).forEach(cell => {
                        cell.classList.toggle('is-hidden', !this.checked);
                    });
                });
            });
            const sortButton = workspace.querySelector('[data-workbench-evidence-sort]');
            if (sortButton && table) {
                sortButton.addEventListener('click', function() {
                    const field = workspace.querySelector('[data-workbench-evidence-sort-field]')?.value || 'severity';
                    const direction = workspace.querySelector('[data-workbench-evidence-sort-direction]')?.value || 'desc';
                    const tbody = table.querySelector('tbody');
                    Array.from(tbody.querySelectorAll('[data-workbench-ticket-row]'))
                        .sort((left, right) => {
                            const leftValue = left.dataset[field] || '';
                            const rightValue = right.dataset[field] || '';
                            const result = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: 'base' });
                            return direction === 'asc' ? result : -result;
                        })
                        .forEach(row => tbody.appendChild(row));
                });
            }
            const bulkButton = workspace.querySelector('[data-workbench-ticket-bulk]');
            if (bulkButton) {
                bulkButton.addEventListener('click', function() {
                    const selectedTickets = selectedTicketPayloads();
                    if (selectedTickets.length === 0) {
                        return;
                    }
                    openDetail();
                    setDetailText('[data-ticket-detail-issue]', `${selectedTickets.length} selected tickets`);
                    const visibleIssueKeys = selectedTickets.slice(0, 12).map(ticket => ticket.issueKey);
                    const hiddenCount = selectedTickets.length - visibleIssueKeys.length;
                    const summary = hiddenCount > 0
                        ? `${visibleIssueKeys.join(', ')} +${hiddenCount} more`
                        : visibleIssueKeys.join(', ');
                    setDetailText('[data-ticket-detail-summary]', summary);
                    setDetailText('[data-ticket-detail-status]', 'mixed');
                    setDetailText('[data-ticket-detail-severity]', 'mixed');
                    setDetailText('[data-ticket-detail-owner]', 'mixed');
                    setDetailText('[data-ticket-detail-component]', 'mixed');
                    setDetailText('[data-ticket-detail-created]', '-');
                    setDetailText('[data-ticket-detail-updated]', '-');
                });
            }
            workspace.querySelectorAll('[data-workbench-ticket-row]').forEach(row => {
                row.addEventListener('click', function(event) {
                    if (event.target.closest('a, button, input, select, textarea')) {
                        return;
                    }
                    workspace.querySelectorAll('[data-workbench-ticket-row]').forEach(candidate => {
                        candidate.classList.remove('is-active');
                    });
                    this.classList.add('is-active');
                    openDetail();
                    setDetailText('[data-ticket-detail-issue]', this.dataset.issueKey);
                    setDetailText('[data-ticket-detail-summary]', this.dataset.summary);
                    setDetailText('[data-ticket-detail-status]', this.dataset.status);
                    setDetailText('[data-ticket-detail-severity]', this.dataset.severity);
                    setDetailText('[data-ticket-detail-owner]', this.dataset.owner);
                    setDetailText('[data-ticket-detail-component]', this.dataset.component);
                    setDetailText('[data-ticket-detail-created]', this.dataset.created);
                    setDetailText('[data-ticket-detail-updated]', this.dataset.updated);
                    const sourceLink = workspace.querySelector('[data-ticket-detail-source]');
                    if (sourceLink) {
                        sourceLink.href = this.dataset.sourceUrl || '#';
                        sourceLink.classList.toggle('is-disabled', !this.dataset.sourceUrl);
                    }
                });
            });
            workspace.querySelectorAll('[data-workbench-ticket-detail-close]').forEach(button => {
                button.addEventListener('click', function() {
                    if (layout) {
                        layout.classList.add('is-detail-collapsed');
                    }
                });
            });
            updateSelectedCount();
        });

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
    
    let activeRequestCount = 0;

    function showLoadingIndicator() {
        activeRequestCount += 1;
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.remove('is-hidden');
        }
    }

    function hideLoadingIndicator() {
        activeRequestCount = Math.max(0, activeRequestCount - 1);
        if (activeRequestCount > 0) {
            return;
        }
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.add('is-hidden');
        }
    }

    function showErrorNotification(url, statusCode, statusText) {
        const container = document.getElementById('notification-container');
        if (!container) {
            return;
        }

        const message = statusCode
            ? `${statusCode} ${statusText}: ${url}`
            : `Network Error: ${url}`;

        const hint = statusCode === 503
            ? '<p>Request could be blocked by WAF due to long execution time. Retry.</p>'
            : '';

        const notificationHtml = `
            <div class="notification is-danger is-light">
                <button class="delete"></button>
                <p><strong>${message}</strong></p>
                ${hint}
            </div>
        `;

        container.innerHTML = notificationHtml;

        const deleteButton = container.querySelector('.delete');
        if (deleteButton) {
            deleteButton.addEventListener('click', function() {
                container.innerHTML = '';
            });
        }
    }

    document.querySelectorAll('.menu-toggle').forEach(toggle => {
        toggle.addEventListener('click', handleMenuToggle);
    });
    expandInitialActiveMenus();
    initializeDirtyForms();
    initializeConfirmForms();
    initializeWorkbenchShell();
    
    document.querySelectorAll('.menu-list a').forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.hasAttribute('hx-get') || this.hasAttribute('hx-post')) {
                setActiveMenuItem(this);
            }
        });
    });
    
    document.querySelectorAll('details').forEach(details => {
        details.addEventListener('toggle', function() {
            const icon = this.querySelector('summary i[class*="iconoir"]');
            if (icon) {
                icon.className = this.open ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right';
            }
        });
    });
    
    document.body.addEventListener('htmx:beforeRequest', showLoadingIndicator);
    document.body.addEventListener('htmx:afterRequest', hideLoadingIndicator);
    document.body.addEventListener('htmx:afterSwap', function() {
        initializeWorkbenchShell();
        if (typeof window.initBugTrendChart === 'function') {
            window.initBugTrendChart();
        }
    });

    document.body.addEventListener('htmx:pushedIntoHistory', saveCurrentWorkbenchUrl);

    document.body.addEventListener('htmx:responseError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        const statusCode = event.detail.xhr.status;
        const statusText = event.detail.xhr.statusText;
        showErrorNotification(url, statusCode, statusText);
    });

    document.body.addEventListener('htmx:sendError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        showErrorNotification(url, null, null);
    });

    window.addEventListener('popstate', function() {
        const currentPath = window.location.pathname;
        const currentSearch = window.location.search;
        const currentUrl = currentPath + currentSearch;
        
        const matchingLink = document.querySelector(`.menu-list a[href="${currentUrl}"]`);
        if (matchingLink) {
            setActiveMenuItem(matchingLink);
        }
    });
});
