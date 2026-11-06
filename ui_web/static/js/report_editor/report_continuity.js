import { mount } from './adapter.js';

const EMPTY_FRAGMENT = { schema_version: 2, blocks: [] };

export function createContinuityController(root, form) {
    const field = form?.querySelector('[name="continuity_changes"]') || null;
    const listeners = new AbortController();
    const { signal } = listeners;
    const fragments = [];
    const commands = [];
    let activeFragment = null;
    let destroyed = false;

    function controls() {
        return Array.from(root.querySelectorAll('[data-continuity-change]'));
    }

    function changes() {
        return [
            ...commands,
            ...rowGroupChanges(),
            ...controls().map(changeFromControl).filter(change => change !== null),
            ...fragments.map(fragmentChange).filter(change => change !== null),
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
        if (item.kind === 'action' && item.done.checked) {
            return {
                kind: 'set_action_tracking',
                action_id: item.actionId,
                expected_state: item.expectedState,
                state: 'done',
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

    function addPersistent(button) {
        const target = button.dataset.persistentTarget || 'issue';
        const host = target === 'report'
            ? root.querySelector('[data-continuity-report-persistent-list]')
            : button.closest('th')?.querySelector('[data-continuity-persistent-list]');
        if (!host || !crypto?.randomUUID) return;
        const noteId = crypto.randomUUID();
        const article = document.createElement('article');
        article.className = 'notification is-light mt-2';
        article.dataset.continuityPersistentDraft = noteId;
        article.innerHTML = `
            <label class="label">Persistent note</label>
            <div class="report-editor-surface" data-continuity-fragment-surface tabindex="0" aria-label="Persistent note"></div>
            <label class="checkbox mt-2"><input type="checkbox" data-continuity-carry checked> Carry forward</label>
        `;
        host.appendChild(article);
        const item = {
            kind: 'persistent',
            noteId,
            target,
            issueRef: target === 'report' ? null : JSON.parse(button.dataset.issueRefJson || '{}'),
            carry: article.querySelector('[data-continuity-carry]'),
            surface: article.querySelector('[data-continuity-fragment-surface]'),
            fragment: EMPTY_FRAGMENT,
            handle: null,
            mountGeneration: 0,
        };
        fragments.push(item);
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

    async function runToolbarCommand(control) {
        if (!activeFragment?.handle) return;
        const command = control.dataset.reportCommand;
        const value = control.dataset.color || control.value || '';
        if (command === 'link') {
            const href = window.prompt('https://');
            if (href) activeFragment.handle.command(command, href);
        } else {
            activeFragment.handle.command(command, value);
        }
        announceChange();
    }

    function registerAction(details) {
        const surface = details.querySelector('[data-continuity-action-editor]');
        const done = details.querySelector('[data-continuity-action-done]');
        const item = {
            kind: 'action',
            actionId: details.dataset.actionId,
            expectedState: details.dataset.expectedState,
            done,
            surface,
            fragment: EMPTY_FRAGMENT,
            handle: null,
            mountGeneration: 0,
            evidenceRefs: () => Array.from(details.querySelectorAll('[data-continuity-evidence]:checked')).map(input => input.value),
        };
        fragments.push(item);
        surface.addEventListener('focusin', () => {
            if (!item.handle) mountFragment(item);
        }, { once: true, signal });
        done.addEventListener('change', announceChange, { signal });
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
    root.querySelectorAll('[data-report-command]').forEach(control => {
        if (control.tagName === 'BUTTON') {
            control.addEventListener('mousedown', event => {
                if (activeFragment) event.preventDefault();
            }, { signal });
            control.addEventListener('click', () => runToolbarCommand(control), { signal });
            return;
        }
        control.addEventListener('change', () => runToolbarCommand(control), { signal });
    });

    if (field && !field.value) field.value = '[]';

    return {
        serialize,
        signature: serialize,
        write,
        reset() {
            write();
        },
        destroy() {
            destroyed = true;
            listeners.abort();
            fragments.forEach(item => {
                item.mountGeneration += 1;
            });
            fragments.forEach(item => item.handle?.destroy());
        },
    };
}
