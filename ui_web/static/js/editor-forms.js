/*
 * Editor form state: unsaved-change tracking for [data-dirty-form] editors (banner, field
 * marking, disabled-when-clean actions, discard guard) and provider auth-mode panels that
 * enable only the fields of the selected mode.
 */

document.addEventListener('DOMContentLoaded', function() {
    function initializeDirtyForms() {
        document.querySelectorAll('[data-dirty-form]').forEach(form => {
            const banner = form.querySelector('[data-dirty-banner]');
            const cleanDisabledControls = Array.from(form.querySelectorAll('[data-disable-when-clean]'));

            function dirtyFields() {
                return Array.from(form.querySelectorAll('input[name], textarea[name], select[name]'))
                    .filter(field => (field.type !== 'hidden' || field.hasAttribute('data-dirty-track')) && field.type !== 'submit');
            }

            function setInitialFieldValue(field) {
                if (field.dataset.dirtyFieldInitialized === 'true') {
                    return;
                }
                field.dataset.initialValue = field.type === 'checkbox' ? String(field.checked) : field.value;
            }

            function markDirtyFields() {
                let formIsDirty = false;
                const dirtyShells = new Map();
                dirtyFields().forEach(field => {
                    setInitialFieldValue(field);
                    const currentValue = field.type === 'checkbox' ? String(field.checked) : field.value;
                    const fieldIsDirty = currentValue !== field.dataset.initialValue;
                    formIsDirty = formIsDirty || fieldIsDirty;
                    const fieldShell = field.closest('.provider-form-field, .scope-config-form-field, .provider-json-panel, .scope-config-form-field-wide');
                    field.classList.toggle('is-dirty-control', fieldIsDirty);
                    if (fieldShell) {
                        dirtyShells.set(fieldShell, Boolean(dirtyShells.get(fieldShell)) || fieldIsDirty);
                    }
                    const label = field.id ? form.querySelector(`label[for="${field.id}"]`) : null;
                    if (!label) {
                        return;
                    }
                    let marker = label.querySelector('[data-dirty-marker]');
                    if (fieldIsDirty && !marker) {
                        marker = document.createElement('span');
                        marker.className = 'tag is-warning dirty-marker';
                        marker.dataset.dirtyMarker = 'true';
                        marker.textContent = 'Unsaved *';
                        label.appendChild(marker);
                    }
                    if (!fieldIsDirty && marker) {
                        marker.remove();
                    }
                });
                dirtyShells.forEach((fieldIsDirty, fieldShell) => {
                    fieldShell.classList.toggle('is-dirty-field', fieldIsDirty);
                });
                if (banner) {
                    banner.classList.toggle('is-hidden', !formIsDirty);
                }
                form.dataset.dirty = String(formIsDirty);
                cleanDisabledControls.forEach(control => {
                    control.disabled = !formIsDirty;
                    control.setAttribute('aria-disabled', String(!formIsDirty));
                });
            }

            dirtyFields().forEach(field => {
                if (field.dataset.dirtyFieldInitialized === 'true') {
                    return;
                }
                setInitialFieldValue(field);
                field.dataset.dirtyFieldInitialized = 'true';
                field.addEventListener('input', markDirtyFields);
                field.addEventListener('change', markDirtyFields);
            });

            if (form.dataset.dirtyInitialized !== 'true') {
                form.dataset.dirtyInitialized = 'true';
                form.addEventListener('reset', () => {
                    window.setTimeout(() => {
                        form.querySelectorAll('[data-provider-auth-select]').forEach(select => {
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                        });
                        markDirtyFields();
                    }, 0);
                });

                form.querySelectorAll('[data-dirty-guard]').forEach(link => {
                    link.addEventListener('click', event => {
                        if (form.dataset.dirty === 'true' && !window.confirm('Discard unsaved changes?')) {
                            event.preventDefault();
                        }
                    });
                });
            }
            markDirtyFields();
        });
    }

    function initializeProviderAuthForms() {
        document.querySelectorAll('[data-provider-auth-form]').forEach(form => {
            if (form.dataset.providerAuthInitialized === 'true') {
                return;
            }
            form.dataset.providerAuthInitialized = 'true';
            const formProviderId = (form.dataset.providerId || '').trim().toLowerCase();
            const authSelect = form.querySelector('[data-provider-auth-select]');
            const panels = Array.from(form.querySelectorAll('[data-auth-modes], [data-auth-empty-panel]'));
            if (!authSelect || panels.length === 0) {
                return;
            }
            function syncAuthPanels() {
                const selectedMode = authSelect.value;
                panels.forEach(panel => {
                    const isEmptyPanel = panel.hasAttribute('data-auth-empty-panel');
                    const modes = (panel.dataset.authModes || '').split(/\s+/).filter(Boolean);
                    const providerIds = (panel.dataset.providerIds || '').split(/\s+/).filter(Boolean);
                    const providerMatches = providerIds.length === 0 || providerIds.includes(formProviderId);
                    const isActive = providerMatches && (isEmptyPanel ? !selectedMode : modes.includes(selectedMode));
                    panel.classList.toggle('is-hidden', !isActive);
                    panel.querySelectorAll('input, select, textarea').forEach(field => {
                        if (field.type !== 'hidden') {
                            field.disabled = !isActive;
                        }
                    });
                });
            }
            authSelect.addEventListener('change', syncAuthPanels);
            syncAuthPanels();
        });
    }

    function initializeEditorForms() {
        initializeDirtyForms();
        initializeProviderAuthForms();
    }

    initializeEditorForms();
    document.body.addEventListener('htmx:afterSwap', initializeEditorForms);
});
