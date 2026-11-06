(function() {
    function initializeReportEditor(root) {
        if (!root || root.dataset.reportEditorInitialized === 'true') {
            return;
        }
        root.dataset.reportEditorInitialized = 'true';

        const form = root.querySelector('[data-report-save-form]');
        const dirtyFields = Array.from(root.querySelectorAll('[data-report-dirty-field]'));
        const dirtyBanner = root.querySelector('[data-report-dirty-banner]');
        const copyButton = root.querySelector('[data-report-copy-button]');
        const finalizeButton = root.querySelector('[data-report-finalize-button]');
        const status = root.querySelector('[data-report-copy-status]');
        const languageForms = Array.from(root.querySelectorAll('form[action*="projects/language"]'));
        const authoredMode = Boolean(root.querySelector('[data-report-authored-form]'));
        let payload = null;
        let dirty = false;

        function setStatus(message, kind) {
            if (!status) {
                return;
            }
            status.textContent = message;
            status.classList.toggle('is-danger', kind === 'error');
            status.classList.toggle('is-success', kind === 'success');
            status.classList.toggle('is-light', !kind);
        }

        function currentValues() {
            return JSON.stringify(dirtyFields.map(field => ({
                name: field.name || '',
                type: field.type || '',
                checked: field.type === 'checkbox' ? Boolean(field.checked) : null,
                value: field.type === 'checkbox' ? '' : field.value
            })));
        }

        const initialValues = currentValues();

        function authoredBlocked() {
            return root.dataset.reportAuthoringDirty === 'true'
                || root.dataset.reportAuthoringSaving === 'true'
                || root.dataset.reportAuthoringFailed === 'true'
                || root.dataset.reportAuthoringUncertain === 'true';
        }

        function syncButtons() {
            dirty = currentValues() !== initialValues || authoredBlocked();
            if (dirtyBanner) {
                dirtyBanner.classList.toggle('is-hidden', !dirty);
            }
            if (copyButton) {
                const canCopy = Boolean(payload) && !dirty && payload.clipboard_available && !authoredBlocked();
                copyButton.disabled = !canCopy;
                copyButton.setAttribute('aria-disabled', String(!canCopy));
            }
            if (finalizeButton && !finalizeButton.hasAttribute('data-server-disabled')) {
                finalizeButton.disabled = dirty;
                finalizeButton.setAttribute('aria-disabled', String(dirty));
            }
        }

        async function sha256Hex(text) {
            if (!window.crypto || !window.crypto.subtle || typeof TextEncoder === 'undefined') {
                throw new Error('hash unavailable');
            }
            const data = new TextEncoder().encode(text);
            const digest = await window.crypto.subtle.digest('SHA-256', data);
            return Array.from(new Uint8Array(digest))
                .map(value => value.toString(16).padStart(2, '0'))
                .join('');
        }

        async function validPayload(value) {
            const structureMatches = value
                && value.schema_version === 1
                && value.draft_id === root.dataset.draftId
                && String(value.revision) === String(root.dataset.revision)
                && value.revision_hash === root.dataset.revisionHash
                && value.snapshot_hash === root.dataset.snapshotHash
                && value.template_hash === root.dataset.templateHash
                && typeof value.html_fragment === 'string'
                && typeof value.plain_text === 'string'
                && typeof value.html_sha256 === 'string'
                && typeof value.plain_sha256 === 'string'
                && typeof value.clipboard_available === 'boolean';
            if (!structureMatches) {
                return false;
            }
            const htmlHash = await sha256Hex(value.html_fragment);
            const plainHash = await sha256Hex(value.plain_text);
            return htmlHash === value.html_sha256 && plainHash === value.plain_sha256;
        }

        async function loadClipboardPayload() {
            const url = root.dataset.clipboardUrl;
            if (!url) {
                setStatus(root.dataset.messagePayloadMissing, 'error');
                syncButtons();
                return;
            }
            try {
                const response = await window.fetch(url, {
                    credentials: 'same-origin',
                    headers: { 'Accept': 'application/json' }
                });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const value = await response.json();
                if (!await validPayload(value)) {
                    throw new Error('revision mismatch');
                }
                payload = value;
                setStatus(root.dataset.messageReady, null);
            } catch (error) {
                payload = null;
                setStatus(root.dataset.messageDownloadFallback, 'error');
            }
            syncButtons();
        }

        function applySavedRevision(event) {
            const detail = event.detail || {};
            payload = null;
            if (detail.revision !== undefined) {
                root.dataset.revision = String(detail.revision);
            }
            if (detail.revision_hash) {
                root.dataset.revisionHash = detail.revision_hash;
            }
            if (detail.snapshot_hash) {
                root.dataset.snapshotHash = detail.snapshot_hash;
            }
            if (detail.template_hash) {
                root.dataset.templateHash = detail.template_hash;
            }
            if (detail.clipboard_url) {
                root.dataset.clipboardUrl = detail.clipboard_url;
            }
            syncButtons();
            loadClipboardPayload();
        }

        async function copyReport() {
            if (!payload || dirty) {
                setStatus(root.dataset.messageSaveBeforeCopy, 'error');
                syncButtons();
                return;
            }
            if (!navigator.clipboard || typeof ClipboardItem === 'undefined') {
                setStatus(root.dataset.messageNativeUnavailable, 'error');
                return;
            }
            try {
                const item = new ClipboardItem({
                    'text/html': new Blob([payload.html_fragment], { type: 'text/html' }),
                    'text/plain': new Blob([payload.plain_text], { type: 'text/plain' })
                });
                await navigator.clipboard.write([item]);
                setStatus(root.dataset.messageCopied, 'success');
            } catch (error) {
                setStatus(root.dataset.messageCopyFailed, 'error');
            }
        }

        dirtyFields.forEach(field => {
            field.addEventListener('input', syncButtons);
            field.addEventListener('change', syncButtons);
        });
        if (copyButton) {
            copyButton.addEventListener('click', copyReport);
        }
        if (form) {
            form.addEventListener('submit', () => {
                if (copyButton) {
                    copyButton.disabled = true;
                }
            });
        }
        root.addEventListener('report-authoring-state', syncButtons);
        root.addEventListener('report-authoring-saved', applySavedRevision);
        if (!authoredMode) {
            languageForms.forEach(languageForm => {
                languageForm.addEventListener('submit', event => {
                    if (dirty) {
                        event.preventDefault();
                        setStatus(root.dataset.messageSaveBeforeCopy, 'error');
                    }
                });
            });
        }
        syncButtons();
        loadClipboardPayload();
    }

    function initializeAllReportEditors() {
        document.querySelectorAll('[data-report-editor]').forEach(initializeReportEditor);
    }

    document.addEventListener('DOMContentLoaded', initializeAllReportEditors);
    document.body.addEventListener('htmx:afterSwap', initializeAllReportEditors);
})();
