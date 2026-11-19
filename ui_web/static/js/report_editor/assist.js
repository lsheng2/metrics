import { fragmentToPreview } from './fragment_codec.js';

const PENDING = new Set(['prepared', 'observing', 'unknown', 'cancel_requested']);

export function createAssistController(root, { activeRegion, resolveTarget, blocked, changed }) {
    const panel = root.querySelector('[data-report-assist-dialog]');
    if (!panel) return { changed() {}, destroy() {} };
    const instruction = panel.querySelector('[data-report-assist-instruction]');
    const status = panel.querySelector('[data-report-assist-status]');
    const preview = panel.querySelector('[data-report-assist-preview]');
    const generate = panel.querySelector('[data-report-assist-generate]');
    const apply = panel.querySelector('[data-report-assist-apply]');
    const cancel = panel.querySelector('[data-report-assist-cancel]');
    const check = panel.querySelector('[data-report-assist-check]');
    const listeners = new AbortController();
    let context = null;
    let timer = null;
    let destroyed = false;

    function message(key) {
        return panel.dataset[key] || panel.dataset.failed;
    }

    function showStatus(key, error = false) {
        status.textContent = message(key);
        status.classList.toggle('is-danger', error);
    }

    function current(ctx) {
        return !destroyed && context === ctx;
    }

    function unchanged(ctx) {
        return current(ctx) && ctx.cleanAtOpen && ctx.region === activeRegion()
            && !ctx.region.destroyed && ctx.region.handle?.editor_epoch === ctx.epoch
            && ctx.region.handle?.local_version === ctx.version
            && root.dataset.revisionHash === ctx.revisionHash
            && sameTarget(resolveTarget(ctx.region)?.target, ctx.target);
    }

    function sync() {
        if (!context) return;
        generate.disabled = !context.available || blocked() || context.busy || context.pending;
        apply.disabled = !context.candidate || context.busy || applyingBlocked() || !unchanged(context);
        cancel.disabled = !context.assistId || context.busy;
        check.disabled = !context.assistId || context.busy || context.limited;
        check.hidden = !context.pending;
        apply.hidden = !context.candidate;
        preview.hidden = !context.candidate;
        position();
    }

    function applyingBlocked() {
        return root.dataset.reportAuthoringSaving === 'true' || root.dataset.reportAuthoringUncertain === 'true'
            || root.dataset.reportAuthoringFailed === 'true';
    }

    async function request(url, body) {
        const response = await fetch(url, {
            method: body ? 'POST' : 'GET',
            credentials: 'same-origin',
            signal: AbortSignal.timeout(15000),
            headers: {
                Accept: 'application/json',
                ...(body ? {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': root.querySelector('[name="csrfmiddlewaretoken"]').value,
                } : {}),
            },
            ...(body ? { body: JSON.stringify(body) } : {}),
        });
        const value = await response.json();
        if (!response.ok || value.schema_version !== 1 || !value.result || value.error) {
            throw new Error(value.error?.code || 'REPORT_AI_UNAVAILABLE');
        }
        return value.result;
    }

    function failure(error) {
        const code = error?.message;
        showStatus(code === 'REPORT_REVISION_CONFLICT' ? 'stale'
            : code === 'REPORT_EDIT_TARGET_INVALID' ? 'invalidTarget'
            : code === 'REPORT_AI_BUSY' ? 'pending'
            : code === 'REPORT_AI_UNAVAILABLE' ? 'unavailable' : 'failed', true);
    }

    async function open() {
        const region = activeRegion();
        if (!region?.handle) return;
        hide();
        const ctx = {
            region, target: resolveTarget(region)?.target,
            epoch: region.handle.editor_epoch, version: region.handle.local_version,
            revisionHash: root.dataset.revisionHash, available: false, busy: true,
            pending: false, candidate: null, assistId: null, observations: 0, cleanAtOpen: !blocked(),
        };
        context = ctx;
        panel.hidden = false;
        preview.replaceChildren();
        showStatus(blocked() ? 'saveFirst' : 'loading');
        sync();
        position();
        instruction.focus();
        try {
            const info = await request(root.dataset.assistUrl);
            if (!current(ctx)) return;
            ctx.targetId = info.targets.find(item => sameTarget(item.target, ctx.target))?.target_id;
            ctx.available = info.available && Boolean(ctx.targetId);
            showStatus(!info.available ? 'unavailable' : !ctx.targetId ? 'invalidTarget'
                : blocked() ? 'saveFirst' : 'ready');
            if (info.latest && PENDING.has(info.latest.state)) {
                ctx.assistId = info.latest.assist_id;
                ctx.pending = true;
                ctx.limited = info.latest.error_code === 'REPORT_AI_LIMIT';
                showStatus(ctx.limited ? 'limit' : info.latest.error_code === 'REPORT_AI_EXPIRED' ? 'expired' : 'pending');
            } else if (info.latest?.state === 'candidate_ready' && ctx.cleanAtOpen) {
                await acceptStatus(ctx, info.latest);
            }
        } catch (error) {
            if (current(ctx)) failure(error);
        } finally {
            if (current(ctx)) {
                ctx.busy = false;
                sync();
            }
        }
    }

    async function run() {
        const ctx = context;
        if (!ctx || generate.disabled || !instruction.reportValidity()) return;
        if (!unchanged(ctx)) {
            showStatus('stale', true);
            return;
        }
        ctx.busy = true;
        ctx.pending = true;
        ctx.candidate = null;
        ctx.commandId = crypto.randomUUID();
        showStatus('loading');
        sync();
        try {
            const value = await request(root.dataset.assistUrl, {
                command_id: ctx.commandId,
                expected_revision: Number(root.dataset.revision),
                expected_revision_hash: ctx.revisionHash,
                target_ids: [ctx.targetId],
                instruction: instruction.value,
            });
            if (current(ctx)) await acceptStatus(ctx, value);
        } catch (error) {
            if (!current(ctx)) return;
            failure(error);
            // An uncertain POST is recovered by its persisted active key, never resubmitted.
            try {
                const info = await request(root.dataset.assistUrl);
                if (current(ctx) && info.latest) {
                    ctx.assistId = info.latest.assist_id;
                    ctx.pending = PENDING.has(info.latest.state);
                }
            } catch (_) { /* Keep generation blocked until observation is possible. */ }
        } finally {
            if (current(ctx)) {
                ctx.busy = false;
                sync();
            }
        }
    }

    async function acceptStatus(ctx, value) {
        if (!current(ctx)) return;
        ctx.assistId = value.assist_id;
        ctx.pending = PENDING.has(value.state);
        ctx.limited = value.error_code === 'REPORT_AI_LIMIT';
        if (value.state === 'candidate_ready') {
            const candidate = await request(`${root.dataset.assistUrl}${ctx.assistId}/candidate/`);
            if (!current(ctx)) return;
            const targets = candidate.targets;
            if (!Array.isArray(targets) || targets.length !== 1 || targets[0].target_id !== ctx.targetId) {
                showStatus('invalidTarget', true);
                return;
            }
            ctx.candidate = targets[0].fragment;
            preview.replaceChildren(fragmentToPreview(ctx.candidate));
            showStatus(unchanged(ctx) ? 'candidateReady' : 'stale', !unchanged(ctx));
        } else if (ctx.pending) {
            const expired = value.error_code === 'REPORT_AI_EXPIRED';
            showStatus(ctx.limited ? 'limit' : expired ? 'expired' : 'pending');
            if (ctx.observations < 12 && !ctx.limited && !expired && value.state !== 'cancel_requested') {
                clearTimeout(timer);
                timer = setTimeout(observe, 2000);
            }
        } else {
            showStatus(value.state === 'insufficient_evidence' ? 'insufficient'
                : value.state === 'canceled' ? 'canceled' : 'failed', value.state === 'failed');
        }
    }

    async function observe() {
        const ctx = context;
        if (!ctx?.assistId || ctx.busy) return;
        clearTimeout(timer);
        ctx.busy = true;
        ctx.observations += 1;
        sync();
        try {
            await acceptStatus(ctx, await request(`${root.dataset.assistUrl}${ctx.assistId}/`));
        } catch (error) {
            if (current(ctx)) failure(error);
        } finally {
            if (current(ctx)) {
                ctx.busy = false;
                sync();
            }
        }
    }

    function applyCandidate() {
        const ctx = context;
        if (!ctx?.candidate || !unchanged(ctx) || ctx.busy || applyingBlocked()) {
            showStatus('stale', true);
            return;
        }
        if (ctx.region.handle.replaceFragment(ctx.version, ctx.candidate) !== 'applied') {
            showStatus('stale', true);
            return;
        }
        ctx.region.assistReceiptId = ctx.assistId;
        ctx.region.dirty = true;
        changed();
        hide();
    }

    async function reject() {
        const ctx = context;
        if (!ctx?.assistId || ctx.busy) return;
        clearTimeout(timer);
        ctx.busy = true;
        ctx.candidate = null;
        sync();
        try {
            await request(`${root.dataset.assistUrl}${ctx.assistId}/cancel/`, { command_id: crypto.randomUUID() });
            if (current(ctx)) hide();
        } catch (error) {
            if (current(ctx)) failure(error);
        } finally {
            if (current(ctx)) {
                ctx.busy = false;
                sync();
            }
        }
    }

    function hide() {
        clearTimeout(timer);
        context = null;
        panel.hidden = true;
    }

    function position() {
        if (!context) return;
        const footer = document.querySelector('[data-workbench-status-bar]');
        const bottom = Math.min(window.innerHeight, footer?.getBoundingClientRect().top ?? window.innerHeight);
        panel.style.maxHeight = `${Math.max(1, bottom - 16)}px`;
        const rect = context.region.surface.getBoundingClientRect();
        const box = panel.getBoundingClientRect();
        panel.style.left = `${Math.max(8, Math.min(rect.right - box.width, window.innerWidth - box.width - 8))}px`;
        panel.style.top = `${Math.max(8, Math.min(rect.bottom + 6, bottom - box.height - 8))}px`;
    }

    function editorChanged() {
        if (context?.candidate && !unchanged(context)) showStatus('stale', true);
        sync();
    }

    const { signal } = listeners;
    const opener = root.querySelector('[data-report-assist-open]');
    opener.addEventListener('mousedown', event => event.preventDefault(), { signal });
    opener.addEventListener('click', open, { signal });
    generate.addEventListener('click', run, { signal });
    apply.addEventListener('click', applyCandidate, { signal });
    cancel.addEventListener('click', reject, { signal });
    check.addEventListener('click', observe, { signal });
    panel.querySelector('[data-report-assist-close]').addEventListener('click', hide, { signal });
    panel.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); hide(); }
    }, { signal });
    root.addEventListener('report-authoring-state', editorChanged, { signal });
    window.addEventListener('resize', position, { signal });
    window.addEventListener('scroll', position, { capture: true, passive: true, signal });
    return { changed: editorChanged, destroy() { destroyed = true; hide(); listeners.abort(); } };
}

function sameTarget(left, right) {
    return Boolean(left && right) && Object.keys(left).length === Object.keys(right).length
        && Object.keys(left).every(key => left[key] === right[key]);
}
