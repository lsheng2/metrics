/*
 * Client checks that mirror server validation: [data-required-form] field messages and
 * aria-invalid state, and form[data-confirm] prompts including typed delete confirmation.
 */

document.addEventListener('DOMContentLoaded', function() {
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
                clone.querySelectorAll('.tag, .help-tip, .dashboard-required-tag, [data-dirty-marker]').forEach(node => node.remove());
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

    initializeRequiredForms();
    initializeConfirmForms();
    document.body.addEventListener('htmx:afterSwap', initializeRequiredForms);
});
