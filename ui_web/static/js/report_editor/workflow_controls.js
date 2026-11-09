import { mount } from './adapter.js';
import { recoveryTargetKey } from './recovery_state.js';

export function createWorkflowControls(root, changed) {
    const abort = new AbortController();
    const actions = [];
    const on = (node, event, handler) => node.addEventListener(event, handler, { signal: abort.signal });
    const message = (key, fallback) => root.dataset[key] || fallback;

    function addAction(button, restored = null) {
        const host = button.closest('th').querySelector('[data-continuity-new-actions]');
        const node = document.createElement('div');
        node.className = 'report-new-action';
        node.dataset.newReportAction = restored?.action_id || crypto.randomUUID();
        const ownerLabel = document.createElement('label');
        ownerLabel.className = 'label is-small';
        ownerLabel.textContent = message('messageArOwner', 'AR owner');
        const owner = document.createElement('input');
        owner.type = 'text';
        owner.className = 'input is-small';
        owner.maxLength = 160;
        owner.setAttribute('aria-label', ownerLabel.textContent);
        owner.value = restored?.owner_ref?.display_name || '';
        const body = document.createElement('div');
        body.className = 'report-editor-surface paper';
        body.tabIndex = 0;
        body.setAttribute('aria-label', message('messageArBody', 'AR'));
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'button is-small';
        remove.textContent = message('messageRemoveAr', 'Remove unsaved AR');
        node.append(ownerLabel, owner, body, remove);
        host.append(node);
        const item = { node, owner, body, handle: null,
            fragment: restored?.fragment || { schema_version: 2, blocks: [] },
            issue: JSON.parse(button.dataset.issueRefJson), id: node.dataset.newReportAction };
        actions.push(item);
        mount(body, {
            fragment: item.fragment, readOnly: false,
            onDirty: (_, fragment) => { item.fragment = fragment; changed(); },
        }).then(handle => {
            if (!node.isConnected) { handle.destroy(); return; }
            item.handle = handle;
        }).catch(() => { body.textContent = message('messageSaveFailed', 'Report request failed.'); });
        on(owner, 'input', changed);
        on(remove, 'click', () => {
            actions.splice(actions.indexOf(item), 1);
            item.handle?.destroy();
            node.remove();
            changed();
        });
        changed();
    }

    root.querySelectorAll('[data-continuity-add-action]').forEach(button => on(button, 'click', () => addAction(button)));
    root.querySelectorAll('[data-meeting-review], [data-report-action-owner]').forEach(input => on(input, 'change', changed));

    function changes() {
        const result = actions.map(item => ({
            kind: 'add_report_action', action_id: item.id, issue_ref: item.issue,
            owner_ref: item.owner.value.trim() ? { owner_id: item.owner.value.trim(), display_name: item.owner.value.trim() } : null,
            fragment: item.handle ? item.handle.getFragment() : item.fragment,
        }));
        root.querySelectorAll('[data-meeting-review]').forEach(select => {
            if (select.value !== select.dataset.originalReview) {
                result.push({ ...JSON.parse(select.dataset.reviewPayload), state: select.value });
            }
        });
        root.querySelectorAll('[data-report-action-owner]').forEach(input => {
            if (input.value !== input.dataset.originalOwner) {
                result.push({ ...JSON.parse(input.dataset.ownerPayload),
                    owner_ref: input.value.trim() ? { owner_id: input.value.trim(), display_name: input.value.trim() } : null });
            }
        });
        return result;
    }

    return {
        changes,
        restore(commands) {
            for (const command of commands) {
                if (command.kind === 'add_report_action') {
                    const button = Array.from(root.querySelectorAll('[data-continuity-add-action]'))
                        .find(node => recoveryTargetKey(JSON.parse(node.dataset.issueRefJson)) === recoveryTargetKey(command.issue_ref));
                    if (!button) throw new Error('Recovery target unavailable');
                    addAction(button, command);
                } else if (command.kind === 'set_meeting_review') {
                    const select = Array.from(root.querySelectorAll('[data-meeting-review]'))
                        .find(node => recoveryTargetKey(JSON.parse(node.dataset.reviewPayload).issue_ref) === recoveryTargetKey(command.issue_ref));
                    if (!select) throw new Error('Recovery target unavailable');
                    select.value = command.state;
                } else if (command.kind === 'set_action_owner') {
                    const input = Array.from(root.querySelectorAll('[data-report-action-owner]'))
                        .find(node => JSON.parse(node.dataset.ownerPayload).action_id === command.action_id);
                    if (!input) throw new Error('Recovery target unavailable');
                    input.value = command.owner_ref?.display_name || '';
                }
            }
        },
        destroy() { abort.abort(); actions.forEach(item => item.handle?.destroy()); },
    };
}
