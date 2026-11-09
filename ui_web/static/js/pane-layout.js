/*
 * Resizable panes: the dashboard sidebar splitter and the workbench grid (AI rail width,
 * chart/evidence split, ticket-detail width, collapse buttons) persisted in localStorage,
 * plus the scroll guards that keep the workbench at the top while the AI iframe loads.
 */

document.addEventListener('DOMContentLoaded', function() {
    function syncSplitterValue(splitter, value, min, max) {
        if (!splitter) {
            return;
        }
        const now = Math.round(Math.max(min, Math.min(max, Number.isFinite(value) ? value : min)));
        splitter.setAttribute('aria-valuemin', String(min));
        splitter.setAttribute('aria-valuemax', String(max));
        splitter.setAttribute('aria-valuenow', String(now));
        splitter.setAttribute('aria-valuetext', `${now} pixels`);
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
            syncSplitterValue(splitter, next, minWidth, maxWidth);
            try {
                window.localStorage.setItem(storageKey, `${next}px`);
            } catch (error) {
                return;
            }
        }

        syncSplitterValue(splitter, sidebar.getBoundingClientRect().width, minWidth, maxWidth);
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
            syncSplitterValue(splitter, sidebar.getBoundingClientRect().width, minWidth, maxWidth);
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

    function initializeWorkbenchPanes() {
        const workbenchGrid = document.getElementById('workbench-grid');
        const aiRailWidth = 40;
        const minExpandedAiWidth = 280;
        const maxExpandedAiWidth = 600;
        const ticketDetailMinWidth = 180;
        const ticketDetailMaxWidth = 360;
        function syncWorkbenchAiSplitterValue(width) {
            syncSplitterValue(document.querySelector('[data-workbench-splitter="main-ai"]'), width, aiRailWidth, maxExpandedAiWidth);
        }
        function syncWorkbenchChartSplitterValue() {
            const splitter = document.querySelector('[data-workbench-splitter="chart-evidence"]');
            const chartPane = document.querySelector('[data-workbench-pane="chart"]');
            if (!workbenchGrid || !splitter || !chartPane) {
                return;
            }
            const maxHeight = Math.max(50, Math.round(workbenchGrid.getBoundingClientRect().height - 240));
            syncSplitterValue(splitter, chartPane.getBoundingClientRect().height, 50, maxHeight);
        }
        function currentTicketDetailWidth(splitter) {
            const evidenceLayout = splitter.closest('[data-workbench-evidence-layout]');
            const width = evidenceLayout
                ? Number.parseInt(getComputedStyle(evidenceLayout).getPropertyValue('--workbench-ticket-detail-width'))
                : 0;
            return width || 245;
        }
        function setTicketDetailWidth(splitter, width) {
            const evidenceLayout = splitter.closest('[data-workbench-evidence-layout]');
            const next = Math.max(ticketDetailMinWidth, Math.min(ticketDetailMaxWidth, Math.round(width)));
            if (evidenceLayout) {
                evidenceLayout.style.setProperty('--workbench-ticket-detail-width', `${next}px`);
            }
            syncSplitterValue(splitter, next, ticketDetailMinWidth, ticketDetailMaxWidth);
        }
        function normalizeWorkbenchAiWidth(width) {
            const numericWidth = Number.parseInt(width);
            if (!numericWidth || numericWidth <= aiRailWidth || numericWidth < minExpandedAiWidth) {
                return aiRailWidth;
            }
            return Math.min(maxExpandedAiWidth, numericWidth);
        }
        function syncWorkbenchCollapseState(paneName, isCollapsed) {
            const pane = document.querySelector(`[data-workbench-pane="${paneName}"]`);
            const button = document.querySelector(`[data-workbench-collapse="${paneName}"]`);
            if (pane) {
                pane.classList.toggle('is-collapsed', isCollapsed);
            }
            if (!button) {
                return;
            }
            button.setAttribute('aria-expanded', String(!isCollapsed));
            if (paneName === 'ai-assistant') {
                button.textContent = isCollapsed ? workbenchAiExpandLabel() : 'Collapse';
                button.setAttribute('aria-label', isCollapsed ? 'Expand AI assistant' : 'Collapse AI assistant');
                return;
            }
            button.textContent = isCollapsed ? 'Expand' : 'Collapse';
        }
        function setWorkbenchAiCollapsed(isCollapsed, width) {
            if (!workbenchGrid) {
                return;
            }
            const normalizedWidth = width
                ? normalizeWorkbenchAiWidth(width)
                : isCollapsed ? aiRailWidth : 340;
            const shouldCollapse = isCollapsed || normalizedWidth === aiRailWidth;
            workbenchGrid.classList.toggle('is-ai-collapsed', shouldCollapse);
            workbenchGrid.style.setProperty('--workbench-ai-width', `${normalizedWidth}px`);
            syncWorkbenchCollapseState('ai-assistant', shouldCollapse);
            syncWorkbenchAiSplitterValue(normalizedWidth);
        }
        function setWorkbenchChartCollapsed(isCollapsed, height) {
            if (!workbenchGrid) {
                return;
            }
            workbenchGrid.classList.toggle('is-chart-collapsed', isCollapsed);
            workbenchGrid.style.setProperty('--workbench-chart-height', height || (isCollapsed ? '3.15rem' : '38vh'));
            syncWorkbenchCollapseState('chart', isCollapsed);
            syncWorkbenchChartSplitterValue();
        }
        if (workbenchGrid && workbenchGrid.dataset.workbenchLayoutInitialized !== 'true') {
            workbenchGrid.dataset.workbenchLayoutInitialized = 'true';
            const savedAiWidth = window.localStorage.getItem('metricsWorkbench.aiWidth');
            const savedChartHeight = window.localStorage.getItem('metricsWorkbench.chartHeight');
            let aiCollapsed = false;
            let chartCollapsed = false;
            if (savedAiWidth) {
                const migratedAiWidth = savedAiWidth === '44px' ? '40px' : savedAiWidth;
                const normalizedAiWidth = normalizeWorkbenchAiWidth(migratedAiWidth);
                aiCollapsed = normalizedAiWidth === aiRailWidth;
                setWorkbenchAiCollapsed(aiCollapsed, `${normalizedAiWidth}px`);
                if (`${normalizedAiWidth}px` !== savedAiWidth) {
                    window.localStorage.setItem('metricsWorkbench.aiWidth', `${normalizedAiWidth}px`);
                }
            }
            if (savedChartHeight) {
                chartCollapsed = savedChartHeight === '3.15rem';
                setWorkbenchChartCollapsed(chartCollapsed, savedChartHeight);
            }
            syncWorkbenchCollapseState('ai-assistant', aiCollapsed);
            syncWorkbenchCollapseState('chart', chartCollapsed);
            syncWorkbenchAiSplitterValue(Number.parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-ai-width')) || 340);
            syncWorkbenchChartSplitterValue();
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
            if (splitter.dataset.workbenchSplitter === 'ticket-detail') {
                syncSplitterValue(splitter, currentTicketDetailWidth(splitter), ticketDetailMinWidth, ticketDetailMaxWidth);
            }
            splitter.addEventListener('dblclick', function() {
                if (this.dataset.workbenchSplitter === 'main-ai' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-ai-width');
                    workbenchGrid.classList.remove('is-ai-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.aiWidth');
                    syncWorkbenchAiSplitterValue(340);
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-chart-height');
                    workbenchGrid.classList.remove('is-chart-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.chartHeight');
                    syncWorkbenchChartSplitterValue();
                }
            });
            splitter.addEventListener('keydown', function(event) {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
                    return;
                }
                event.preventDefault();
                if (this.dataset.workbenchSplitter === 'ticket-detail') {
                    const delta = event.key === 'ArrowLeft' ? 16 : event.key === 'ArrowRight' ? -16 : 0;
                    setTicketDetailWidth(this, currentTicketDetailWidth(this) + delta);
                    return;
                }
                if (!workbenchGrid) {
                    return;
                }
                const gridRect = workbenchGrid.getBoundingClientRect();
                if (this.dataset.workbenchSplitter === 'main-ai') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-ai-width')) || 340;
                    const delta = event.key === 'ArrowLeft' ? 16 : event.key === 'ArrowRight' ? -16 : 0;
                    const candidate = current <= aiRailWidth && delta > 0 ? 340 : current + delta;
                    const next = normalizeWorkbenchAiWidth(candidate);
                    setWorkbenchAiCollapsed(next === aiRailWidth, `${next}px`);
                    window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-chart-height')) || Math.round(gridRect.height * 0.55);
                    const delta = event.key === 'ArrowUp' ? -16 : event.key === 'ArrowDown' ? 16 : 0;
                    const next = Math.max(50, Math.min(gridRect.height - 240, current + delta));
                    setWorkbenchChartCollapsed(next <= 52, `${next}px`);
                    window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                }
            });
            splitter.addEventListener('pointerdown', function(event) {
                const splitterKind = this.dataset.workbenchSplitter;
                const evidenceLayout = this.closest('[data-workbench-evidence-layout]');
                if (!workbenchGrid && !(splitterKind === 'ticket-detail' && evidenceLayout)) {
                    return;
                }
                event.preventDefault();
                const gridRect = workbenchGrid ? workbenchGrid.getBoundingClientRect() : null;
                const evidenceRect = evidenceLayout ? evidenceLayout.getBoundingClientRect() : null;
                const onPointerMove = moveEvent => {
                    if (splitterKind === 'main-ai' && gridRect) {
                        const next = normalizeWorkbenchAiWidth(Math.round(gridRect.right - moveEvent.clientX));
                        setWorkbenchAiCollapsed(next === aiRailWidth, `${next}px`);
                        window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                    }
                    if (splitterKind === 'chart-evidence' && gridRect) {
                        const next = Math.max(50, Math.min(gridRect.height - 240, Math.round(moveEvent.clientY - gridRect.top)));
                        setWorkbenchChartCollapsed(next <= 52, `${next}px`);
                        window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                    }
                    if (splitterKind === 'ticket-detail' && evidenceRect) {
                        setTicketDetailWidth(splitter, evidenceRect.right - moveEvent.clientX);
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
                const wasCollapsed = pane.classList.contains('is-collapsed')
                    || (workbenchGrid && this.dataset.workbenchCollapse === 'ai-assistant' && workbenchGrid.classList.contains('is-ai-collapsed'))
                    || (workbenchGrid && this.dataset.workbenchCollapse === 'chart' && workbenchGrid.classList.contains('is-chart-collapsed'));
                const isCollapsed = !wasCollapsed;
                if (workbenchGrid && this.dataset.workbenchCollapse === 'ai-assistant') {
                    setWorkbenchAiCollapsed(isCollapsed);
                    window.localStorage.setItem('metricsWorkbench.aiWidth', isCollapsed ? '40px' : '340px');
                }
                if (workbenchGrid && this.dataset.workbenchCollapse === 'chart') {
                    setWorkbenchChartCollapsed(isCollapsed);
                    window.localStorage.setItem('metricsWorkbench.chartHeight', isCollapsed ? '3.15rem' : '38vh');
                }
                syncWorkbenchCollapseState(this.dataset.workbenchCollapse, isCollapsed);
            });
        });
    }

    // Same breakpoint as workbench-shell.css: from 1024px a collapsed AI pane is a narrow rail labelled "AI";
    // stacked below it, the pane keeps its header and the button reads "Expand" like the chart pane.
    const workbenchRailLayout = window.matchMedia('(min-width: 1024px)');
    function workbenchAiExpandLabel() {
        return workbenchRailLayout.matches ? 'AI' : 'Expand';
    }
    workbenchRailLayout.addEventListener('change', function() {
        const button = document.querySelector('[data-workbench-collapse="ai-assistant"]');
        if (button && button.getAttribute('aria-expanded') === 'false') {
            button.textContent = workbenchAiExpandLabel();
        }
    });

    function initializePaneLayout() {
        initializeDashboardSidebarSplitter();
        initializeWorkbenchPanes();
    }

    initializePaneLayout();
    document.body.addEventListener('htmx:afterSwap', initializePaneLayout);
});
