/*
 * Workbench evidence table: ticket selection and select-all, column toggles, sorting, the
 * ticket detail pane and bulk summary, and sharing selected tickets with the AI iframe.
 */

document.addEventListener('DOMContentLoaded', function() {
    function initializeWorkbenchEvidence() {
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
                // Phones stack the detail under the table (workbench-evidence.css), so it can open off screen.
                const tableWrap = layout && layout.querySelector('.workbench-evidence-table-wrap');
                if (detail && tableWrap && detail.getBoundingClientRect().top >= tableWrap.getBoundingClientRect().bottom) {
                    detail.scrollIntoView({ block: 'nearest' });
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
                    openDetail();
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
                    setDetailText('[data-ticket-detail-issue]', this.dataset.issueKey);
                    setDetailText('[data-ticket-detail-summary]', this.dataset.summary);
                    setDetailText('[data-ticket-detail-status]', this.dataset.status);
                    setDetailText('[data-ticket-detail-severity]', this.dataset.severity);
                    setDetailText('[data-ticket-detail-owner]', this.dataset.owner);
                    setDetailText('[data-ticket-detail-component]', this.dataset.component);
                    setDetailText('[data-ticket-detail-created]', this.dataset.createdLabel);
                    setDetailText('[data-ticket-detail-updated]', this.dataset.updatedLabel);
                    const sourceLink = workspace.querySelector('[data-ticket-detail-source]');
                    if (sourceLink) {
                        sourceLink.href = this.dataset.sourceUrl || '#';
                        sourceLink.classList.toggle('is-disabled', !this.dataset.sourceUrl);
                    }
                    openDetail();
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
    }

    initializeWorkbenchEvidence();
    document.body.addEventListener('htmx:afterSwap', initializeWorkbenchEvidence);
});
