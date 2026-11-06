export function createCompletionController(root) {
    const DISMISSED_LIMIT = 64;
    const listeners = new AbortController();
    let timer = null;
    let active = null;
    let menu = null;
    let selectedIndex = 0;
    let composing = false;
    const dismissed = new Set();

    function handleCapture(state, capture, metadata = {}) {
        if (metadata.reason === 'selection') {
            cancelActive(false, true);
            removeMenu();
            return;
        }
        if (!capture || !validToken(capture.expected_text)) {
            clearTimeout(timer);
            cancelActive(false, true);
            if (tooLongToken(capture?.expected_text)) {
                active = { state, capture, signature: stableTokenKey(capture), requestId: crypto.randomUUID(), abort: new AbortController() };
                renderShell(active, 'error', message('errorTooLong') || 'Reference id is longer than the supported 31 characters.');
            } else {
                removeMenu();
            }
            return;
        }
        const key = stableTokenKey(capture);
        if (dismissed.has(key)) {
            clearTimeout(timer);
            removeMenu();
            return;
        }
        if (active?.capture && stableTokenKey(active.capture) === key) {
            return;
        }
        clearTimeout(timer);
        cancelActive(false, true);
        active = {
            state,
            capture,
            signature: key,
            requestId: crypto.randomUUID(),
            abort: new AbortController(),
        };
        renderShell(active, 'loading', root.dataset.messageCompletionLoading || 'Checking reference...');
        timer = setTimeout(() => lookup(active), 250);
    }

    async function lookup(context) {
        try {
            const response = await fetch(root.dataset.completionUrl, {
                method: 'POST',
                credentials: 'same-origin',
                signal: context.abort.signal,
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken(root),
                },
                body: JSON.stringify(payload(context)),
            });
            const result = await response.json();
            if (!isCurrent(context)) return;
            if (!validResult(context, result)) {
                renderShell(context, 'error', errorText('COMPLETION_RESPONSE_INVALID'));
                return;
            }
            if (result.status !== 'ready') {
                renderShell(context, 'error', errorText(result.error?.code));
                return;
            }
            renderOptions(context, result.options);
        } catch (error) {
            if (error?.name !== 'AbortError' && isCurrent(context)) {
                renderShell(context, 'error', errorText('COMPLETION_NETWORK_ERROR'));
            }
        }
    }

    function payload(context) {
        return {
            request_id: context.requestId,
            token: context.capture.expected_text,
            expected_revision: Number(root.querySelector('[name="expected_revision"]').value),
            expected_revision_hash: root.querySelector('[name="expected_revision_hash"]').value,
            snapshot_hash: root.dataset.snapshotHash,
            region_target: JSON.parse(context.state.region.dataset.targetJson || '{}'),
            editor_epoch: context.capture.editor_epoch,
            local_version: context.capture.local_version,
        };
    }

    function renderShell(context, mode, text) {
        const box = ensureMenu(context);
        box.__completionContext = context;
        box.dataset.state = mode;
        box.innerHTML = '';
        const item = document.createElement('div');
        item.className = 'report-completion-message';
        item.textContent = text || '';
        box.appendChild(item);
        placeMenu(context);
    }

    function renderOptions(context, options) {
        selectedIndex = options.findIndex(option => option.enabled);
        const box = ensureMenu(context);
        box.__completionContext = context;
        box.dataset.state = 'ready';
        box.innerHTML = '';
        const list = document.createElement('div');
        list.className = 'report-completion-list';
        list.setAttribute('role', 'listbox');
        list.id = `completion-${context.requestId}`;
        box.appendChild(list);
        options.forEach((option, index) => {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'report-completion-option';
            row.id = `${list.id}-${index}`;
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', String(index === selectedIndex));
            row.disabled = !option.enabled;
            row.textContent = option.enabled ? optionText(option.fragment) : disabledText(option.disabled_reason);
            row.addEventListener('mousedown', event => event.preventDefault());
            row.addEventListener('click', () => applyOption(context, option));
            list.appendChild(row);
        });
        syncActiveDescendant(context);
        placeMenu(context);
    }

    function applyOption(context, option) {
        if (!option.enabled || !option.fragment || !option.receipt || !context.state.handle) return;
        const status = context.state.handle.applyCandidate(context.capture, { fragment: option.fragment });
        if (status === 'applied') {
            const referenceId = firstReferenceId(option.fragment);
            context.state.referenceReceipts = context.state.referenceReceipts.filter(item => item.reference_id !== referenceId);
            context.state.referenceReceipts.push({ reference_id: referenceId, receipt: option.receipt });
            close(false);
        }
    }

    function onKeydown(event) {
        if (!menu) return;
        const context = active || menu.__completionContext;
        if (!context || !context.state.region.contains(event.target)) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            close(true);
            return;
        }
        if (composing || event.isComposing) {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter') {
                event.preventDefault();
            }
            return;
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            if (menu.dataset.state !== 'ready') return;
            event.preventDefault();
            move(context, event.key === 'ArrowDown' ? 1 : -1);
            return;
        }
        if (event.key === 'Enter') {
            if (menu.dataset.state !== 'ready') {
                event.stopPropagation();
                return;
            }
            const button = menu.querySelectorAll('.report-completion-option')[selectedIndex];
            if (button && !button.disabled) {
                event.preventDefault();
                button.click();
            }
        }
    }

    function move(context, delta) {
        const options = Array.from(menu.querySelectorAll('.report-completion-option'));
        if (!options.length) return;
        let index = selectedIndex;
        for (let step = 0; step < options.length; step += 1) {
            index = (index + delta + options.length) % options.length;
            if (!options[index].disabled) {
                selectedIndex = index;
                options.forEach((option, position) => option.setAttribute('aria-selected', String(position === index)));
                syncActiveDescendant(context);
                break;
            }
        }
    }

    function ensureMenu(context) {
        if (menu?.dataset.regionId !== context.state.region.dataset.regionId) {
            removeMenu();
        }
        if (!menu) {
            menu = document.createElement('div');
            menu.className = 'report-completion-menu';
            menu.dataset.regionId = context.state.region.dataset.regionId;
            menu.setAttribute('aria-live', 'polite');
            document.body.appendChild(menu);
        }
        return menu;
    }

    function placeMenu(context) {
        if (!menu) return;
        const token = context.state.handle?.getTokenRect(context.capture);
        if (!token) return;
        const margin = 8;
        menu.style.maxHeight = `${Math.max(96, window.innerHeight - margin * 2)}px`;
        menu.style.left = '0px';
        menu.style.top = '0px';
        const rect = menu.getBoundingClientRect();
        const below = token.bottom + 6;
        const above = token.top - rect.height - 6;
        const top = below + rect.height <= window.innerHeight - margin ? below : Math.max(margin, above);
        const left = Math.min(Math.max(margin, token.left), Math.max(margin, window.innerWidth - rect.width - margin));
        menu.style.left = `${Math.round(left)}px`;
        menu.style.top = `${Math.round(top)}px`;
    }

    function syncActiveDescendant(context) {
        const editor = context.state.region.querySelector('.ProseMirror') || context.state.surface;
        const activeOption = menu?.querySelectorAll('.report-completion-option')[selectedIndex];
        if (!editor || !activeOption) return;
        editor.setAttribute('aria-controls', activeOption.parentElement.id);
        editor.setAttribute('aria-activedescendant', activeOption.id);
    }

    function clearActiveDescendant() {
        root.querySelectorAll('[aria-activedescendant]').forEach(node => {
            node.removeAttribute('aria-activedescendant');
            node.removeAttribute('aria-controls');
        });
    }

    function close(dismiss) {
        if (dismiss && active) rememberDismissed(active.signature);
        cancelActive(false, true);
        removeMenu();
    }

    function rememberDismissed(signature) {
        dismissed.add(signature);
        while (dismissed.size > DISMISSED_LIMIT) {
            dismissed.delete(dismissed.values().next().value);
        }
    }

    function cancelActive(keepMenu, abortRequest) {
        clearTimeout(timer);
        timer = null;
        if (abortRequest && active?.abort) active.abort.abort();
        active = null;
        if (!keepMenu) clearActiveDescendant();
    }

    function removeMenu() {
        if (menu) {
            menu.remove();
            menu = null;
        }
        clearActiveDescendant();
    }

    function destroy() {
        close(false);
        listeners.abort();
    }

    function isCurrent(context) {
        return active === context
            && context.state.handle?.local_version === context.capture.local_version
            && Boolean(context.state.handle?.getTokenRect(context.capture));
    }

    root.addEventListener('keydown', onKeydown, { capture: true, signal: listeners.signal });
    root.addEventListener('compositionstart', () => { composing = true; }, { capture: true, signal: listeners.signal });
    root.addEventListener('compositionend', () => { composing = false; }, { capture: true, signal: listeners.signal });
    window.addEventListener('scroll', () => { if (active) placeMenu(active); }, { capture: true, passive: true, signal: listeners.signal });
    window.addEventListener('resize', () => { if (active) placeMenu(active); }, { signal: listeners.signal });

    return { handleCapture, close, destroy };
}

export function currentReferenceReceipts(state) {
    const ids = referenceIds(state.handle ? state.handle.getFragment() : state.fragment);
    return state.referenceReceipts.filter(item => ids.has(item.reference_id)).map(item => item.receipt);
}

export function stripReferenceMetadata(fragment) {
    if (Array.isArray(fragment)) return fragment.map(stripReferenceMetadata);
    if (!fragment || typeof fragment !== 'object') return fragment;
    const result = {};
    Object.entries(fragment).forEach(([key, value]) => {
        if (key !== 'reference_id') result[key] = stripReferenceMetadata(value);
    });
    return result;
}

function validToken(token) {
    return typeof token === 'string' && (/^#[A-Z][A-Z0-9_]*-[1-9][0-9]*$/.test(token) || /^#[0-9]+$/.test(token)) && token.length <= 32;
}

function tooLongToken(token) {
    return typeof token === 'string' && token.startsWith('#') && token.length > 32;
}

function validResult(context, result) {
    if (!result || typeof result !== 'object') return false;
    if (result.request_id !== context.requestId || result.editor_epoch !== context.capture.editor_epoch) return false;
    if (result.local_version !== context.capture.local_version || result.snapshot_hash !== rootSnapshot(context)) return false;
    if (result.status === 'error') return Array.isArray(result.options) && result.options.length === 0 && result.error;
    if (result.status !== 'ready' || !Array.isArray(result.options) || result.options.length !== 3) return false;
    if (result.options.map(option => option.option_id).join(',') !== 'id,id_title,id_title_owner') return false;
    return result.options.every(option => {
        const keys = Object.keys(option).sort().join(',');
        return keys === 'disabled_reason,enabled,fragment,option_id,receipt'
            && typeof option.option_id === 'string'
            && typeof option.enabled === 'boolean'
            && (option.enabled ? option.fragment && option.receipt : option.fragment === null && option.receipt === null);
    });
}

function rootSnapshot(context) {
    return context.state.region.closest('[data-report-editor]')?.dataset.snapshotHash || '';
}

function optionText(fragment) {
    return fragment.blocks?.[0]?.content?.map(inline => {
        if (inline.type === 'link') return inline.content.map(item => item.text || '').join('');
        return inline.text || '';
    }).join('') || '';
}

function disabledText(reason) {
    return {
        unassigned: message('disabledUnassigned') || 'Unassigned owner',
        owner_unavailable: message('disabledOwner') || 'Owner unavailable',
        title_unavailable: message('disabledTitle') || 'Title unavailable',
    }[reason] || (message('disabledUnavailable') || 'Unavailable');
}

function errorText(code) {
    return {
        COMPLETION_RATE_LIMITED: message('errorRateLimited') || 'Reference lookup is rate limited; try again later.',
        COMPLETION_OUTSIDE_REPORT_SCOPE: message('errorOutsideScope') || 'Reference is outside this report scope; original text is unchanged.',
        COMPLETION_ITEM_UNAVAILABLE: message('errorUnavailable') || 'Reference is unavailable; original text is unchanged.',
        COMPLETION_PROVIDER_UNQUALIFIED: message('errorUnqualified') || 'Verified completion is not enabled for this source.',
        COMPLETION_TIMEOUT: message('errorTimeout') || 'Reference lookup timed out; original text is unchanged.',
        COMPLETION_RESPONSE_INVALID: message('errorInvalidResponse') || 'Reference lookup failed; original text is unchanged.',
    }[code] || (message('errorGeneric') || 'Reference lookup failed; original text is unchanged.');
}

function stableTokenKey(capture) {
    return JSON.stringify([
        capture.region_id,
        capture.editor_epoch,
        capture.content_version,
        capture.expected_text,
        capture.bookmark,
    ]);
}

function message(name) {
    return document.querySelector('[data-report-editor]')?.dataset[name] || '';
}

function firstReferenceId(fragment) {
    return Array.from(referenceIds(fragment))[0] || '';
}

function referenceIds(value, ids = new Set()) {
    if (Array.isArray(value)) value.forEach(item => referenceIds(item, ids));
    if (value && typeof value === 'object') {
        if (value.type === 'link' && value.reference_id) ids.add(value.reference_id);
        Object.values(value).forEach(item => referenceIds(item, ids));
    }
    return ids;
}

function csrfToken(root) {
    return root.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
}
