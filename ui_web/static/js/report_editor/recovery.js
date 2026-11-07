import { canRestoreRecovery, createCheckpointWriter } from './recovery_state.js';

export function createRecoveryController(root, { capture, restore, blocked }) {
    const host = root.querySelector('[data-report-recovery]');
    if (!host || !root.dataset.recoveryUrl) return { changed() {}, async saved() {}, destroy() {} };
    const url = root.dataset.recoveryUrl;
    const status = host.querySelector('[data-recovery-status]');
    const choices = host.querySelector('[data-recovery-choices]');
    const restoreButton = host.querySelector('[data-recovery-restore]');
    const discardButton = host.querySelector('[data-recovery-discard]');
    const downloadButton = host.querySelector('[data-recovery-download]');
    const clientId = crypto.randomUUID();
    let receipt = null, loaded = [], restoring = false, destroyed = false, restoredFrom = null;
    const events = new AbortController();
    const binding = () => ({
        revision: Number(root.dataset.revision), revisionHash: root.dataset.revisionHash,
        snapshotHash: root.dataset.snapshotHash, templateHash: root.dataset.templateHash,
    });
    const message = (name, fallback) => host.dataset[name] || fallback;
    const setStatus = value => { if (!destroyed) status.textContent = value; };
    async function request(target, payload) {
        const csrf = root.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
        const response = await fetch(target, {
            method: payload === undefined ? 'GET' : 'POST', credentials: 'same-origin',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
            signal: AbortSignal.timeout(8000),
        });
        const value = await response.json();
        if (!response.ok || value.error) throw new Error(value.error?.code || 'RECOVERY_FAILED');
        return value.result;
    }
    function syncButtons() {
        const item = loaded.find(value => value.client_id === choices.value);
        restoreButton.disabled = !item || blocked() || restoring || !canRestoreRecovery(item, binding());
        discardButton.disabled = !item || restoring;
        downloadButton.disabled = !item || restoring;
    }
    async function refresh() {
        try {
            loaded = await request(url);
            if (destroyed) return;
            choices.replaceChildren();
            loaded.sort((a, b) => b.saved_at.localeCompare(a.saved_at)).forEach(item => {
                const option = document.createElement('option');
                option.value = item.client_id;
                option.textContent = `${item.saved_at} / r${item.base_revision}${item.restorable ? '' : ' *'}`;
                choices.append(option);
            });
            choices.hidden = loaded.length === 0;
            syncButtons();
            if (loaded.length) setStatus(message('messageAvailable', 'Recovery checkpoint available.'));
        } catch {
            setStatus(message('messageFailed', 'Recovery unavailable; newer edits are not protected.'));
        }
    }
    const writer = createCheckpointWriter({
        capture: async () => {
            if (restoring || destroyed) return null;
            const content = await capture();
            if (!content) return null;
            const base = binding();
            return { client_id: clientId, base_revision: base.revision, base_revision_hash: base.revisionHash,
                snapshot_hash: base.snapshotHash, template_hash: base.templateHash, content };
        },
        put: payload => request(url, payload),
        saved: value => {
            receipt = value;
            root.dataset.recoverySequence = String(value.sequence);
            setStatus(`${message('messageCheckpoint', 'Recovery checkpoint')}: ${value.saved_at}`);
        },
        failed: () => setStatus(message('messageFailed', 'Recovery unavailable; newer edits are not protected.')),
    });
    const on = (node, type, handler) => node.addEventListener(type, handler, { signal: events.signal });
    on(choices, 'change', syncButtons);
    on(root, 'report-authoring-state', syncButtons);
    on(restoreButton, 'click', async () => {
        if (blocked() || restoring) return;
        restoring = true; syncButtons();
        try {
            const item = await request(`${url}${choices.value}/`);
            if (!canRestoreRecovery(item, binding())) throw new Error('RECOVERY_CONFLICT');
            await restore(item.content);
            restoredFrom = item;
            setStatus(message('messageRestored', 'Recovered edits are unsaved.'));
        } catch {
            setStatus(message('messageConflict', 'Recovery conflicts with this revision. Download the checkpoint to reconcile.'));
        } finally { restoring = false; syncButtons(); }
    });
    on(discardButton, 'click', async () => {
        const item = loaded.find(value => value.client_id === choices.value);
        if (!item) return;
        try {
            await request(`${url}${item.client_id}/`, { expected_sequence: item.sequence });
            await refresh();
            setStatus(message('messageDiscarded', 'Recovery checkpoint discarded.'));
        } catch { setStatus(message('messageFailed', 'Recovery request failed.')); }
    });
    on(downloadButton, 'click', async () => {
        try {
            const item = await request(`${url}${choices.value}/`);
            const href = URL.createObjectURL(new Blob([JSON.stringify(item, null, 2)], { type: 'application/json' }));
            const anchor = document.createElement('a');
            anchor.href = href; anchor.download = `report-recovery-${item.client_id}.json`; anchor.click();
            setTimeout(() => URL.revokeObjectURL(href), 1000);
        } catch { setStatus(message('messageFailed', 'Recovery request failed.')); }
    });
    refresh();
    return {
        changed() { if (!restoring) writer.changed(); },
        async saved() {
            await writer.stop();
            for (const item of [receipt, restoredFrom].filter(Boolean)) {
                try { await request(`${url}${item.client_id}/`, { expected_sequence: item.sequence }); } catch { /* A newer checkpoint remains intact. */ }
            }
            receipt = restoredFrom = null;
        },
        resume() { writer.resume(); writer.changed(); },
        destroy() { destroyed = true; events.abort(); writer.stop(); },
    };
}
