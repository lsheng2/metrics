export function exportState(url, format, editor, base) {
    const disabled = { href: null, disabled: true };
    if (!['markdown', 'xlsx'].includes(format)) return disabled;
    if (editor && ['reportAuthoringDirty', 'reportAuthoringSaving', 'reportAuthoringFailed', 'reportAuthoringUncertain']
        .some(key => editor[key] === 'true')) return disabled;
    if (editor && (!/^[1-9][0-9]*$/.test(editor.revision) || !Number.isSafeInteger(Number(editor.revision)))) return disabled;
    try {
        const target = new URL(url, base);
        if (target.origin !== new URL(base).origin) return disabled;
        target.searchParams.set('format', format);
        if (editor) target.searchParams.set('revision', editor.revision);
        return { href: target.href, disabled: false };
    } catch (_) {
        return disabled;
    }
}

function sync(control) {
    const editor = control.closest('[data-report-editor]');
    const select = control.querySelector('[data-report-export-format]');
    const link = control.querySelector('[data-report-export-link]');
    const state = exportState(control.dataset.exportUrl, select.value, editor?.dataset || null, location.href);
    select.disabled = state.disabled;
    link.setAttribute('aria-disabled', String(state.disabled));
    link.tabIndex = state.disabled ? -1 : 0;
    if (state.href) link.setAttribute('href', state.href);
    else link.removeAttribute('href');
}

function initialize() {
    document.querySelectorAll('[data-report-exports]').forEach(sync);
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
    else initialize();
    document.body.addEventListener('change', event => {
        if (event.target.matches('[data-report-export-format]')) sync(event.target.closest('[data-report-exports]'));
    });
    document.body.addEventListener('htmx:afterSwap', initialize);
    for (const event of ['report-authoring-state', 'report-authoring-saved']) {
        document.body.addEventListener(event, initialize, { capture: true });
    }
}
