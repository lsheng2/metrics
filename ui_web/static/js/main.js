function initializeTaskForecastToggles() {
    document.querySelectorAll('.task-toggle').forEach(button => {
        button.addEventListener('click', function() {
            const parentLevel = parseInt(this.getAttribute('data-parent-level'));
            const parentRow = this.closest('tr');
            const icon = this.querySelector('i[class*="iconoir"]');
            
            let currentRow = parentRow.nextElementSibling;
            const childRows = [];
            
            while (currentRow) {
                const rowLevel = parseInt(currentRow.getAttribute('data-level'));
                
                if (rowLevel <= parentLevel) {
                    break;
                }
                
                if (rowLevel > parentLevel) {
                    childRows.push(currentRow);
                }
                
                currentRow = currentRow.nextElementSibling;
            }
            
            const isExpanded = icon.classList.contains('iconoir-nav-arrow-down');
            
            childRows.forEach(row => {
                if (isExpanded) {
                    row.classList.add('is-hidden');
                    const childButton = row.querySelector('.task-toggle');
                    const childToggle = childButton ? childButton.querySelector('i[class*="iconoir"]') : null;
                    if (childButton) {
                        childButton.setAttribute('aria-expanded', 'false');
                    }
                    if (childToggle && childToggle.classList.contains('iconoir-nav-arrow-down')) {
                        childToggle.className = 'iconoir-nav-arrow-right';
                    }
                } else {
                    const rowLevel = parseInt(row.getAttribute('data-level'));
                    if (rowLevel === parentLevel + 1) {
                        row.classList.remove('is-hidden');
                    }
                }
            });
            
            if (icon) {
                icon.className = isExpanded ? 'iconoir-nav-arrow-right' : 'iconoir-nav-arrow-down';
            }
            this.setAttribute('aria-expanded', String(!isExpanded));
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    
    function handleMenuToggle(e) {
        e.preventDefault();
        
        const targetId = this.getAttribute('data-target');
        const submenu = document.getElementById(targetId);
        
        if (submenu) {
            const isHidden = submenu.classList.contains('is-hidden');
            
            if (isHidden) {
                submenu.classList.remove('is-hidden');
                this.setAttribute('aria-expanded', 'true');
            } else {
                submenu.classList.add('is-hidden');
                this.setAttribute('aria-expanded', 'false');
            }
        }
    }
    
    function setActiveMenuItem(clickedElement) {
        if (!clickedElement || clickedElement.tagName !== 'A' || !clickedElement.closest('.menu-list')) {
            return;
        }
        
        document.querySelectorAll('.menu-list .is-active').forEach(item => {
            item.classList.remove('is-active');
        });
        
        clickedElement.classList.add('is-active');
        
        const parentSubmenu = clickedElement.closest('.menu-submenu');
        if (parentSubmenu) {
            parentSubmenu.classList.remove('is-hidden');
            
            const submenuId = parentSubmenu.getAttribute('id');
            const toggle = document.querySelector(`[data-target="${submenuId}"]`);
            if (toggle) {
                toggle.classList.add('is-active');
                toggle.setAttribute('aria-expanded', 'true');
            }
        }
    }
    
    function expandInitialActiveMenus() {
        const activeMenus = document.querySelectorAll('.menu-list .is-active');
        activeMenus.forEach(activeItem => {
            const parentSubmenu = activeItem.closest('.menu-submenu');
            if (parentSubmenu) {
                parentSubmenu.classList.remove('is-hidden');
                
                const submenuId = parentSubmenu.getAttribute('id');
                const toggle = document.querySelector(`[data-target="${submenuId}"]`);
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'true');
                }
            }
        });
    }

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
                        marker.className = 'tag is-warning is-light dirty-marker';
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

    function initializeRequiredForms() {
        document.querySelectorAll('[data-required-form]').forEach(form => {
            if (form.dataset.requiredInitialized === 'true') {
                return;
            }
            form.dataset.requiredInitialized = 'true';

            const defaultActions = requiredActionList(form.dataset.requiredActions);
            const fields = () => Array.from(form.querySelectorAll('input[name], textarea[name], select[name]'))
                .filter(field => field.type !== 'hidden' && field.type !== 'submit' && field.type !== 'button' && field.type !== 'reset');

            function requiredActionList(value) {
                return String(value || '').split(/\s+/).filter(Boolean);
            }

            function submitterAction(submitter) {
                if (!submitter) {
                    return '';
                }
                const name = submitter.getAttribute('name') || '';
                return name === 'action' ? submitter.value : '';
            }

            function fieldActions(field) {
                const explicitActions = requiredActionList(field.dataset.requiredActions);
                if (explicitActions.length) {
                    return explicitActions;
                }
                if (field.required || field.hasAttribute('aria-required')) {
                    return defaultActions;
                }
                return [];
            }

            function actionMatches(actions, action) {
                if (!actions.length) {
                    return false;
                }
                return actions.includes('*') || actions.includes(action);
            }

            function isVisibleControl(field) {
                if (field.disabled) {
                    return false;
                }
                if (field.offsetParent !== null) {
                    return true;
                }
                return Boolean(field.getClientRects().length);
            }

            function hasFieldValue(field) {
                if (field.type === 'checkbox' || field.type === 'radio') {
                    return field.checked;
                }
                if (field.type === 'file') {
                    return field.files && field.files.length > 0;
                }
                if (field.tagName === 'SELECT' && field.multiple) {
                    return Array.from(field.selectedOptions).some(option => option.value.trim());
                }
                return String(field.value || '').trim().length > 0;
            }

            function fieldLabel(field) {
                const label = field.id ? form.querySelector(`label[for="${field.id}"]`) : null;
                if (field.dataset.requiredLabel) {
                    return field.dataset.requiredLabel;
                }
                if (!label) {
                    return field.name || 'This field';
                }
                const clone = label.cloneNode(true);
                clone.querySelectorAll('.tag, .help-tip, [data-dirty-marker]').forEach(node => node.remove());
                return clone.textContent.trim() || field.name || 'This field';
            }

            function fieldShell(field) {
                return field.closest('.dashboard-form-field, .provider-form-field, .scope-config-form-field, .provider-json-panel, .scope-config-form-field-wide') || field.closest('.field') || field.parentElement;
            }

            function describedByTokens(field) {
                return String(field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
            }

            function messageId(field) {
                const base = field.id || field.name || 'required-field';
                return `${base}-required-message`;
            }

            function clearRequiredState(field) {
                const shell = fieldShell(field);
                field.classList.remove('is-required-missing-control');
                field.removeAttribute('aria-invalid');
                const tokens = describedByTokens(field).filter(token => token !== messageId(field));
                if (tokens.length) {
                    field.setAttribute('aria-describedby', tokens.join(' '));
                } else {
                    field.removeAttribute('aria-describedby');
                }
                if (shell) {
                    shell.classList.remove('is-missing-required');
                    const message = shell.querySelector(`[data-required-message-for="${field.name}"]`);
                    if (message) {
                        message.remove();
                    }
                }
            }

            function showRequiredState(field) {
                const shell = fieldShell(field);
                const id = messageId(field);
                const label = fieldLabel(field);
                const messageText = field.dataset.requiredMessage || `${label} is required.`;
                field.classList.add('is-required-missing-control');
                field.setAttribute('aria-invalid', 'true');
                const tokens = new Set(describedByTokens(field));
                tokens.add(id);
                field.setAttribute('aria-describedby', Array.from(tokens).join(' '));
                if (!shell) {
                    return;
                }
                shell.classList.add('is-missing-required');
                let message = shell.querySelector(`[data-required-message-for="${field.name}"]`);
                if (!message) {
                    message = document.createElement('p');
                    message.className = 'dashboard-required-message';
                    message.dataset.requiredMessageFor = field.name;
                    message.id = id;
                    shell.appendChild(message);
                }
                message.textContent = messageText;
            }

            function requiredCandidates(action) {
                return fields().filter(field => {
                    if (!isVisibleControl(field)) {
                        return false;
                    }
                    return actionMatches(fieldActions(field), action);
                });
            }

            function missingFieldsForAction(action) {
                const candidates = requiredCandidates(action);
                const groupValues = new Map();
                candidates.forEach(field => {
                    const group = field.dataset.requiredGroup || '';
                    if (group) {
                        groupValues.set(group, Boolean(groupValues.get(group)) || hasFieldValue(field));
                    }
                });
                return candidates.filter(field => {
                    const group = field.dataset.requiredGroup || '';
                    if (group) {
                        return !groupValues.get(group);
                    }
                    return !hasFieldValue(field);
                });
            }

            function syncRequiredState(action, focusFirstMissing) {
                const candidates = requiredCandidates(action);
                const missing = missingFieldsForAction(action);
                const missingSet = new Set(missing);
                candidates.forEach(field => {
                    if (missingSet.has(field)) {
                        showRequiredState(field);
                    } else {
                        clearRequiredState(field);
                    }
                });
                fields()
                    .filter(field => !candidates.includes(field))
                    .forEach(clearRequiredState);

                const summary = form.querySelector('[data-required-summary]');
                if (summary) {
                    summary.classList.toggle('is-hidden', missing.length === 0);
                    summary.textContent = missing.length
                        ? (summary.dataset.requiredSummary || 'Fill the highlighted required fields before continuing.')
                        : '';
                }
                form.dataset.requiredInvalid = String(missing.length > 0);
                form.dataset.lastRequiredAction = action;

                if (missing.length && focusFirstMissing) {
                    const firstField = missing[0];
                    const shell = fieldShell(firstField);
                    if (shell) {
                        shell.scrollIntoView({ block: 'center', behavior: 'smooth' });
                    }
                    firstField.focus({ preventScroll: true });
                }
                return missing.length === 0;
            }

            form.addEventListener('submit', event => {
                const action = submitterAction(event.submitter);
                if (!actionMatches(defaultActions, action)) {
                    return;
                }
                if (!syncRequiredState(action, true)) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            }, true);

            fields().forEach(field => {
                field.addEventListener('input', () => {
                    if (form.dataset.requiredInvalid === 'true') {
                        syncRequiredState(form.dataset.lastRequiredAction || '', false);
                    }
                });
                field.addEventListener('change', () => {
                    if (form.dataset.requiredInvalid === 'true') {
                        syncRequiredState(form.dataset.lastRequiredAction || '', false);
                    }
                });
            });
        });
    }

    function initializeConfirmForms() {
        document.querySelectorAll('form[data-confirm]').forEach(form => {
            form.addEventListener('submit', event => {
                const message = form.dataset.confirm;
                if (message && !window.confirm(message)) {
                    event.preventDefault();
                    return;
                }
                const confirmationField = form.querySelector('input[name="delete_confirmation"]');
                if (!confirmationField) {
                    return;
                }
                const expectedConfirmation = (form.dataset.confirmToken || confirmationField.getAttribute('placeholder') || '').trim();
                if (!expectedConfirmation || confirmationField.value.trim() === expectedConfirmation) {
                    confirmationField.value = confirmationField.value.trim();
                    return;
                }
                const providedConfirmation = window.prompt(
                    `Permanent delete requires a typed confirmation.\n\nType the exact text below into the input box, then click OK:\n\n${expectedConfirmation}\n\nDeletion will not continue unless the text matches exactly.`,
                    confirmationField.value.trim()
                );
                if (providedConfirmation === null) {
                    event.preventDefault();
                    return;
                }
                confirmationField.value = providedConfirmation.trim();
                if (confirmationField.value !== expectedConfirmation) {
                    event.preventDefault();
                    confirmationField.focus();
                }
            });
        });
    }

    function initializeSearchablePickupLists() {
        document.querySelectorAll('[data-searchable-pickup-list]').forEach(pickupList => {
            if (pickupList.dataset.searchablePickupInitialized === 'true') {
                return;
            }
            pickupList.dataset.searchablePickupInitialized = 'true';
            const valueInput = pickupList.querySelector('[data-searchable-pickup-value-input]');
            const toggle = pickupList.querySelector('[data-searchable-pickup-toggle]');
            const label = pickupList.querySelector('[data-searchable-pickup-label]');
            const menu = pickupList.querySelector('[data-searchable-pickup-menu]');
            const search = pickupList.querySelector('[data-searchable-pickup-search]');
            const emptyMessage = pickupList.querySelector('[data-searchable-pickup-empty]');
            const options = Array.from(pickupList.querySelectorAll('[data-searchable-pickup-option]'));
            if (!valueInput || !toggle || !label || !menu || !search || !options.length) {
                return;
            }

            function setOpen(isOpen) {
                const shouldOpen = isOpen && !toggle.disabled;
                menu.hidden = !shouldOpen;
                toggle.setAttribute('aria-expanded', String(shouldOpen));
                pickupList.classList.toggle('is-open', shouldOpen);
                if (shouldOpen) {
                    search.value = '';
                    filterOptions();
                    window.setTimeout(() => search.focus(), 0);
                }
            }

            function normalizedText(value) {
                return String(value || '').trim().toLowerCase();
            }

            function filterOptions() {
                const query = normalizedText(search.value);
                let visibleCount = 0;
                options.forEach(option => {
                    const isPlaceholder = option.dataset.searchablePickupValue === '';
                    const text = normalizedText(option.dataset.searchablePickupSearchText || option.textContent);
                    const isVisible = query ? !isPlaceholder && text.includes(query) : true;
                    option.hidden = !isVisible;
                    if (isVisible) {
                        visibleCount += 1;
                    }
                });
                if (emptyMessage) {
                    emptyMessage.hidden = visibleCount > 0;
                }
            }

            function selectOption(option) {
                valueInput.value = option.dataset.searchablePickupValue || '';
                label.textContent = option.dataset.searchablePickupLabel || option.textContent.trim();
                options.forEach(candidate => {
                    candidate.setAttribute('aria-selected', String(candidate === option));
                });
                valueInput.dispatchEvent(new Event('input', { bubbles: true }));
                valueInput.dispatchEvent(new Event('change', { bubbles: true }));
                setOpen(false);
                toggle.focus();
            }

            toggle.addEventListener('click', event => {
                event.preventDefault();
                setOpen(menu.hidden);
            });
            search.addEventListener('input', filterOptions);
            search.addEventListener('keydown', event => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    setOpen(false);
                    toggle.focus();
                    return;
                }
                if (event.key === 'Enter') {
                    const firstVisibleOption = options.find(option => !option.hidden);
                    if (firstVisibleOption) {
                        event.preventDefault();
                        selectOption(firstVisibleOption);
                    }
                }
            });
            options.forEach(option => {
                option.addEventListener('click', () => selectOption(option));
            });
            document.addEventListener('click', event => {
                if (!pickupList.contains(event.target)) {
                    setOpen(false);
                }
            });
        });
    }

    function initializeSearchableValuePickers() {
        document.querySelectorAll('[data-searchable-value-picker]').forEach(picker => {
            if (picker.dataset.searchableValuePickerInitialized === 'true') {
                return;
            }
            picker.dataset.searchableValuePickerInitialized = 'true';
            const input = picker.querySelector('[data-searchable-value-picker-input]');
            const toggle = picker.querySelector('[data-searchable-value-picker-toggle]');
            const menu = picker.querySelector('[data-searchable-value-picker-menu]');
            const search = picker.querySelector('[data-searchable-value-picker-search]');
            const emptyMessage = picker.querySelector('[data-searchable-value-picker-empty]');
            const status = picker.querySelector('[data-searchable-value-picker-status]');
            if (!input || !toggle || !menu || !search) {
                return;
            }

            function optionNodes() {
                return Array.from(picker.querySelectorAll('[data-searchable-value-picker-option]'));
            }

            function normalizedText(value) {
                return String(value || '').trim().toLowerCase();
            }

            function valueTokens(value) {
                return String(value || '')
                    .replace(/\r\n/g, '\n')
                    .replace(/\r/g, '\n')
                    .split(/[\n,]/)
                    .map(token => token.trim())
                    .filter((token, index, tokens) => token && tokens.indexOf(token) === index);
            }

            function writeTokens(tokens) {
                input.value = picker.dataset.searchableValuePickerMode === 'multi' ? tokens.join('\n') : (tokens[0] || '');
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                syncSelectedOptions();
            }

            function syncSelectedOptions() {
                const selectedLookup = new Set(valueTokens(input.value).map(value => value.toLowerCase()));
                optionNodes().forEach(option => {
                    option.setAttribute('aria-selected', String(selectedLookup.has(normalizedText(option.dataset.searchableValuePickerValue))));
                });
            }

            function filterOptions() {
                const query = normalizedText(search.value);
                let visibleCount = 0;
                optionNodes().forEach(option => {
                    const text = normalizedText(option.dataset.searchableValuePickerSearchText || option.textContent);
                    const isVisible = query ? text.includes(query) : true;
                    option.hidden = !isVisible;
                    if (isVisible) {
                        visibleCount += 1;
                    }
                });
                if (emptyMessage) {
                    emptyMessage.hidden = visibleCount > 0;
                }
            }

            function setOpen(isOpen) {
                const shouldOpen = isOpen && !toggle.disabled;
                menu.hidden = !shouldOpen;
                toggle.setAttribute('aria-expanded', String(shouldOpen));
                picker.classList.toggle('is-open', shouldOpen);
                if (shouldOpen) {
                    search.value = '';
                    filterOptions();
                    syncSelectedOptions();
                    window.setTimeout(() => search.focus(), 0);
                }
            }

            function setRefreshing() {
                picker.classList.add('is-refreshing');
                if (status) {
                    status.textContent = 'Refreshing metadata...';
                }
            }

            function selectOption(option) {
                const value = option.dataset.searchableValuePickerValue || '';
                if (!value) {
                    return;
                }
                if (picker.dataset.searchableValuePickerMode === 'multi') {
                    const existingTokens = valueTokens(input.value);
                    if (!existingTokens.some(token => token.toLowerCase() === value.toLowerCase())) {
                        existingTokens.push(value);
                    }
                    writeTokens(existingTokens);
                } else {
                    writeTokens([value]);
                    setOpen(false);
                    toggle.focus();
                }
            }

            toggle.addEventListener('click', event => {
                if (toggle.hasAttribute('hx-get')) {
                    setRefreshing();
                    if (optionNodes().length) {
                        setOpen(menu.hidden);
                    }
                    return;
                }
                event.preventDefault();
                setOpen(menu.hidden);
            });
            search.addEventListener('input', filterOptions);
            search.addEventListener('keydown', event => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    setOpen(false);
                    toggle.focus();
                    return;
                }
                if (event.key === 'Enter') {
                    const firstVisibleOption = optionNodes().find(option => !option.hidden);
                    if (firstVisibleOption) {
                        event.preventDefault();
                        selectOption(firstVisibleOption);
                    }
                }
            });
            optionNodes().forEach(option => {
                option.addEventListener('click', () => selectOption(option));
            });
            input.addEventListener('input', syncSelectedOptions);
            input.addEventListener('change', syncSelectedOptions);
            document.addEventListener('click', event => {
                if (!picker.contains(event.target)) {
                    setOpen(false);
                }
            });
            syncSelectedOptions();
            if (picker.classList.contains('is-open') || !menu.hidden) {
                setOpen(true);
            }
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
                options.forEach(option => {
                    const label = option.closest('label.button');
                    if (label) {
                        label.classList.toggle('is-primary', option.value === activeMode);
                        label.classList.toggle('is-selected', option.value === activeMode);
                    }
                });
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

    const workbenchLastUrlKey = 'metricsWorkbench.lastUrl';
    const workbenchStateParams = [
        'scope_id',
        'range_mode',
        'begin',
        'end',
        'chart_id',
        'chart_version',
        'run',
        'snapshot',
        'bucket',
        'series',
    ];

    function normalizedWorkbenchUrl(rawUrl) {
        try {
            const url = new URL(rawUrl, window.location.origin);
            if (url.origin !== window.location.origin || url.pathname !== '/workbench/' || !url.search) {
                return '';
            }
            return `${url.pathname}${url.search}`;
        } catch (error) {
            return '';
        }
    }

    function isMeaningfulWorkbenchUrl(rawUrl) {
        const normalizedUrl = normalizedWorkbenchUrl(rawUrl);
        if (!normalizedUrl) {
            return false;
        }
        const url = new URL(normalizedUrl, window.location.origin);
        return workbenchStateParams.some(param => Boolean(url.searchParams.get(param)));
    }

    function storedWorkbenchUrl() {
        try {
            const storedUrl = window.localStorage.getItem(workbenchLastUrlKey);
            return isMeaningfulWorkbenchUrl(storedUrl) ? normalizedWorkbenchUrl(storedUrl) : '';
        } catch (error) {
            return '';
        }
    }

    function updateWorkbenchNavigationLinks() {
        const restoredUrl = storedWorkbenchUrl();
        document.querySelectorAll('[data-workbench-nav-link]').forEach(link => {
            link.href = restoredUrl || '/workbench/';
        });
    }

    function saveCurrentWorkbenchUrl() {
        const currentUrl = `${window.location.pathname}${window.location.search}`;
        if (!isMeaningfulWorkbenchUrl(currentUrl)) {
            updateWorkbenchNavigationLinks();
            return;
        }
        try {
            window.localStorage.setItem(workbenchLastUrlKey, normalizedWorkbenchUrl(currentUrl));
        } catch (error) {
            return;
        }
        updateWorkbenchNavigationLinks();
    }

    function workbenchAiBaseOrigin() {
        const contextNode = document.getElementById('workbench-ai-context');
        if (!contextNode) {
            return '';
        }
        try {
            const context = JSON.parse(contextNode.textContent || '{}');
            const frontendUrl = context.ai_base && context.ai_base.frontend_url;
            return frontendUrl ? new URL(frontendUrl, window.location.origin).origin : '';
        } catch (error) {
            return '';
        }
    }

    function workbenchUrlFromHostAction(request) {
        const payload = request && request.payload ? request.payload : {};
        const explicitUrl = payload.workbenchUrl || request.fallbackUrl;
        const normalizedExplicitUrl = explicitUrl ? normalizedWorkbenchUrl(explicitUrl) : '';
        if (normalizedExplicitUrl) {
            return normalizedExplicitUrl;
        }
        const params = new URLSearchParams(window.location.search);
        ['chartId', 'panelId', 'dashboardUid'].forEach(key => {
            if (!payload[key]) {
                return;
            }
            const queryKey = key === 'chartId'
                ? 'chart_id'
                : key === 'panelId'
                    ? 'panel_id'
                    : 'dashboard_uid';
            params.set(queryKey, String(payload[key]));
        });
        return `${window.location.pathname}?${params.toString()}`;
    }

    function acknowledgeHostAction(event, request, status, result) {
        if (!event.source || !request) {
            return;
        }
        event.source.postMessage({
            type: 'ai-base.host-action.result',
            result: {
                sourceAppId: request.sourceAppId,
                bindingKey: request.bindingKey,
                sessionId: request.sessionId,
                requestId: request.requestId,
                artifactId: request.artifactId || null,
                correlationId: request.correlationId,
                idempotencyKey: request.idempotencyKey,
                status: status,
                result: result,
            },
        }, event.origin);
    }

    function handleWorkbenchHostAction(event, payload) {
        const aiBaseOrigin = workbenchAiBaseOrigin();
        if (!aiBaseOrigin || event.origin !== aiBaseOrigin) {
            return false;
        }
        const request = payload.request || {};
        if (request.sourceAppId !== 'metrics-dashboard' || request.actionKind !== 'metrics.openGrafanaChart') {
            acknowledgeHostAction(event, request, 'rejected', { reason: 'unsupported_action' });
            return true;
        }
        const url = workbenchUrlFromHostAction(request);
        if (!isMeaningfulWorkbenchUrl(url)) {
            acknowledgeHostAction(event, request, 'failed', { reason: 'invalid_workbench_url' });
            return true;
        }
        if (window.htmx) {
            htmx.ajax('GET', url, {
                target: '.workbench-shell',
                select: '.workbench-shell',
                swap: 'outerHTML'
            });
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
            acknowledgeHostAction(event, request, 'handled', { openedIn: 'metrics-workbench.chart', url: url });
        } else {
            window.location.assign(url);
        }
        return true;
    }

    function workbenchToolbarUrl(form) {
        const action = form.getAttribute('hx-get') || form.getAttribute('action') || window.location.pathname;
        const url = new URL(action, window.location.origin);
        const params = new URLSearchParams(new FormData(form));
        url.search = params.toString();
        return `${url.pathname}${url.search}`;
    }

    function refreshWorkbenchFromToolbar(form) {
        const url = workbenchToolbarUrl(form);
        if (window.htmx) {
            htmx.ajax('GET', url, {
                target: '.workbench-shell',
                select: '.workbench-shell',
                swap: 'outerHTML'
            });
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
            return;
        }
        window.location.assign(url);
    }

    function closeWorkbenchMenus(exceptMenu) {
        document.querySelectorAll('.workbench-menu[open]').forEach(menu => {
            if (menu !== exceptMenu) {
                menu.open = false;
            }
        });
    }

    function initializeDismissibleWorkbenchMenus() {
        if (document.body.dataset.workbenchMenuDismissInitialized === 'true') {
            return;
        }
        document.body.dataset.workbenchMenuDismissInitialized = 'true';
        document.addEventListener('click', event => {
            const clickedMenu = event.target.closest('.workbench-menu');
            if (clickedMenu) {
                closeWorkbenchMenus(clickedMenu);
                return;
            }
            closeWorkbenchMenus(null);
        });
        document.addEventListener('keydown', event => {
            if (event.key !== 'Escape') {
                return;
            }
            closeWorkbenchMenus(null);
        });
    }

    function initializeDashboardSidebarSplitter() {
        const layout = document.querySelector('[data-dashboard-layout]');
        const sidebar = document.querySelector('[data-dashboard-sidebar]');
        const splitter = document.querySelector('[data-dashboard-sidebar-splitter]');
        if (!layout || !sidebar || !splitter || splitter.dataset.dashboardSidebarInitialized === 'true') {
            return;
        }
        splitter.dataset.dashboardSidebarInitialized = 'true';
        const storageKey = 'metricsDashboard.sidebarWidth';
        const minWidth = 168;
        const maxWidth = 360;

        function applySidebarWidth(width) {
            const next = Math.max(minWidth, Math.min(maxWidth, width));
            layout.style.setProperty('--dashboard-sidebar-width', `${next}px`);
            try {
                window.localStorage.setItem(storageKey, `${next}px`);
            } catch (error) {
                return;
            }
        }

        try {
            const savedWidth = parseInt(window.localStorage.getItem(storageKey));
            if (savedWidth) {
                applySidebarWidth(savedWidth);
            }
        } catch (error) {
            return;
        }

        splitter.addEventListener('dblclick', function() {
            layout.style.removeProperty('--dashboard-sidebar-width');
            try {
                window.localStorage.removeItem(storageKey);
            } catch (error) {
                return;
            }
        });
        splitter.addEventListener('keydown', function(event) {
            if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) {
                return;
            }
            event.preventDefault();
            const current = Math.round(sidebar.getBoundingClientRect().width) || 248;
            applySidebarWidth(current + (event.key === 'ArrowLeft' ? -16 : 16));
        });
        splitter.addEventListener('pointerdown', function(event) {
            event.preventDefault();
            const onPointerMove = moveEvent => {
                const layoutRect = layout.getBoundingClientRect();
                applySidebarWidth(Math.round(moveEvent.clientX - layoutRect.left));
            };
            const onPointerUp = () => {
                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
            };
            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', onPointerUp, { once: true });
        });
    }

    function initializeWorkbenchShell() {
        updateWorkbenchNavigationLinks();
        initializeDashboardSidebarSplitter();
        if (document.querySelector('.workbench-shell')) {
            saveCurrentWorkbenchUrl();
        }

        const workbenchGrid = document.getElementById('workbench-grid');
        const aiRailWidth = 40;
        const minExpandedAiWidth = 280;
        const maxExpandedAiWidth = 600;
        function normalizeWorkbenchAiWidth(width) {
            const numericWidth = Number.parseInt(width);
            if (!numericWidth || numericWidth <= aiRailWidth || numericWidth < minExpandedAiWidth) {
                return aiRailWidth;
            }
            return Math.min(maxExpandedAiWidth, numericWidth);
        }
        function syncWorkbenchCollapseState(paneName, isCollapsed) {
            const pane = document.querySelector(`[data-workbench-pane="${paneName}"]`);
            const button = document.querySelector(`[data-workbench-collapse="${paneName}"]`);
            if (pane) {
                pane.classList.toggle('is-collapsed', isCollapsed);
            }
            if (!button) {
                return;
            }
            button.setAttribute('aria-expanded', String(!isCollapsed));
            if (paneName === 'ai-assistant') {
                button.textContent = isCollapsed ? 'AI' : 'Collapse';
                button.setAttribute('aria-label', isCollapsed ? 'Expand AI assistant' : 'Collapse AI assistant');
                return;
            }
            button.textContent = isCollapsed ? 'Expand' : 'Collapse';
        }
        function setWorkbenchAiCollapsed(isCollapsed, width) {
            if (!workbenchGrid) {
                return;
            }
            const normalizedWidth = width
                ? normalizeWorkbenchAiWidth(width)
                : isCollapsed ? aiRailWidth : 340;
            const shouldCollapse = isCollapsed || normalizedWidth === aiRailWidth;
            workbenchGrid.classList.toggle('is-ai-collapsed', shouldCollapse);
            workbenchGrid.style.setProperty('--workbench-ai-width', `${normalizedWidth}px`);
            syncWorkbenchCollapseState('ai-assistant', shouldCollapse);
        }
        function setWorkbenchChartCollapsed(isCollapsed, height) {
            if (!workbenchGrid) {
                return;
            }
            workbenchGrid.classList.toggle('is-chart-collapsed', isCollapsed);
            workbenchGrid.style.setProperty('--workbench-chart-height', height || (isCollapsed ? '3.15rem' : '38vh'));
            syncWorkbenchCollapseState('chart', isCollapsed);
        }
        if (workbenchGrid && workbenchGrid.dataset.workbenchLayoutInitialized !== 'true') {
            workbenchGrid.dataset.workbenchLayoutInitialized = 'true';
            const savedAiWidth = window.localStorage.getItem('metricsWorkbench.aiWidth');
            const savedChartHeight = window.localStorage.getItem('metricsWorkbench.chartHeight');
            let aiCollapsed = false;
            let chartCollapsed = false;
            if (savedAiWidth) {
                const migratedAiWidth = savedAiWidth === '44px' ? '40px' : savedAiWidth;
                const normalizedAiWidth = normalizeWorkbenchAiWidth(migratedAiWidth);
                aiCollapsed = normalizedAiWidth === aiRailWidth;
                setWorkbenchAiCollapsed(aiCollapsed, `${normalizedAiWidth}px`);
                if (`${normalizedAiWidth}px` !== savedAiWidth) {
                    window.localStorage.setItem('metricsWorkbench.aiWidth', `${normalizedAiWidth}px`);
                }
            }
            if (savedChartHeight) {
                chartCollapsed = savedChartHeight === '3.15rem';
                setWorkbenchChartCollapsed(chartCollapsed, savedChartHeight);
            }
            syncWorkbenchCollapseState('ai-assistant', aiCollapsed);
            syncWorkbenchCollapseState('chart', chartCollapsed);
        }

        if (document.querySelector('.workbench-shell') && !window.metricsWorkbenchInitialScrollGuardRegistered) {
            window.metricsWorkbenchInitialScrollGuardRegistered = true;
            let userMovedViewport = false;
            ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(eventName => {
                window.addEventListener(eventName, function() {
                    userMovedViewport = true;
                }, { once: true, passive: true });
            });
            [0, 250, 750, 1500, 3000].forEach(delay => {
                window.setTimeout(function() {
                    if (!userMovedViewport && window.scrollY > 8 && window.scrollY < 480) {
                        window.scrollTo(window.scrollX, 0);
                    }
                }, delay);
            });
        }

        document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
            if (frame.dataset.workbenchScrollGuardInitialized === 'true') {
                return;
            }
            frame.dataset.workbenchScrollGuardInitialized = 'true';
            const initialScrollY = window.scrollY;
            frame.addEventListener('load', function() {
                frame.dataset.workbenchAiLoaded = 'true';
                if (initialScrollY <= 8 && window.scrollY > 8 && window.scrollY < 480) {
                    window.scrollTo(window.scrollX, initialScrollY);
                }
            });
        });

        document.querySelectorAll('[data-workbench-splitter]').forEach(splitter => {
            if (splitter.dataset.workbenchInitialized === 'true') {
                return;
            }
            splitter.dataset.workbenchInitialized = 'true';
            splitter.addEventListener('dblclick', function() {
                if (this.dataset.workbenchSplitter === 'main-ai' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-ai-width');
                    workbenchGrid.classList.remove('is-ai-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.aiWidth');
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence' && workbenchGrid) {
                    workbenchGrid.style.removeProperty('--workbench-chart-height');
                    workbenchGrid.classList.remove('is-chart-collapsed');
                    window.localStorage.removeItem('metricsWorkbench.chartHeight');
                }
            });
            splitter.addEventListener('keydown', function(event) {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
                    return;
                }
                event.preventDefault();
                if (!workbenchGrid) {
                    return;
                }
                const gridRect = workbenchGrid.getBoundingClientRect();
                if (this.dataset.workbenchSplitter === 'main-ai') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-ai-width')) || 340;
                    const delta = event.key === 'ArrowLeft' ? 16 : event.key === 'ArrowRight' ? -16 : 0;
                    const candidate = current <= aiRailWidth && delta > 0 ? 340 : current + delta;
                    const next = normalizeWorkbenchAiWidth(candidate);
                    setWorkbenchAiCollapsed(next === aiRailWidth, `${next}px`);
                    window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                }
                if (this.dataset.workbenchSplitter === 'chart-evidence') {
                    const current = parseInt(getComputedStyle(workbenchGrid).getPropertyValue('--workbench-chart-height')) || Math.round(gridRect.height * 0.55);
                    const delta = event.key === 'ArrowUp' ? -16 : event.key === 'ArrowDown' ? 16 : 0;
                    const next = Math.max(50, Math.min(gridRect.height - 240, current + delta));
                    setWorkbenchChartCollapsed(next <= 52, `${next}px`);
                    window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                }
            });
            splitter.addEventListener('pointerdown', function(event) {
                if (!workbenchGrid) {
                    return;
                }
                event.preventDefault();
                const splitterKind = this.dataset.workbenchSplitter;
                const gridRect = workbenchGrid.getBoundingClientRect();
                const evidenceLayout = this.closest('[data-workbench-evidence-layout]');
                const evidenceRect = evidenceLayout ? evidenceLayout.getBoundingClientRect() : null;
                const onPointerMove = moveEvent => {
                    if (splitterKind === 'main-ai') {
                        const next = normalizeWorkbenchAiWidth(Math.round(gridRect.right - moveEvent.clientX));
                        setWorkbenchAiCollapsed(next === aiRailWidth, `${next}px`);
                        window.localStorage.setItem('metricsWorkbench.aiWidth', `${next}px`);
                    }
                    if (splitterKind === 'chart-evidence') {
                        const next = Math.max(50, Math.min(gridRect.height - 240, Math.round(moveEvent.clientY - gridRect.top)));
                        setWorkbenchChartCollapsed(next <= 52, `${next}px`);
                        window.localStorage.setItem('metricsWorkbench.chartHeight', `${next}px`);
                    }
                    if (splitterKind === 'ticket-detail' && evidenceLayout && evidenceRect) {
                        const next = Math.max(180, Math.min(360, Math.round(evidenceRect.right - moveEvent.clientX)));
                        evidenceLayout.style.setProperty('--workbench-ticket-detail-width', `${next}px`);
                    }
                };
                const onPointerUp = () => {
                    window.removeEventListener('pointermove', onPointerMove);
                    window.removeEventListener('pointerup', onPointerUp);
                };
                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp, { once: true });
            });
        });

        document.querySelectorAll('[data-workbench-collapse]').forEach(button => {
            if (button.dataset.workbenchInitialized === 'true') {
                return;
            }
            button.dataset.workbenchInitialized = 'true';
            button.addEventListener('click', function() {
                const pane = document.querySelector(`[data-workbench-pane="${this.dataset.workbenchCollapse}"]`);
                if (!pane) {
                    return;
                }
                const wasCollapsed = pane.classList.contains('is-collapsed')
                    || (workbenchGrid && this.dataset.workbenchCollapse === 'ai-assistant' && workbenchGrid.classList.contains('is-ai-collapsed'))
                    || (workbenchGrid && this.dataset.workbenchCollapse === 'chart' && workbenchGrid.classList.contains('is-chart-collapsed'));
                const isCollapsed = !wasCollapsed;
                if (workbenchGrid && this.dataset.workbenchCollapse === 'ai-assistant') {
                    setWorkbenchAiCollapsed(isCollapsed);
                    window.localStorage.setItem('metricsWorkbench.aiWidth', isCollapsed ? '40px' : '340px');
                }
                if (workbenchGrid && this.dataset.workbenchCollapse === 'chart') {
                    setWorkbenchChartCollapsed(isCollapsed);
                    window.localStorage.setItem('metricsWorkbench.chartHeight', isCollapsed ? '3.15rem' : '38vh');
                }
                syncWorkbenchCollapseState(this.dataset.workbenchCollapse, isCollapsed);
            });
        });

        const scopeSelect = document.querySelector('[data-workbench-state-trigger="scope"]');
        if (scopeSelect && scopeSelect.dataset.workbenchScopeSyncInitialized !== 'true') {
            scopeSelect.dataset.workbenchScopeSyncInitialized = 'true';
            scopeSelect.addEventListener('change', function() {
                const selected = this.selectedOptions && this.selectedOptions.length ? this.selectedOptions[0] : null;
                const profileId = selected ? selected.dataset.profileId || '' : '';
                const providerId = selected ? selected.dataset.providerId || '' : '';
                const profileField = document.getElementById('workbench-profile');
                const providerField = document.getElementById('workbench-provider');
                if (profileField && profileId) {
                    profileField.value = profileId;
                }
                if (providerField) {
                    providerField.value = providerId;
                }
                const toolbar = this.closest('form');
                if (toolbar) {
                    refreshWorkbenchFromToolbar(toolbar);
                }
            });
        }

        document.querySelectorAll('[data-workbench-evidence-workspace]').forEach(workspace => {
            if (workspace.dataset.workbenchInitialized === 'true') {
                return;
            }
            workspace.dataset.workbenchInitialized = 'true';
            const table = workspace.querySelector('[data-workbench-evidence-table]');
            const selectedCount = workspace.querySelector('[data-workbench-ticket-selected-count]');
            const selectAll = workspace.querySelector('[data-workbench-ticket-select-all]');
            const ticketBoxes = Array.from(workspace.querySelectorAll('[data-workbench-ticket-checkbox]'));
            const detail = workspace.querySelector('[data-workbench-ticket-detail]');
            const detailEmpty = workspace.querySelector('[data-ticket-detail-empty]');
            const detailContent = workspace.querySelector('[data-ticket-detail-content]');
            const layout = workspace.querySelector('[data-workbench-evidence-layout]');
            function setDetailText(selector, value) {
                const node = workspace.querySelector(selector);
                if (node) {
                    node.textContent = value || '-';
                }
            }
            function openDetail() {
                if (layout) {
                    layout.classList.remove('is-detail-collapsed');
                }
                if (detailEmpty) {
                    detailEmpty.classList.add('is-hidden');
                }
                if (detailContent) {
                    detailContent.classList.remove('is-hidden');
                }
            }
            function selectedTicketPayloads() {
                return ticketBoxes
                    .filter(box => box.checked)
                    .map(box => box.closest('[data-workbench-ticket-row]'))
                    .filter(row => row)
                    .map(row => ({
                        issueKey: row.dataset.issueKey || '',
                        summary: row.dataset.summary || '',
                        series: row.dataset.series || '',
                        status: row.dataset.status || '',
                        severity: row.dataset.severity || '',
                        owner: row.dataset.owner || '',
                        component: row.dataset.component || '',
                        created: row.dataset.created || '',
                        updated: row.dataset.updated || '',
                    }));
            }
            function notifyAiSelectedTickets() {
                const selectedTickets = selectedTicketPayloads();
                const payload = {
                    selectedTicketCount: selectedTickets.length,
                    truncated: selectedTickets.length > 50,
                    tickets: selectedTickets.slice(0, 50),
                };
                window.metricsWorkbenchSelectedTickets = payload;
                document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
                    if (!frame.contentWindow || !frame.src) {
                        return;
                    }
                    if (frame.dataset.workbenchAiLoaded !== 'true') {
                        return;
                    }
                    let targetOrigin = window.location.origin;
                    try {
                        targetOrigin = new URL(frame.src).origin;
                    } catch (error) {
                        targetOrigin = window.location.origin;
                    }
                    frame.contentWindow.postMessage({
                        type: 'metrics-workbench:selected-tickets',
                        source: 'metrics-workbench',
                        selectedTicketCount: payload.selectedTicketCount,
                        truncated: payload.truncated,
                        selectedTickets: payload.tickets,
                    }, targetOrigin);
                });
            }
            document.querySelectorAll('.workbench-ai-chat-frame').forEach(frame => {
                if (frame.dataset.workbenchTicketNotifyInitialized === 'true') {
                    return;
                }
                frame.dataset.workbenchTicketNotifyInitialized = 'true';
                frame.addEventListener('load', notifyAiSelectedTickets);
            });
            function updateSelectedCount() {
                const count = ticketBoxes.filter(box => box.checked).length;
                if (selectedCount) {
                    selectedCount.textContent = `${count} selected`;
                }
                if (selectAll) {
                    selectAll.checked = count > 0 && count === ticketBoxes.length;
                    selectAll.indeterminate = count > 0 && count < ticketBoxes.length;
                }
                notifyAiSelectedTickets();
            }
            if (selectAll) {
                selectAll.addEventListener('change', function() {
                    ticketBoxes.forEach(box => {
                        box.checked = this.checked;
                    });
                    updateSelectedCount();
                });
            }
            ticketBoxes.forEach(box => {
                box.addEventListener('change', updateSelectedCount);
            });
            workspace.querySelectorAll('[data-workbench-column-toggle]').forEach(toggle => {
                toggle.addEventListener('change', function() {
                    const field = this.dataset.workbenchColumnToggle;
                    workspace.querySelectorAll(`[data-workbench-field="${field}"]`).forEach(cell => {
                        cell.classList.toggle('is-hidden', !this.checked);
                    });
                });
            });
            const sortButton = workspace.querySelector('[data-workbench-evidence-sort]');
            if (sortButton && table) {
                sortButton.addEventListener('click', function() {
                    const field = workspace.querySelector('[data-workbench-evidence-sort-field]')?.value || 'severity';
                    const direction = workspace.querySelector('[data-workbench-evidence-sort-direction]')?.value || 'desc';
                    const tbody = table.querySelector('tbody');
                    Array.from(tbody.querySelectorAll('[data-workbench-ticket-row]'))
                        .sort((left, right) => {
                            const leftValue = left.dataset[field] || '';
                            const rightValue = right.dataset[field] || '';
                            const result = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: 'base' });
                            return direction === 'asc' ? result : -result;
                        })
                        .forEach(row => tbody.appendChild(row));
                });
            }
            const bulkButton = workspace.querySelector('[data-workbench-ticket-bulk]');
            if (bulkButton) {
                bulkButton.addEventListener('click', function() {
                    const selectedTickets = selectedTicketPayloads();
                    if (selectedTickets.length === 0) {
                        return;
                    }
                    openDetail();
                    setDetailText('[data-ticket-detail-issue]', `${selectedTickets.length} selected tickets`);
                    const visibleIssueKeys = selectedTickets.slice(0, 12).map(ticket => ticket.issueKey);
                    const hiddenCount = selectedTickets.length - visibleIssueKeys.length;
                    const summary = hiddenCount > 0
                        ? `${visibleIssueKeys.join(', ')} +${hiddenCount} more`
                        : visibleIssueKeys.join(', ');
                    setDetailText('[data-ticket-detail-summary]', summary);
                    setDetailText('[data-ticket-detail-status]', 'mixed');
                    setDetailText('[data-ticket-detail-severity]', 'mixed');
                    setDetailText('[data-ticket-detail-owner]', 'mixed');
                    setDetailText('[data-ticket-detail-component]', 'mixed');
                    setDetailText('[data-ticket-detail-created]', '-');
                    setDetailText('[data-ticket-detail-updated]', '-');
                });
            }
            workspace.querySelectorAll('[data-workbench-ticket-row]').forEach(row => {
                row.addEventListener('click', function(event) {
                    if (event.target.closest('a, button, input, select, textarea')) {
                        return;
                    }
                    workspace.querySelectorAll('[data-workbench-ticket-row]').forEach(candidate => {
                        candidate.classList.remove('is-active');
                    });
                    this.classList.add('is-active');
                    openDetail();
                    setDetailText('[data-ticket-detail-issue]', this.dataset.issueKey);
                    setDetailText('[data-ticket-detail-summary]', this.dataset.summary);
                    setDetailText('[data-ticket-detail-status]', this.dataset.status);
                    setDetailText('[data-ticket-detail-severity]', this.dataset.severity);
                    setDetailText('[data-ticket-detail-owner]', this.dataset.owner);
                    setDetailText('[data-ticket-detail-component]', this.dataset.component);
                    setDetailText('[data-ticket-detail-created]', this.dataset.created);
                    setDetailText('[data-ticket-detail-updated]', this.dataset.updated);
                    const sourceLink = workspace.querySelector('[data-ticket-detail-source]');
                    if (sourceLink) {
                        sourceLink.href = this.dataset.sourceUrl || '#';
                        sourceLink.classList.toggle('is-disabled', !this.dataset.sourceUrl);
                    }
                });
            });
            workspace.querySelectorAll('[data-workbench-ticket-detail-close]').forEach(button => {
                button.addEventListener('click', function() {
                    if (layout) {
                        layout.classList.add('is-detail-collapsed');
                    }
                });
            });
            updateSelectedCount();
        });

        if (window.metricsWorkbenchMessageHandlerRegistered) {
            return;
        }
        window.metricsWorkbenchMessageHandlerRegistered = true;
        window.addEventListener('message', event => {
            const payload = event.data || {};
            if (payload.type === 'ai-base.host-action.request') {
                handleWorkbenchHostAction(event, payload);
                return;
            }
            if (event.origin !== window.location.origin) {
                return;
            }
            if (payload.type !== 'metrics-workbench:grafana-selection') {
                return;
            }
            const params = new URLSearchParams(window.location.search);
            Object.entries(payload).forEach(([key, value]) => {
                if (key === 'type') {
                    return;
                }
                if (value) {
                    params.set(key, value);
                }
            });
            const url = `${window.location.pathname}?${params.toString()}`;
            if (window.htmx) {
                htmx.ajax('GET', url, {
                    target: '.workbench-shell',
                    select: '.workbench-shell',
                    swap: 'outerHTML'
                });
            } else {
                window.location.assign(url);
                return;
            }
            window.history.pushState({}, '', url);
            saveCurrentWorkbenchUrl();
        });
    }
    
    let activeRequestCount = 0;

    function showLoadingIndicator() {
        activeRequestCount += 1;
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.remove('is-hidden');
        }
    }

    function hideLoadingIndicator() {
        activeRequestCount = Math.max(0, activeRequestCount - 1);
        if (activeRequestCount > 0) {
            return;
        }
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.add('is-hidden');
        }
    }

    function showErrorNotification(url, statusCode, statusText) {
        const container = document.getElementById('notification-container');
        if (!container) {
            return;
        }

        const message = statusCode
            ? `${statusCode} ${statusText}: ${url}`
            : `Network Error: ${url}`;

        const hint = statusCode === 503
            ? '<p>Request could be blocked by WAF due to long execution time. Retry.</p>'
            : '';

        const notificationHtml = `
            <div class="notification is-danger is-light">
                <button class="delete"></button>
                <p><strong>${message}</strong></p>
                ${hint}
            </div>
        `;

        container.innerHTML = notificationHtml;

        const deleteButton = container.querySelector('.delete');
        if (deleteButton) {
            deleteButton.addEventListener('click', function() {
                container.innerHTML = '';
            });
        }
    }

    document.querySelectorAll('.menu-toggle').forEach(toggle => {
        toggle.addEventListener('click', handleMenuToggle);
    });
    expandInitialActiveMenus();
    initializeSearchablePickupLists();
    initializeSearchableValuePickers();
    initializeScopeSourceModes();
    initializeDirtyForms();
    initializeProviderAuthForms();
    initializeRequiredForms();
    initializeConfirmForms();
    initializeDismissibleWorkbenchMenus();
    initializeWorkbenchShell();
    
    document.querySelectorAll('.menu-list a').forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.hasAttribute('hx-get') || this.hasAttribute('hx-post')) {
                setActiveMenuItem(this);
            }
        });
    });
    
    document.querySelectorAll('details').forEach(details => {
        details.addEventListener('toggle', function() {
            const icon = this.querySelector('summary i[class*="iconoir"]');
            if (icon) {
                icon.className = this.open ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right';
            }
        });
    });
    
    document.body.addEventListener('htmx:beforeRequest', showLoadingIndicator);
    document.body.addEventListener('htmx:afterRequest', hideLoadingIndicator);
    document.body.addEventListener('htmx:afterSwap', function() {
        initializeSearchablePickupLists();
        initializeSearchableValuePickers();
        initializeScopeSourceModes();
        initializeDirtyForms();
        initializeProviderAuthForms();
        initializeRequiredForms();
        initializeWorkbenchShell();
        if (typeof window.initBugTrendChart === 'function') {
            window.initBugTrendChart();
        }
    });

    document.body.addEventListener('htmx:pushedIntoHistory', saveCurrentWorkbenchUrl);

    document.body.addEventListener('htmx:responseError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        const statusCode = event.detail.xhr.status;
        const statusText = event.detail.xhr.statusText;
        showErrorNotification(url, statusCode, statusText);
    });

    document.body.addEventListener('htmx:sendError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        showErrorNotification(url, null, null);
    });

    window.addEventListener('popstate', function() {
        const currentPath = window.location.pathname;
        const currentSearch = window.location.search;
        const currentUrl = currentPath + currentSearch;
        
        const matchingLink = document.querySelector(`.menu-list a[href="${currentUrl}"]`);
        if (matchingLink) {
            setActiveMenuItem(matchingLink);
        }
    });
});
