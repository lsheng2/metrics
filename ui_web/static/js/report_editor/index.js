import { fragmentText, fragmentToPreview, normalizeFragment, plainTextFragment } from './fragment_codec.js';
import { mount } from './adapter.js';
import { createCompletionController, currentReferenceReceipts, stripReferenceMetadata } from './completion.js';
import { createContinuityController } from './report_continuity.js';
import { createAssistController } from './assist.js';
import { createRecoveryController } from './recovery.js';
import { recoveryTargetKey } from './recovery_state.js';

const EMPTY = { schema_version: 2, blocks: [] };

function initializeReportAuthoring(root) {
    if (!root || root.dataset.reportAuthoringInitialized === 'true') {
        return;
    }
    root.dataset.reportAuthoringInitialized = 'true';
    const form = root.querySelector('[data-report-authored-form]');
    if (!form) {
        const recovery = createRecoveryController(root, {
            capture: async () => null,
            restore: async () => { throw new Error('Read-only report'); },
            blocked: () => true,
        });
        root.__reportAuthoring = { destroy: () => recovery.destroy() };
        return;
    }
    const regions = Array.from(root.querySelectorAll('[data-report-wysiwyg-region]')).map(regionState);
    const authoredField = form.querySelector('[name="authored_edits"]');
    const commandId = form.querySelector('[name="command_id"]');
    const expectedRevision = form.querySelector('[name="expected_revision"]');
    const expectedHash = form.querySelector('[name="expected_revision_hash"]');
    const saveButton = root.querySelector('[data-report-save-button]');
    const copyButton = root.querySelector('[data-report-copy-button]');
    const finalizeButton = root.querySelector('[data-report-finalize-button]');
    const assistButton = root.querySelector('[data-report-assist-open]');
    const dirtyBanner = root.querySelector('[data-report-dirty-banner]');
    const status = root.querySelector('[data-report-copy-status]');
    let dirty = false;
    let saving = false;
    let failedMount = false;
    let saveEpoch = 0;
    let activeState = null;
    let baselineSignature = '';
    let uncertainSave = null;
    let destroyed = false;
    const completions = createCompletionController(root);
    const continuity = createContinuityController(root, form);
    const recovery = createRecoveryController(root, {
        capture: async () => {
            if (!dirty && !uncertainSave) return null;
            return { edits: await collectEdits(), continuity_changes: JSON.parse(continuity.serialize()),
                save_request: recoverySaveRequest(uncertainSave) };
        },
        restore: restoreRecovery,
        blocked: () => dirty || saving || failedMount || Boolean(uncertainSave),
    });
    const assists = createAssistController(root, {
        activeRegion: () => activeState,
        resolveTarget,
        blocked: () => dirty || saving || failedMount || Boolean(uncertainSave),
        changed: () => refreshDirty(),
    });
    const listeners = new AbortController();
    const { signal } = listeners;

    function setStatus(message, kind) {
        if (!status) return;
        status.textContent = message || '';
        status.classList.toggle('is-danger', kind === 'error');
        status.classList.toggle('is-success', kind === 'success');
        status.classList.toggle('is-light', !kind);
    }

    function setDirty(value) {
        dirty = value === undefined
            ? currentSignature() !== baselineSignature || regions.some(state => Boolean(state.assistReceiptId))
            : value;
        root.dataset.reportAuthoringDirty = String(dirty);
        if (dirtyBanner) dirtyBanner.classList.toggle('is-hidden', !dirty);
        syncDisabled();
    }

    function syncDisabled() {
        const blocked = dirty || saving || failedMount || Boolean(uncertainSave);
        root.dataset.reportAuthoringSaving = String(saving);
        root.dataset.reportAuthoringFailed = String(failedMount);
        root.dataset.reportAuthoringUncertain = String(Boolean(uncertainSave));
        if (finalizeButton && !finalizeButton.hasAttribute('data-server-disabled')) {
            finalizeButton.disabled = blocked;
            finalizeButton.setAttribute('aria-disabled', String(blocked));
        }
        if (saveButton) {
            saveButton.disabled = saving || failedMount;
            saveButton.setAttribute('aria-disabled', String(saveButton.disabled));
        }
        if (assistButton) assistButton.disabled = !activeState?.handle || saving || failedMount || Boolean(uncertainSave);
        root.dispatchEvent(new CustomEvent('report-authoring-state'));
    }

    function refreshDirty() {
        setDirty();
        recovery.changed();
    }

    async function ensureMounted(state) {
        if (destroyed || state.destroyed) {
            return null;
        }
        if (state.handle || state.mounting) {
            return state.mounting || state.handle;
        }
        const mountGeneration = ++state.mountGeneration;
        state.surface.dataset.regionId = state.region.dataset.regionId || state.editId;
        state.mounting = mount(state.surface, {
            fragment: state.fragment,
            onDirty: (isDirty, fragment) => {
                if (destroyed || state.destroyed || mountGeneration !== state.mountGeneration) {
                    return;
                }
                state.fragment = fragment;
                state.dirty = isDirty;
                state.assistReceiptId = null;
                refreshDirty();
            },
            onCompletionToken: (capture, metadata) => {
                completions.handleCapture(state, capture, metadata);
                assists.changed();
            },
            readOnly: false,
        }).then(handle => {
            state.mounting = null;
            if (destroyed || state.destroyed || mountGeneration !== state.mountGeneration) {
                handle.destroy();
                return null;
            }
            state.handle = handle;
            syncDisabled();
            return handle;
        }).catch(error => {
            state.mounting = null;
            if (destroyed || state.destroyed) {
                return null;
            }
            failedMount = true;
            setStatus(root.dataset.messageSaveFailed, 'error');
            syncDisabled();
            return null;
        });
        return state.mounting;
    }

    regions.forEach(state => {
        state.surface.addEventListener('focus', () => ensureMounted(state), { once: true, signal });
        state.surface.addEventListener('focusin', () => {
            activeState = state;
            ensureMounted(state);
        }, { signal });
        state.surface.addEventListener('mousedown', () => {
            activeState = state;
            ensureMounted(state);
        }, { once: true, signal });
        state.surface.addEventListener('paste', event => {
            const html = event.clipboardData?.getData('text/html');
            if (html) {
                event.preventDefault();
                event.stopPropagation();
            }
            ensureMounted(state).then(handle => {
                if (!handle || destroyed || state.destroyed) {
                    return;
                }
                if (handle.pasteHtml && html) {
                    const message = pasteMessage(root, handle.pasteHtml(html));
                    const pasteStatus = state.region.querySelector('[data-report-paste-status]');
                    if (pasteStatus) pasteStatus.textContent = message;
                }
            });
        }, { capture: true, signal });
        const target = state.region.querySelector('[data-report-edit-target]');
        if (target) {
            target.addEventListener('change', () => {
                state.dirty = true;
                state.assistReceiptId = null;
                refreshDirty();
            }, { signal });
        }
        const operation = state.region.querySelector('[data-report-edit-operation]');
        if (operation) {
            operation.addEventListener('change', () => refreshDirty(), { signal });
        }
    });

    root.querySelectorAll('[data-report-command]').forEach(control => {
        if (control.tagName === 'BUTTON') {
            control.addEventListener('mousedown', event => event.preventDefault(), { signal });
            control.addEventListener('click', () => runCommand(control), { signal });
            return;
        }
        control.addEventListener('change', () => runCommand(control), { signal });
    });

    async function runCommand(control) {
        const contextual = continuity.activeEditor();
        const state = activeState || regions.find(item => item.handle);
        if (!state && !contextual) return;
        const handle = contextual ? contextual.handle : await ensureMounted(state);
        if (!handle) return;
        const command = control.dataset.reportCommand;
        const value = control.dataset.color || control.value || '';
        if (command === 'link') {
            const href = window.prompt('https://');
            if (href) handle.command(command, href);
            refreshDirty();
            return;
        }
        handle.command(command, value);
        if (control.tagName === 'SELECT') {
            control.blur();
            (contextual?.surface || state.region).querySelector('.ProseMirror')?.focus();
        }
        refreshDirty();
    }

    async function collectEdits() {
        const edits = [];
        for (const state of regions) {
            const operation = state.region.querySelector('[data-report-edit-operation]')?.value || 'add';
            if (operation === 'remove') {
                continue;
            }
            const fragment = state.handle ? state.handle.getFragment() : state.fragment;
            const submittedFragment = state.humanizeReferences ? stripReferenceMetadata(fragment) : fragment;
            const targetData = resolveTarget(state);
            if (!targetData) {
                if (state.existing) {
                    continue;
                }
                if (fragmentText(fragment) === '') {
                    continue;
                }
                throw new Error('target required');
            }
            if (!state.existing && !state.dirty) {
                continue;
            }
            edits.push({
                edit_id: state.editId,
                kind: state.kind,
                target: targetData.target,
                fragment: submittedFragment,
                expected_original_hash: expectedOriginalHash(state, targetData),
                reference_receipts: [...new Set([...currentReferenceReceipts(state), ...(state.recoveredReceipts || [])])],
                assist_receipt_id: state.assistReceiptId || null,
            });
        }
        return edits;
    }

    function expectedOriginalHash(state, targetData) {
        if (state.kind === 'narrative_override') {
            return targetData.expectedOriginalHash;
        }
        if (targetData.target?.scope === 'daily_note') {
            return targetData.expectedOriginalHash;
        }
        return null;
    }

    function currentSignature() {
        return JSON.stringify({
            regions: regions.map(state => ({
                editId: state.editId,
                kind: state.kind,
                target: state.region.dataset.targetJson || '',
                operation: state.region.querySelector('[data-report-edit-operation]')?.value || 'add',
                fragment: signatureFragment(state),
            })),
            continuity: continuity.signature(),
        });
    }

    function signatureFragment(state) {
        const fragment = state.handle ? state.handle.getFragment() : state.fragment;
        const normalized = normalizeFragment(fragment);
        return isApplicationEmptyFragment(normalized) ? EMPTY : normalized;
    }

    function isApplicationEmptyFragment(fragment) {
        if (!fragment.blocks.length) {
            return true;
        }
        if (fragment.blocks.length !== 1) {
            return false;
        }
        const [block] = fragment.blocks;
        if (block.type !== 'paragraph') {
            return false;
        }
        if (!block.content.length) {
            return true;
        }
        if (block.content.length !== 1) {
            return false;
        }
        const [inline] = block.content;
        return inline.type === 'text'
            && inline.text === ''
            && inline.marks.length === 0
            && inline.foreground === null
            && inline.background === null;
    }

    function rotateCommandId() {
        if (commandId && crypto?.randomUUID) {
            commandId.value = crypto.randomUUID();
        }
    }

    function formDataFromEntries(entries) {
        const data = new FormData();
        entries.forEach(([key, value]) => data.append(key, value));
        return data;
    }

    async function submit(event) {
        event.preventDefault();
        if (saving || destroyed) {
            return;
        }
        saving = true;
        const submittedEpoch = ++saveEpoch;
        syncDisabled();
        let submittedSave = uncertainSave;
        if (!submittedSave) {
            let edits;
            try {
                edits = await collectEdits();
            } catch (error) {
                saving = false;
                root.dataset.reportAuthoringError = error.message || 'collect failed';
                setStatus(root.dataset.messageSaveFailed, 'error');
                syncDisabled();
                return;
            }
            authoredField.value = JSON.stringify(edits);
            continuity.write();
            const body = new FormData(form);
            submittedSave = { entries: Array.from(body.entries()), signature: currentSignature() };
            uncertainSave = submittedSave;
            recovery.changed();
        }
        const body = formDataFromEntries(submittedSave.entries);
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body,
            });
            const payload = await response.json();
            if (!response.ok) throw payload;
            if (destroyed || submittedEpoch !== saveEpoch) {
                return;
            }
            const acceptedSignature = submittedSave.signature;
            uncertainSave = null;
            continuity.reset();
            applySavedMetadata(payload);
            baselineSignature = acceptedSignature;
            if (currentSignature() === acceptedSignature) {
                await recovery.saved();
                if (currentSignature() === acceptedSignature) {
                    setDirty(false);
                    window.location.assign(payload.redirect_url);
                    return;
                }
                recovery.resume();
            }
            rotateCommandId();
            refreshDirty();
            setStatus(root.dataset.messageReady, 'success');
            root.dispatchEvent(new CustomEvent('report-authoring-saved', { detail: payload }));
        } catch (error) {
            if (destroyed) {
                return;
            }
            if (error && error.error_code) {
                uncertainSave = null;
            }
            root.dataset.reportAuthoringError = error.error_code || error.message || 'save failed';
            setStatus(root.dataset.messageSaveFailed, 'error');
            if (isReferenceError(error?.error_code)) {
                showHumanLinkConversion();
            }
            setDirty(true);
            recovery.changed();
        } finally {
            if (!destroyed) {
                saving = false;
                syncDisabled();
            }
        }
    }

    function applySavedMetadata(payload) {
        const revision = String(payload.revision);
        const revisionHash = String(payload.revision_hash || '');
        if (expectedRevision) expectedRevision.value = revision;
        if (expectedHash) expectedHash.value = revisionHash;
        root.dataset.revision = revision;
        root.dataset.revisionHash = revisionHash;
        if (payload.snapshot_hash) root.dataset.snapshotHash = payload.snapshot_hash;
        if (payload.template_hash) root.dataset.templateHash = payload.template_hash;
        if (payload.clipboard_url) root.dataset.clipboardUrl = payload.clipboard_url;
        regions.forEach(state => {
            state.assistReceiptId = null;
            const target = resolveTarget(state)?.target;
            if (target?.scope === 'daily_note' && Object.hasOwn(payload.current_note_hashes || {}, target.note_id)) {
                state.region.dataset.expectedOriginalHash = payload.current_note_hashes[target.note_id];
            }
        });
        const finalizeForm = root.querySelector('[data-report-finalize-form]');
        const finalizeExpected = finalizeForm?.querySelector('[name="expected_revision"]');
        if (finalizeExpected) finalizeExpected.value = revision;
        const finalizeRevision = root.querySelector('[data-report-finalize-revision]');
        if (finalizeRevision) finalizeRevision.textContent = revision;
        const finalizeHash = root.querySelector('[data-report-finalize-revision-hash]');
        if (finalizeHash) finalizeHash.textContent = revisionHash.slice(0, 12);
    }

    function recoverySaveRequest(value) {
        if (!value) return null;
        const fields = Object.fromEntries(value.entries);
        return {
            command_id: fields.command_id, expected_revision: Number(fields.expected_revision),
            expected_revision_hash: fields.expected_revision_hash,
            edits: JSON.parse(fields.authored_edits), continuity_changes: JSON.parse(fields.continuity_changes || '[]'),
        };
    }

    async function restoreRecovery(content) {
        const used = new Set();
        const assignments = content.edits.map(edit => {
            const state = regions.find(item => !used.has(item) && item.editId === edit.edit_id)
                || regions.find(item => !used.has(item) && recoveryTargetKey(resolveTarget(item)?.target) === recoveryTargetKey(edit.target));
            if (!state || recoveryTargetKey(resolveTarget(state)?.target) !== recoveryTargetKey(edit.target)) {
                throw new Error('Recovery target unavailable');
            }
            used.add(state);
            return { state, edit, fragment: normalizeFragment(edit.fragment) };
        });
        for (const { state, edit, fragment } of assignments) {
            state.editId = edit.edit_id;
            state.fragment = fragment;
            state.recoveredReceipts = edit.reference_receipts || [];
            state.dirty = true;
            state.region.dataset.expectedOriginalHash = edit.expected_original_hash || '';
            if (state.handle) state.handle.replaceFragment(state.handle.local_version, state.fragment);
            else state.surface.replaceChildren(fragmentToPreview(state.fragment));
            state.assistReceiptId = edit.assist_receipt_id;
        }
        continuity.restore(content.continuity_changes);
        if (content.save_request) {
            const pending = content.save_request;
            const fields = new FormData(form);
            fields.set('command_id', pending.command_id);
            fields.set('expected_revision', String(pending.expected_revision));
            fields.set('expected_revision_hash', pending.expected_revision_hash);
            fields.set('authored_edits', JSON.stringify(pending.edits));
            fields.set('continuity_changes', JSON.stringify(pending.continuity_changes));
            const same = JSON.stringify(content.edits) === JSON.stringify(pending.edits)
                && JSON.stringify(content.continuity_changes) === JSON.stringify(pending.continuity_changes);
            uncertainSave = { entries: Array.from(fields.entries()), signature: same ? currentSignature() : null };
        }
        setDirty(true);
    }

    function isReferenceError(code) {
        return ['REFERENCE_RECEIPT_EXPIRED', 'REFERENCE_CONTENT_CHANGED', 'REFERENCE_INVALID'].includes(code);
    }

    function showHumanLinkConversion() {
        if (!status || status.querySelector('[data-report-keep-human-link]')) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button is-small is-light ml-2';
        button.dataset.reportKeepHumanLink = 'true';
        button.textContent = 'Keep as human link';
        button.addEventListener('click', convertReferencesToHumanLinks);
        status.appendChild(document.createTextNode(' '));
        status.appendChild(button);
    }

    function convertReferencesToHumanLinks() {
        regions.forEach(state => {
            state.referenceReceipts = [];
            state.recoveredReceipts = [];
            state.humanizeReferences = true;
            state.dirty = true;
        });
        refreshDirty();
        setStatus(root.dataset.messageReady, 'success');
    }

    form.addEventListener('submit', submit, { signal });
    form.addEventListener('input', () => refreshDirty(), { signal });
    form.addEventListener('change', () => refreshDirty(), { signal });
    root.addEventListener('report-continuity-change', () => refreshDirty(), { signal });
    baselineSignature = currentSignature();
    installExitGuards(root, form, () => dirty || saving || failedMount || Boolean(uncertainSave), signal);
    root.__reportAuthoring = {
        destroy() {
            if (destroyed) return;
            destroyed = true;
            listeners.abort();
            regions.forEach(state => {
                state.destroyed = true;
                state.mountGeneration += 1;
                if (state.handle) state.handle.destroy();
                state.handle = null;
                state.mounting = null;
            });
            root.__reportAuthoringExitCleanup?.();
            completions.destroy();
            continuity.destroy();
            assists.destroy();
            recovery.destroy();
            root.dataset.reportAuthoringInitialized = 'false';
        },
    };
    syncDisabled();
}

function pasteMessage(root, codeText) {
    const codes = String(codeText || 'kept').split(',').filter(Boolean);
    const messages = {
        kept: root.dataset.messagePasteKept,
        script: root.dataset.messagePasteScript,
        link: root.dataset.messagePasteLink,
        media: root.dataset.messagePasteMedia,
        heading: root.dataset.messagePasteHeading,
        html: root.dataset.messagePasteHtml,
    };
    return codes.map(code => messages[code] || code).join(' ');
}

function installExitGuards(root, saveForm, isBlocked, signal) {
    const message = root.dataset.messageUnsavedExit || 'Unsaved edits may be lost.';
    let confirmedExit = false;
    const beforeUnload = event => {
        if (confirmedExit || !isBlocked()) return;
        event.preventDefault();
        event.returnValue = message;
    };
    const click = event => {
        const anchor = event.target.closest?.('a[href]');
        if (!anchor || anchor.target || anchor.hasAttribute('download') || !isBlocked()) return;
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
    const htmx = event => {
        if (!isBlocked()) return;
        if (!window.confirm(message)) {
            event.preventDefault();
            return;
        }
        confirmedExit = true;
    };
    window.addEventListener('beforeunload', beforeUnload, { signal });
    document.addEventListener('click', click, { capture: true, signal });
    document.addEventListener('submit', submit, { capture: true, signal });
    document.body.addEventListener('htmx:beforeRequest', htmx, { signal });
    root.__reportAuthoringExitCleanup = () => {
        window.removeEventListener('beforeunload', beforeUnload);
        document.removeEventListener('click', click, true);
        document.removeEventListener('submit', submit, true);
        document.body.removeEventListener('htmx:beforeRequest', htmx);
    };
}

function regionState(region) {
    const fragmentScript = document.getElementById(region.dataset.fragmentScriptId);
    const fragment = JSON.parse(fragmentScript?.textContent || '{"schema_version":2,"blocks":[]}');
    const surface = region.querySelector('[data-report-editor-surface]');
    surface.replaceChildren(fragmentToPreview(fragment));
    return {
        region,
        surface,
        handle: null,
        mounting: null,
        fragment: normalizeFragment(fragment),
        editId: region.dataset.editId,
        kind: region.dataset.editKind,
        existing: region.dataset.existing === 'true',
        dirty: false,
        destroyed: false,
        mountGeneration: 0,
        referenceReceipts: [],
        humanizeReferences: false,
    };
}

function resolveTarget(state) {
    const selector = state.region.querySelector('[data-report-edit-target]');
    if (!selector) {
        return {
            target: JSON.parse(state.region.dataset.targetJson || '{}'),
            expectedOriginalHash: state.region.dataset.expectedOriginalHash || null,
        };
    }
    const selected = selector.selectedOptions[0];
    if (!selected || !selected.value) return null;
    return {
        target: JSON.parse(selected.dataset.targetJson || '{}'),
        expectedOriginalHash: selected.dataset.expectedOriginalHash || null,
    };
}

function initializeAll() {
    document.querySelectorAll('[data-report-editor]').forEach(initializeReportAuthoring);
}

document.addEventListener('DOMContentLoaded', initializeAll);
document.body.addEventListener('htmx:beforeSwap', event => {
    const target = event.target;
    if (!target || !target.querySelectorAll) return;
    if (target.matches?.('[data-report-editor]')) {
        target.__reportAuthoring?.destroy();
    }
    target.querySelectorAll('[data-report-editor]').forEach(root => root.__reportAuthoring?.destroy());
});
document.body.addEventListener('htmx:afterSwap', initializeAll);

export { initializeReportAuthoring, plainTextFragment };
