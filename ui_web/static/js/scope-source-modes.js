/*
 * Scope editor source modes: shows the panel of the selected source mode and keeps the
 * query-builder preview in sync with its fields.
 */

document.addEventListener('DOMContentLoaded', function() {
    function initializeScopeSourceModes() {
        document.querySelectorAll('[data-source-mode-root]').forEach(root => {
            const options = Array.from(root.querySelectorAll('[data-source-mode-option]'));
            const panels = Array.from(root.querySelectorAll('[data-source-mode-panel]'));
            if (!options.length || !panels.length) {
                return;
            }

            function uniqueValues(values) {
                return values
                    .map(value => value.trim())
                    .filter((value, index, normalizedValues) => value && normalizedValues.indexOf(value) === index);
            }

            function textValues(value) {
                return String(value || '')
                    .replace(/\r\n/g, '\n')
                    .replace(/\r/g, '\n')
                    .split(/[\n,]/);
            }

            function fieldValues(field) {
                if (field.type === 'checkbox' || field.type === 'radio') {
                    return field.checked ? [field.value] : [];
                }
                if (field.tagName === 'SELECT' && field.multiple) {
                    return Array.from(field.selectedOptions).map(option => option.value);
                }
                if (field.tagName === 'SELECT') {
                    return field.value ? [field.value] : [];
                }
                return textValues(field.value);
            }

            function listValues(name) {
                const fields = Array.from(root.querySelectorAll(`[name="${name}"]`));
                if (!fields.length) {
                    return [];
                }
                return uniqueValues(fields.flatMap(fieldValues));
            }

            function combinedListValues(name) {
                return uniqueValues(listValues(name).concat(listValues(`${name}_manual`)));
            }

            function firstValue(name) {
                const values = listValues(name);
                return values.length ? values[0] : '';
            }

            function quoteJqlValue(value) {
                return /^[A-Za-z0-9_.-]+$/.test(value)
                    ? value
                    : `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
            }

            function jqlClause(fieldName, values) {
                if (!fieldName || !values.length) {
                    return '';
                }
                if (values.length === 1) {
                    return `${fieldName} = ${quoteJqlValue(values[0])}`;
                }
                return `${fieldName} in (${values.map(quoteJqlValue).join(', ')})`;
            }

            function syncQueryBuilderPreview() {
                const preview = root.querySelector('#query-builder-preview');
                if (!preview) {
                    return;
                }
                const clauses = [];
                const project = root.querySelector('[name="query_builder_project"]');
                if (project && project.value.trim()) {
                    clauses.push(jqlClause('project', [project.value.trim()]));
                }
                [
                    ['query_builder_issue_types', 'issuetype'],
                    ['query_builder_components', 'components'],
                    ['query_builder_affected_versions', 'versions'],
                    ['query_builder_fix_versions', 'fixVersions'],
                    ['query_builder_priorities', 'priority'],
                    ['query_builder_resolutions', 'resolution'],
                    ['query_builder_security_levels', 'security'],
                    ['query_builder_labels', 'labels'],
                ].forEach(([name, fieldName]) => {
                    const clause = jqlClause(fieldName, combinedListValues(name));
                    if (clause) {
                        clauses.push(clause);
                    }
                });
                [1, 2, 3, 4, 5, 6].forEach(index => {
                    const fieldName = firstValue(`query_builder_custom_field_${index}_manual`) || firstValue(`query_builder_custom_field_${index}`);
                    const clause = jqlClause(fieldName, listValues(`query_builder_custom_values_${index}`));
                    if (clause) {
                        clauses.push(clause);
                    }
                });
                preview.value = clauses.length ? clauses.join(' AND ') : 'No Query Builder filters selected.';
            }

            function syncSourcePanels() {
                const activeOption = options.find(option => option.checked) || options[0];
                const activeMode = activeOption.value;
                panels.forEach(panel => {
                    const isActive = panel.dataset.sourceModePanel === activeMode;
                    panel.hidden = !isActive;
                    panel.classList.toggle('is-inactive', !isActive);
                    panel.querySelectorAll('[data-source-mode-input]').forEach(field => {
                        field.disabled = !isActive;
                    });
                });
                syncQueryBuilderPreview();
            }

            if (root.dataset.sourceModeInitialized !== 'true') {
                options.forEach(option => {
                    option.addEventListener('change', syncSourcePanels);
                });
                root.dataset.sourceModeInitialized = 'true';
            }
            root.querySelectorAll('[name^="query_builder_"]').forEach(field => {
                if (field.dataset.queryBuilderPreviewInitialized === 'true') {
                    return;
                }
                field.dataset.queryBuilderPreviewInitialized = 'true';
                field.addEventListener('input', syncQueryBuilderPreview);
                field.addEventListener('change', syncQueryBuilderPreview);
            });
            syncSourcePanels();
        });
    }

    initializeScopeSourceModes();
    document.body.addEventListener('htmx:afterSwap', initializeScopeSourceModes);
});
