import { fragmentToPreview, normalizeFragment, emptyFragment } from './fragment_codec.js';
import { mount } from './adapter.js';

const DATA_OPTIONS = { group_by: 'none', sort_by: 'key', optional_columns: [] };
const MATRIX_OPTIONS = {
    row_mode: 'one_ticket',
    order_mode: 'stable_append',
    initial_sort: 'key_natural_asc',
    group_mode: 'none',
    groups: [],
    history_mode: 'cumulative',
    cross_week_carry: 'last_confirmed_and_unresolved',
    note_prefix: 'workweek_day_source_status',
    action_labels: { recorded: 'AR', proposed: 'AR?' },
};

export function initializeTemplateBuilder(root) {
    if (!root || root.dataset.templateBuilderInitialized === 'true') return;
    const form = root.querySelector('[data-template-save-form]');
    if (!form) return;
    root.dataset.templateBuilderInitialized = 'true';
    const rows = root.querySelector('[data-template-rows]');
    const documentField = form.querySelector('[data-template-document-field]');
    const policyField = form.querySelector('[data-template-policy-field]');
    const dirtyBanner = root.querySelector('[data-template-dirty-banner]');
    const status = root.querySelector('[data-template-status]');
    const saveButton = root.querySelector('[data-template-save-button]');
    const rowTemplate = root.querySelector('[data-template-row-template]');
    const listeners = new AbortController();
    const { signal } = listeners;
    let activeState = null;
    let dirty = false;
    let mountFailed = false;
    let saving = false;
    let destroyed = false;
    let uncertainSave = null;

    function states() {
        return Array.from(rows.querySelectorAll('[data-template-row]')).map(rowState);
    }

    function markDirty() {
        dirty = true;
        root.dataset.templateDirty = 'true';
        if (dirtyBanner) dirtyBanner.classList.remove('is-hidden');
        syncBlocked();
    }

    function setStatus(message, kind = '') {
        if (!status) return;
        status.textContent = message;
        status.classList.toggle('is-danger', kind === 'error');
        status.classList.toggle('is-success', kind === 'success');
        status.classList.toggle('is-light', !kind);
    }

    function syncBlocked() {
        if (!saveButton) return;
        const blocked = mountFailed || saving || root.dataset.archived === 'true';
        saveButton.disabled = blocked;
        saveButton.setAttribute('aria-disabled', String(blocked));
    }

    function syncPanels(row) {
        const kind = row.querySelector('[data-template-kind]').value;
        row.dataset.kind = kind;
        row.querySelectorAll('[data-template-panel]').forEach(panel => {
            panel.hidden = panel.dataset.templatePanel !== kind;
        });
        const richPanel = row.querySelector('[data-template-rich-panel]');
        if (richPanel) richPanel.hidden = kind === 'data';
        const richLabel = row.querySelector('[data-template-rich-label]');
        if (richLabel) {
            richLabel.textContent = kind === 'slot'
                ? richLabel.dataset.slotText || richLabel.textContent
                : richLabel.dataset.contentText || richLabel.textContent;
        }
        syncMatrixPanel(row);
    }

    function syncMatrixPanel(row) {
        const source = row.querySelector('[data-template-data-source]')?.value;
        row.querySelectorAll('[data-template-matrix-panel]').forEach(panel => {
            panel.hidden = row.dataset.kind !== 'data' || source !== 'meeting_matrix';
        });
    }

    async function ensureMounted(state) {
        if (destroyed || state.destroyed) return null;
        if (state.handle || state.mounting) return state.mounting || state.handle;
        const generation = ++state.mountGeneration;
        state.surface.replaceChildren(fragmentToPreview(state.fragment));
        state.mounting = mount(state.surface, {
            fragment: state.fragment,
            onDirty: (_, fragment) => {
                state.fragment = fragment;
                markDirty();
            },
            readOnly: false,
        }).then(handle => {
            state.handle = handle;
            state.mounting = null;
            if (destroyed || state.destroyed || generation !== state.mountGeneration || !state.row.isConnected) {
                handle.destroy();
                state.handle = null;
                return null;
            }
            state.surface.querySelector('.ProseMirror')?.focus();
            return handle;
        }).catch(() => {
            state.mounting = null;
            if (destroyed || state.destroyed) return null;
            mountFailed = true;
            root.dataset.templateMountFailed = 'true';
            setStatus(message('mountFailed'), 'error');
            syncBlocked();
            return null;
        });
        return state.mounting;
    }

    function rowState(row) {
        if (row.__templateState) return row.__templateState;
        const script = row.querySelector('script[type="application/json"]');
        const fragment = normalizeFragment(script ? JSON.parse(script.textContent) : emptyFragment());
        const surface = row.querySelector('[data-template-editor-surface]');
        const state = {
            row,
            surface,
            fragment,
            handle: null,
            mounting: null,
            destroyed: false,
            mountGeneration: 0,
        };
        row.__templateState = state;
        if (surface && !surface.childElementCount) surface.replaceChildren(fragmentToPreview(fragment));
        return state;
    }

    function rowFragment(row) {
        const state = rowState(row);
        return state.handle ? state.handle.getFragment() : state.fragment;
    }

    function addRow(kind) {
        const row = rowTemplate.content.firstElementChild.cloneNode(true);
        row.dataset.templateRow = 'true';
        row.dataset.blockId = crypto.randomUUID();
        row.dataset.slotId = kind === 'slot' ? crypto.randomUUID() : '';
        row.dataset.kind = kind;
        rows.appendChild(row);
        initializeRow(row);
        markDirty();
    }

    function initializeRow(row) {
        row.querySelector('[data-template-kind]').value = row.dataset.kind || 'content';
        syncPanels(row);
        row.querySelectorAll('[data-template-editor-surface]').forEach(surface => {
            surface.addEventListener('focusin', () => {
                const state = rowState(row);
                state.surface = surface;
                activeState = state;
                ensureMounted(state);
            }, { signal });
        });
        row.querySelector('[data-template-data-source]')?.addEventListener('change', () => syncMatrixPanel(row), { signal });
    }

    function move(row, direction) {
        if (direction === 'up' && row.previousElementSibling) rows.insertBefore(row, row.previousElementSibling);
        if (direction === 'down' && row.nextElementSibling) rows.insertBefore(row.nextElementSibling, row);
        markDirty();
    }

    async function runCommand(control) {
        if (!activeState) return;
        const handle = await ensureMounted(activeState);
        if (!handle) return;
        const command = control.dataset.reportCommand;
        const value = control.dataset.color || control.value || '';
        if (command === 'link') {
            const href = window.prompt('https://');
            if (href) handle.command(command, href);
        } else {
            handle.command(command, value);
        }
        if (control.tagName === 'SELECT') {
            control.blur();
            activeState.row.querySelector('.ProseMirror')?.focus();
        }
        markDirty();
    }

    function collect() {
        const payload = payloadFromRows();
        documentField.value = JSON.stringify(payload.document);
        policyField.value = JSON.stringify(payload.policy);
        return payload;
    }

    function payloadFromRows() {
        const blocks = states().map(state => blockPayload(state.row));
        const schemaVersion = root.dataset.templateSchemaVersion === '2'
            || blocks.some(block => block.kind === 'data' && block.source === 'meeting_matrix')
            ? 2 : 1;
        const policy = { schema_version: schemaVersion, instructions: {} };
        if (schemaVersion === 2) {
            const instructions = root.querySelector('[data-template-daily-note-instructions]')?.value || '';
            policy.daily_note_instructions = instructions || null;
        }
        const document = {
            schema_version: schemaVersion,
            report_kind: root.querySelector('[data-template-report-kind]').value,
            blocks,
        };
        collectSlotInstructions(blocks, policy);
        return { document, policy };
    }

    function currentSignature() {
        const payload = payloadFromRows();
        return JSON.stringify({
            name: form.querySelector('[name="name"]')?.value || '',
            document: payload.document,
            policy: payload.policy,
        });
    }

    function formDataFromEntries(entries) {
        const data = new FormData();
        entries.forEach(([key, value]) => data.append(key, value));
        return data;
    }

    function rotateCommandId() {
        const command = form.querySelector('[name="command_id"]');
        if (command && crypto?.randomUUID) command.value = crypto.randomUUID();
    }

    function applySavedMetadata(payload) {
        const expectedRevision = form.querySelector('[name="expected_revision"]');
        const expectedHash = form.querySelector('[name="expected_revision_hash"]');
        if (expectedRevision) expectedRevision.value = String(payload.revision);
        if (expectedHash) expectedHash.value = String(payload.revision_hash || '');
        rotateCommandId();
    }

    function blockPayload(row) {
        const kind = row.querySelector('[data-template-kind]').value;
        if (kind === 'content') {
            return { kind, block_id: row.dataset.blockId, fragment: rowFragment(row) };
        }
        if (kind === 'slot') {
            const slotId = row.dataset.slotId || crypto.randomUUID();
            row.dataset.slotId = slotId;
            const fillMode = row.querySelector('[data-template-slot-fill-mode]').value;
            const instruction = row.querySelector('[data-template-slot-instruction]').value || '';
            return {
                kind,
                block_id: row.dataset.blockId,
                slot_id: slotId,
                label: row.querySelector('[data-template-slot-label]').value,
                required: row.querySelector('[data-template-slot-required]').checked,
                initial: rowFragment(row),
                fill_mode: fillMode,
            };
        }
        const source = row.querySelector('[data-template-data-source]').value;
        return {
            kind,
            block_id: row.dataset.blockId,
            source,
            options: source === 'meeting_matrix' ? matrixOptions(row) : {
                ...DATA_OPTIONS,
                group_by: row.querySelector('[data-template-data-group]').value,
                optional_columns: Array.from(row.querySelectorAll('[data-template-data-column]:checked')).map(item => item.value),
            },
        };
    }

    function collectSlotInstructions(blocks, policy) {
        states().forEach((state, index) => {
            const block = blocks[index];
            if (!block || block.kind !== 'slot' || block.fill_mode !== 'ai_optional') return;
            const instruction = state.row.querySelector('[data-template-slot-instruction]').value || '';
            if (instruction) policy.instructions[block.slot_id] = instruction;
        });
    }

    function matrixOptions(row) {
        const mode = row.querySelector('[data-template-matrix-group-mode]')?.value || 'none';
        const groups = Array.from(row.querySelectorAll('[data-template-matrix-group]')).map((group, index) => ({
            group_id: group.dataset.groupId,
            label: group.querySelector('[data-template-matrix-group-label]').value || 'Group',
            rank: index,
        }));
        return {
            ...MATRIX_OPTIONS,
            group_mode: mode,
            groups: mode === 'manual' ? groups : [],
            action_labels: { ...MATRIX_OPTIONS.action_labels },
        };
    }

    async function submit(event) {
        event.preventDefault();
        if (mountFailed || saving) {
            setStatus(message('notReadySave'), 'error');
            syncBlocked();
            return;
        }
        let submittedSave = uncertainSave;
        if (!submittedSave) {
            collect();
            submittedSave = {
                entries: Array.from(new FormData(form).entries()),
                signature: currentSignature(),
            };
            uncertainSave = submittedSave;
        }
        saving = true;
        syncBlocked();
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: formDataFromEntries(submittedSave.entries),
            });
            const payload = await response.json();
            if (!response.ok) {
                uncertainSave = null;
                setStatus(payload.message || message('saveFailed'), 'error');
                return;
            }
            if (destroyed) return;
            uncertainSave = null;
            applySavedMetadata(payload);
            if (currentSignature() === submittedSave.signature) {
                dirty = false;
                window.location.assign(payload.redirect_url);
                return;
            }
            dirty = true;
            root.dataset.templateDirty = 'true';
            if (dirtyBanner) dirtyBanner.classList.remove('is-hidden');
            setStatus(message('savedDirty'), 'success');
        } catch (error) {
            if (destroyed) return;
            setStatus(message('saveFailed'), 'error');
        } finally {
            if (destroyed) return;
            saving = false;
            syncBlocked();
        }
    }

    rows.querySelectorAll('[data-template-row]').forEach(initializeRow);
    root.querySelectorAll('[data-template-add]').forEach(button => {
        button.addEventListener('click', () => addRow(button.dataset.templateAdd), { signal });
    });
    root.addEventListener('change', event => {
        const row = event.target.closest?.('[data-template-row]');
        if (event.target.matches('[data-template-kind]')) syncPanels(row);
        markDirty();
    }, { signal });
    root.addEventListener('input', markDirty, { signal });
    root.addEventListener('click', event => {
        const command = event.target.closest?.('[data-template-row-command]');
        if (!command) return;
        const row = command.closest('[data-template-row]');
        const action = command.dataset.templateRowCommand;
        if (action === 'remove') removeRow(row);
        else move(row, action);
        markDirty();
    }, { signal });
    root.addEventListener('click', event => {
        const add = event.target.closest?.('[data-template-matrix-group-add]');
        if (add) {
            addMatrixGroup(add.closest('[data-template-row]'));
            markDirty();
            return;
        }
        const command = event.target.closest?.('[data-template-matrix-group-command]');
        if (!command) return;
        moveMatrixGroup(command.closest('[data-template-matrix-group]'), command.dataset.templateMatrixGroupCommand);
        markDirty();
    }, { signal });
    root.querySelectorAll('[data-report-command]').forEach(control => {
        if (control.tagName === 'BUTTON') {
            control.addEventListener('mousedown', event => event.preventDefault(), { signal });
        }
        control.addEventListener(control.tagName === 'SELECT' ? 'change' : 'click', () => runCommand(control), { signal });
    });
    form.addEventListener('submit', submit, { signal });
    installExitGuards(root, form, () => dirty || saving || mountFailed, signal);
    collect();
    syncBlocked();
    root.__templateBuilder = {
        destroy() {
            if (destroyed) return;
            destroyed = true;
            listeners.abort();
            rows.querySelectorAll('[data-template-row]').forEach(destroyRow);
            root.dataset.templateBuilderInitialized = 'false';
        },
    };

    function removeRow(row) {
        destroyRow(row);
        row.remove();
    }

    function destroyRow(row) {
        const state = row.__templateState;
        if (!state || state.destroyed) return;
        state.destroyed = true;
        state.mountGeneration += 1;
        if (state.handle) state.handle.destroy();
        state.handle = null;
        state.mounting = null;
        if (activeState === state) activeState = null;
    }

    function addMatrixGroup(row) {
        if (!row || !crypto?.randomUUID) return;
        const group = document.createElement('div');
        group.className = 'field has-addons mt-2';
        group.dataset.templateMatrixGroup = 'true';
        group.dataset.groupId = crypto.randomUUID();
        group.innerHTML = `
            <div class="control is-expanded"><input class="input is-small" data-template-matrix-group-label value="Group"></div>
            <div class="control"><button class="button is-small" type="button" data-template-matrix-group-command="up">↑</button></div>
            <div class="control"><button class="button is-small" type="button" data-template-matrix-group-command="down">↓</button></div>
            <div class="control"><button class="button is-small is-danger is-light" type="button" data-template-matrix-group-command="remove">Remove</button></div>
        `;
        row.querySelector('[data-template-matrix-group-mode]').value = 'manual';
        row.querySelector('[data-template-matrix-groups]').appendChild(group);
    }

    function moveMatrixGroup(group, action) {
        if (!group) return;
        if (action === 'remove') group.remove();
        if (action === 'up' && group.previousElementSibling) group.parentElement.insertBefore(group, group.previousElementSibling);
        if (action === 'down' && group.nextElementSibling) group.parentElement.insertBefore(group.nextElementSibling, group);
    }

    function message(name) {
        return root.dataset[`message${name[0].toUpperCase()}${name.slice(1)}`] || '';
    }
}

function installExitGuards(root, saveForm, isBlocked, signal) {
    const message = root.dataset.messageUnsavedExit || 'Unsaved template edits may be lost. Continue?';
    let confirmedExit = false;
    const beforeUnload = event => {
        if (confirmedExit || !isBlocked()) return;
        event.preventDefault();
        event.returnValue = message;
    };
    const click = event => {
        const anchor = event.target.closest?.('a[href]');
        if (!anchor || anchor.target || !isBlocked()) return;
        if (!window.confirm(message)) {
            event.preventDefault();
            return;
        }
        confirmedExit = true;
    };
    const submit = event => {
        if (event.target === saveForm || !isBlocked()) return;
        if (!window.confirm(message)) {
            event.preventDefault();
            return;
        }
        confirmedExit = true;
    };
    window.addEventListener('beforeunload', beforeUnload, { signal });
    document.addEventListener('click', click, { capture: true, signal });
    document.addEventListener('submit', submit, { capture: true, signal });
    document.body.addEventListener('htmx:beforeRequest', event => {
        if (!isBlocked()) return;
        if (!window.confirm(message)) event.preventDefault();
    }, { signal });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-template-builder]').forEach(initializeTemplateBuilder);
});
document.body.addEventListener('htmx:beforeSwap', event => {
    const target = event.target;
    if (!target || !target.querySelectorAll) return;
    if (target.matches?.('[data-template-builder]')) target.__templateBuilder?.destroy();
    target.querySelectorAll('[data-template-builder]').forEach(root => root.__templateBuilder?.destroy());
});
document.body.addEventListener('htmx:afterSwap', () => {
    document.querySelectorAll('[data-template-builder]').forEach(initializeTemplateBuilder);
});
