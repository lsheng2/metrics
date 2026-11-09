/*
 * Searchable pickers in the scope and provider editors: pickup lists and value pickers with
 * a search box, keyboard handling and outside-click close.
 */

document.addEventListener('DOMContentLoaded', function() {
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

    function initializeSearchablePickers() {
        initializeSearchablePickupLists();
        initializeSearchableValuePickers();
    }

    initializeSearchablePickers();
    document.body.addEventListener('htmx:afterSwap', initializeSearchablePickers);
});
