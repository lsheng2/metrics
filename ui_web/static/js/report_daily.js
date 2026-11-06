(function () {
    const selector = '[data-report-daily-prepare-form], [data-report-reprepare-form]';

    function initialize(form) {
        if (form.dataset.dailyControlsReady === 'true') return;
        form.dataset.dailyControlsReady = 'true';
        const source = form.elements.namedItem('source_mode');
        const capture = form.elements.namedItem('capture_id');
        const analysis = form.elements.namedItem('analysis_mode');
        if (!source || !capture || !analysis) return;

        function updateModes(explicitChange) {
            const refreshing = source.value === 'refresh';
            if (explicitChange && refreshing) capture.value = '';
            if (explicitChange && !refreshing) analysis.value = 'manual_only';
            capture.disabled = refreshing && !capture.value;
            capture.required = !refreshing;
            const refreshOption = source.querySelector('option[value="refresh"]');
            const analysisOption = analysis.querySelector('option[value="changed_items"]');
            if (refreshOption) {
                refreshOption.disabled = form.dataset.runtimeReady !== 'true' && !refreshing;
            }
            if (analysisOption) {
                analysisOption.disabled = (!refreshing || form.dataset.analysisReady !== 'true')
                    && analysis.value !== 'changed_items';
            }
        }

        source.addEventListener('change', () => updateModes(true));
        analysis.addEventListener('change', () => updateModes(false));
        form.addEventListener('submit', () => {
            form.dataset.dailyBusy = 'true';
            form.setAttribute('aria-busy', 'true');
            form.querySelectorAll('button[type="submit"]').forEach(button => {
                button.dataset.dailyPreviousDisabled = String(button.disabled);
                button.disabled = true;
                button.classList.add('is-loading');
            });
        });
        updateModes(false);
    }

    function initializeAll() {
        document.querySelectorAll(selector).forEach(initialize);
    }

    window.addEventListener('pageshow', () => {
        document.querySelectorAll(selector).forEach(form => {
            if (form.dataset.dailyBusy !== 'true') return;
            form.dataset.dailyBusy = 'false';
            form.removeAttribute('aria-busy');
            form.querySelectorAll('[data-daily-previous-disabled]').forEach(button => {
                button.disabled = button.dataset.dailyPreviousDisabled === 'true';
                button.classList.remove('is-loading');
                delete button.dataset.dailyPreviousDisabled;
            });
        });
    });
    document.addEventListener('DOMContentLoaded', initializeAll);
    document.body.addEventListener('htmx:afterSwap', initializeAll);
})();
