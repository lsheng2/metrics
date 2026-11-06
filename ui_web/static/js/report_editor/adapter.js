import { fragmentText, normalizeFragment } from './fragment_codec.js';

export async function mount(element, { fragment, onDirty, onCompletionToken, readOnly } = {}) {
    if (!element) {
        throw new Error('editor element is required');
    }
    const runtimeFactory = globalThis.ReportMilkdownEditor?.createRuntime;
    if (typeof runtimeFactory !== 'function') {
        throw new Error('report editor runtime is unavailable');
    }
    let handle;
    const runtime = await runtimeFactory(element, normalizeFragment(fragment || { schema_version: 2, blocks: [] }), {
        readOnly: Boolean(readOnly),
        onChange() {
            if (handle) {
                handle._changedFromRuntime();
            }
        },
        onSelectionChange() {
            if (handle) {
                handle._selectionChanged();
            }
        },
    });
    handle = createEditorHandle(runtime, element.dataset.regionId || '', {
        onDirty,
        initialFragment: normalizeFragment(fragment || { schema_version: 2, blocks: [] }),
        onCompletionToken,
    });
    return handle;
}

export function createEditorHandle(runtime, regionId, { onDirty, initialFragment, onCompletionToken } = {}) {
    let localVersion = 0;
    let contentVersion = 0;
    let dirty = false;
    let destroyed = false;
    let suppressRuntimeChange = false;
    const editorEpoch = cryptoValue();
    let lastSelectionSignature = selectionSignature();
    function currentFragment() {
        return normalizeFragment(runtime.getFragment());
    }

    function markDirty() {
        dirty = true;
        if (typeof onDirty === 'function') {
            onDirty(true, currentFragment());
        }
    }

    function changedFromRuntime() {
        if (destroyed || suppressRuntimeChange) {
            return;
        }
        localVersion += 1;
        contentVersion += 1;
        lastSelectionSignature = selectionSignature();
        markDirty();
        notifyCompletionToken(captureToken(), { reason: 'content' });
    }

    function replaceRuntime(fragment) {
        suppressRuntimeChange = true;
        try {
            runtime.replaceFragment(normalizeFragment(fragment));
        } finally {
            suppressRuntimeChange = false;
        }
    }

    function notifyCompletionToken(capture, metadata) {
        if (typeof onCompletionToken === 'function') {
            onCompletionToken(capture, metadata);
        }
    }

    function selectionChanged() {
        if (destroyed || suppressRuntimeChange) {
            return;
        }
        const nextSelectionSignature = selectionSignature();
        if (nextSelectionSignature !== null && nextSelectionSignature === lastSelectionSignature) {
            return;
        }
        lastSelectionSignature = nextSelectionSignature;
        localVersion += 1;
        notifyCompletionToken(captureToken(), { reason: 'selection' });
    }

    function captureToken() {
        if (destroyed || typeof runtime.findToken !== 'function') {
            return null;
        }
        const token = runtime.findToken();
        if (!token) {
            return null;
        }
        return {
            editor_epoch: editorEpoch,
            region_id: regionId,
            local_version: localVersion,
            content_version: contentVersion,
            bookmark: token.bookmark || { from: token.from, to: token.to },
            expected_text: token.text,
            selection_location: selectionLocation(),
        };
    }

    function captureIsCurrent(capture) {
        if (destroyed || !capture || capture.editor_epoch !== editorEpoch || capture.region_id !== regionId) {
            return false;
        }
        if (capture.local_version !== localVersion) {
            return false;
        }
        if (!sameSelectionLocation(capture.selection_location)) {
            return false;
        }
        const activeText = typeof runtime.textForBookmark === 'function'
            ? runtime.textForBookmark(capture.bookmark)
            : fragmentText(currentFragment()).slice(capture.bookmark.from, capture.bookmark.to);
        return activeText === capture.expected_text;
    }

    function selectionLocation() {
        if (typeof runtime.selectionLocation !== 'function') {
            return null;
        }
        const location = runtime.selectionLocation();
        if (!location || typeof location !== 'object') {
            return null;
        }
        return { from: Number(location.from), to: Number(location.to) };
    }

    function selectionSignature() {
        if (typeof runtime.selectionLocation !== 'function') {
            return null;
        }
        return JSON.stringify(selectionLocation());
    }

    function sameSelectionLocation(expected) {
        if (!expected || typeof runtime.selectionLocation !== 'function') {
            return true;
        }
        return JSON.stringify(expected) === JSON.stringify(selectionLocation());
    }

    return {
        get editor_epoch() {
            return editorEpoch;
        },
        get local_version() {
            return localVersion;
        },
        get content_version() {
            return contentVersion;
        },
        get dirty() {
            return dirty;
        },
        getFragment() {
            if (destroyed) {
                return { schema_version: 2, blocks: [] };
            }
            return currentFragment();
        },
        captureToken() {
            return captureToken();
        },
        getTokenRect(capture) {
            if (!captureIsCurrent(capture) || typeof runtime.rectForBookmark !== 'function') {
                return null;
            }
            return runtime.rectForBookmark(capture.bookmark);
        },
        applyCandidate(capture, candidate) {
            if (!captureIsCurrent(capture)) {
                return 'stale';
            }
            const replacement = typeof candidate === 'string' ? candidate : candidate?.text;
            const replacementFragment = candidate?.fragment || null;
            if (!replacementFragment && typeof replacement !== 'string') {
                return 'stale';
            }
            if (!capture.expected_text || !capture.expected_text.startsWith('#')) {
                return 'stale';
            }
            suppressRuntimeChange = true;
            let applied = false;
            try {
                if (typeof runtime.replaceBookmark === 'function') {
                    applied = runtime.replaceBookmark(capture.bookmark, replacementFragment || replacement);
                } else {
                    runtime.replaceText(capture.bookmark.from, capture.bookmark.to, replacement);
                    applied = true;
                }
            } finally {
                suppressRuntimeChange = false;
            }
            if (!applied) {
                return 'stale';
            }
            localVersion += 1;
            contentVersion += 1;
            lastSelectionSignature = selectionSignature();
            markDirty();
            notifyCompletionToken(null, { reason: 'content' });
            return 'applied';
        },
        replaceFragment(expectedLocalVersion, fragment) {
            if (destroyed || expectedLocalVersion !== localVersion) {
                return 'stale';
            }
            replaceRuntime(fragment);
            localVersion += 1;
            contentVersion += 1;
            lastSelectionSignature = selectionSignature();
            markDirty();
            notifyCompletionToken(null, { reason: 'content' });
            return 'applied';
        },
        command(command, value) {
            if (destroyed || typeof runtime.command !== 'function') {
                return false;
            }
            return Boolean(runtime.command(command, value));
        },
        pasteHtml(html) {
            if (destroyed || typeof runtime.pasteHtml !== 'function') {
                return '';
            }
            return runtime.pasteHtml(html);
        },
        clearReferenceIds() {
            if (destroyed || typeof runtime.clearReferenceIds !== 'function') {
                return false;
            }
            suppressRuntimeChange = true;
            try {
                if (!runtime.clearReferenceIds()) {
                    return false;
                }
            } finally {
                suppressRuntimeChange = false;
            }
            localVersion += 1;
            contentVersion += 1;
            lastSelectionSignature = selectionSignature();
            markDirty();
            notifyCompletionToken(null, { reason: 'content' });
            return true;
        },
        markSaved(fragment) {
            if (destroyed) {
                return;
            }
            replaceRuntime(fragment);
            localVersion += 1;
            contentVersion += 1;
            lastSelectionSignature = selectionSignature();
            dirty = false;
            if (typeof onDirty === 'function') {
                onDirty(false, currentFragment());
            }
            notifyCompletionToken(null, { reason: 'content' });
        },
        destroy() {
            if (destroyed) {
                return;
            }
            destroyed = true;
            if (typeof runtime.destroy === 'function') {
                runtime.destroy();
            }
        },
        _changedFromRuntime: changedFromRuntime,
        _selectionChanged: selectionChanged,
    };
}

function cryptoValue() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `epoch-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
