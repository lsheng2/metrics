import { mount } from './adapter.js';
import { createWorkflowControls } from './workflow_controls.js';
import { recoveryTargetKey } from './recovery_state.js';

const EMPTY_FRAGMENT = { schema_version: 2, blocks: [] };

export function createContinuityController(root, form) {
    const field = form?.querySelector('[name="continuity_changes"]') || null;
    const listeners = new AbortController();
    const { signal } = listeners;
    const fragments = [];
    const commands = [];
    let activeFragment = null;
    let destroyed = false;
    const workflow = createWorkflowControls(root, announceChange);

    function controls() {
        return Array.from(root.querySelectorAll('[data-continuity-change]'));
    }

    function changes() {
        return [
            ...commands,
            ...rowGroupChanges(),
            ...controls().map(changeFromControl).filter(change => change !== null),
            ...fragments.map(fragmentChange).filter(change => change !== null),
            ...workflow.changes(),
        ];
    }

    function rowGroupChanges() {
        return Array.from(root.querySelectorAll('[data-continuity-row-group]')).map(select => {
            if (select.value === (select.dataset.originalGroupId || '')) return null;
            const change = JSON.parse(select.dataset.continuityChange || '{}');
            return { ...change, group_id: select.value || null };
        }).filter(change => change !== null);
    }

    function changeFromControl(control) {
        if (control.dataset.continuityRowGroup !== undefined) return null;
        if (Object.hasOwn(control.dataset, 'continuityCommand')) return null;
        const raw = control.dataset.continuityPayload || control.dataset.continuityChange;
        if (!raw) return null;
        const change = JSON.parse(raw);
        if (control.type === 'checkbox') {
            change[control.dataset.continuityValueField || 'carry_forward'] = control.checked;
        }
        if (control.dataset.continuityTextField) {
            change[control.dataset.continuityTextField] = control.value;
        }
        return change;
    }

    function fragmentChange(item) {
        const fragment = item.handle ? item.handle.getFragment() : item.fragment;
        if (item.kind === 'persistent') {
            return {
                kind: 'add_persistent_note',
                note_id: item.noteId,
                target: item.target,
                issue_ref: item.issueRef,
                fragment,
                carry_forward: item.carry.checked,
            };
        }
        const actionState = item.state?.value || item.expectedState;
        if (item.kind === 'action' && (item.done.checked || actionState !== item.expectedState)) {
            return {
                kind: 'set_action_tracking',
                action_id: item.actionId,
                expected_state: item.expectedState,
                state: item.done.checked ? 'done' : actionState,
                resolution: fragment,
                evidence_refs: item.evidenceRefs(),
            };
        }
        return null;
    }

    function serialize() {
        return JSON.stringify(changes());
    }

    function write() {
        const value = serialize();
        if (field) field.value = value;
        return value;
    }

    function announceChange() {
        root.dispatchEvent(new CustomEvent('report-continuity-change', { bubbles: true }));
    }

    function addPersistent(button, restored = null) {
        const target = restored?.target || button.dataset.persistentTarget || 'issue';
        const host = target === 'report'
            ? root.querySelector('[data-continuity-report-persistent-list]')
            : button.closest('th')?.querySelector('[data-continuity-persistent-list]');
        if (!host || !crypto?.randomUUID) return;
        const noteId = restored?.note_id || crypto.randomUUID();
        const article = document.createElement('article');
        article.className = 'report-persistent-note';
        article.dataset.continuityPersistentDraft = noteId;
        article.innerHTML = `
            <label class="label is-small"></label>
            <div class="report-editor-surface paper" data-continuity-fragment-surface tabindex="0"></div>
            <label class="checkbox"><input type="checkbox" data-continuity-carry checked> <span></span></label>
        `;
        const noteLabel = root.dataset.messagePersistentNote || 'Persistent note';
        article.querySelector('.label').textContent = noteLabel;
        article.querySelector('[data-continuity-fragment-surface]').setAttribute('aria-label', noteLabel);
        article.querySelector('.checkbox > span').textContent = root.dataset.messageCarryForward || 'Carry forward';
        host.appendChild(article);
        const item = {
            kind: 'persistent',
            noteId,
            target,
            issueRef: target === 'report' ? null : JSON.parse(button.dataset.issueRefJson || '{}'),
            carry: article.querySelector('[data-continuity-carry]'),
            surface: article.querySelector('[data-continuity-fragment-surface]'),
            fragment: restored?.fragment || EMPTY_FRAGMENT,
            handle: null,
            mountGeneration: 0,
        };
        fragments.push(item);
        if (restored) item.carry.checked = restored.carry_forward;
        activeFragment = item;
        mountFragment(item);
        item.carry.addEventListener('change', announceChange, { signal });
        announceChange();
    }

    function mountFragment(item) {
        if (destroyed || !item.surface.isConnected) return;
        const generation = ++item.mountGeneration;
        item.surface.addEventListener('focusin', () => {
            if (destroyed || generation !== item.mountGeneration) return;
            activeFragment = item;
        }, { signal });
        mount(item.surface, {
            fragment: item.fragment,
            onDirty: (_, fragment) => {
                if (destroyed || generation !== item.mountGeneration || !item.surface.isConnected) return;
                item.fragment = fragment;
                announceChange();
            },
            readOnly: false,
        }).then(handle => {
            if (destroyed || generation !== item.mountGeneration || !item.surface.isConnected) {
                handle.destroy();
                return;
            }
            item.handle = handle;
            item.surface.querySelector('.ProseMirror')?.focus();
        });
    }

    function registerAction(details) {
        const surface = details.querySelector('[data-continuity-action-editor]');
        const done = details.querySelector('[data-continuity-action-done]');
        const item = {
            kind: 'action',
            actionId: details.dataset.actionId,
            expectedState: details.dataset.expectedState,
            state: details.querySelector('[data-report-action-state]'),
            done,
            surface,
            fragment: EMPTY_FRAGMENT,
            handle: null,
            mountGeneration: 0,
            evidenceRefs: () => Array.from(details.querySelectorAll('[data-continuity-evidence]:checked')).map(input => input.value),
        };
        fragments.push(item);
        surface.addEventListener('focusin', () => {
            activeFragment = item;
            if (!item.handle) mountFragment(item);
        }, { once: true, signal });
        done.addEventListener('change', announceChange, { signal });
        item.state?.addEventListener('change', () => { done.checked = false; announceChange(); }, { signal });
        details.querySelectorAll('[data-continuity-evidence]').forEach(input => {
            input.addEventListener('change', announceChange, { signal });
        });
    }

    controls().forEach(control => {
        control.addEventListener('input', announceChange, { signal });
        control.addEventListener('change', announceChange, { signal });
    });
    root.querySelectorAll('[data-continuity-command]').forEach(button => {
        button.addEventListener('click', () => {
            commands.push(JSON.parse(button.dataset.continuityChange));
            announceChange();
        }, { signal });
    });
    root.querySelectorAll('[data-continuity-add-persistent]').forEach(button => {
        button.addEventListener('click', () => addPersistent(button), { signal });
    });
    root.querySelectorAll('[data-continuity-action-control]').forEach(registerAction);
    root.addEventListener('focusin', event => {
        if (event.target.closest?.('[data-report-shared-toolbar]')) return;
        activeFragment = fragments.find(item => item.surface.contains(event.target)) || null;
    }, { signal });

    if (field && !field.value) field.value = '[]';

    return {
        serialize,
        restore(values) {
            workflow.restore(values);
            for (const value of values) {
                if (value.kind === 'add_persistent_note') {
                    const buttons = Array.from(root.querySelectorAll('[data-continuity-add-persistent]'));
                    const button = buttons.find(node => value.target === 'report'
                        ? node.dataset.persistentTarget === 'report'
                        : node.dataset.issueRefJson && recoveryTargetKey(JSON.parse(node.dataset.issueRefJson)) === recoveryTargetKey(value.issue_ref));
                    if (!button) throw new Error('Recovery target unavailable');
                    addPersistent(button, value);
                } else if (value.kind === 'set_action_tracking') {
                    const item = fragments.find(item => item.actionId === value.action_id);
                    if (!item) throw new Error('Recovery action unavailable');
                    item.done.checked = false;
                    if (item.state) item.state.value = value.state;
                    item.fragment = value.resolution;
                    if (item.handle) item.handle.replaceFragment(item.handle.local_version, value.resolution);
                    else mountFragment(item);
                } else if (value.kind === 'move_row') {
                    commands.push(value);
                } else if (value.kind === 'set_persistent_carry') {
                    const node = controls().find(node => {
                        const raw = node.dataset.continuityPayload;
                        return raw && JSON.parse(raw).note_id === value.note_id;
                    });
                    if (!node) throw new Error('Recovery note unavailable');
                    node.checked = value.carry_forward;
                }
            }
            announceChange();
        },
        activeEditor: () => activeFragment,
        signature: serialize,
        write,
        reset() {
            write();
        },
        destroy() {
            destroyed = true;
            listeners.abort();
            workflow.destroy();
            fragments.forEach(item => {
                item.mountGeneration += 1;
            });
            fragments.forEach(item => item.handle?.destroy());
        },
    };
}
