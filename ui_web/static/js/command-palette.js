/*
 * Meridian command palette: Ctrl/Cmd + K or "/" opens a filtered list of pages and shell actions.
 * Loads after shell.js and changes shell state (theme, sidebar, drawer) only through
 * window.DashboardShell.
 */
(function () {
    'use strict';

    function isTextEntry(element) {
        if (!element) {
            return false;
        }
        if (element.isContentEditable) {
            return true;
        }
        return ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName);
    }

    function initCommandPalette() {
        const dialog = document.querySelector('[data-shell-palette]');
        if (!dialog || typeof dialog.showModal !== 'function') {
            return;
        }
        const shell = window.DashboardShell;
        const input = dialog.querySelector('[data-shell-palette-input]');
        const empty = dialog.querySelector('[data-shell-palette-empty]');
        const options = Array.from(dialog.querySelectorAll('[role="option"]'));
        let activeOption = null;

        function visibleOptions() {
            return options.filter(option => !option.hidden);
        }

        function setActive(option) {
            activeOption = option || null;
            options.forEach(item => item.setAttribute('aria-selected', String(item === activeOption)));
            if (activeOption) {
                input.setAttribute('aria-activedescendant', activeOption.id);
                activeOption.scrollIntoView({ block: 'nearest' });
            } else {
                input.removeAttribute('aria-activedescendant');
            }
        }

        function markCurrentPage() {
            const currentPath = window.location.pathname;
            options.forEach(option => {
                const href = option.dataset.paletteHref;
                const isCurrent = Boolean(href) && new URL(href, window.location.origin).pathname === currentPath;
                if (isCurrent) {
                    option.setAttribute('aria-current', 'page');
                } else {
                    option.removeAttribute('aria-current');
                }
            });
        }

        function filterOptions() {
            const terms = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
            let first = null;
            options.forEach(option => {
                const haystack = (option.dataset.paletteText || option.textContent).toLowerCase();
                const matches = terms.every(term => haystack.includes(term));
                option.hidden = !matches;
                if (matches && !first) {
                    first = option;
                }
            });
            if (empty) {
                empty.hidden = Boolean(first);
            }
            input.setAttribute('aria-expanded', String(Boolean(first)));
            setActive(first);
        }

        function openPalette() {
            if (dialog.open) {
                input.select();
                return;
            }
            shell.closeDrawer();
            input.value = '';
            markCurrentPage();
            filterOptions();
            dialog.showModal();
            input.focus();
        }

        function closePalette() {
            if (dialog.open) {
                dialog.close();
            }
        }

        function runAction(action) {
            const [kind, value] = action.split(':');
            if (kind === 'theme') {
                shell.applyTheme(value);
            } else if (kind === 'sidebar' && value === 'toggle') {
                shell.toggleNavigation();
            }
        }

        function runOption(option, openInNewTab) {
            if (!option) {
                return;
            }
            const href = option.dataset.paletteHref;
            const action = option.dataset.paletteAction;
            closePalette();
            if (action) {
                runAction(action);
            } else if (href && openInNewTab) {
                window.open(href, '_blank', 'noopener');
            } else if (href) {
                window.location.assign(href);
            }
        }

        function moveActive(step) {
            const visible = visibleOptions();
            if (visible.length === 0) {
                return;
            }
            const index = visible.indexOf(activeOption);
            const next = index === -1 ? 0 : (index + step + visible.length) % visible.length;
            setActive(visible[next]);
        }

        input.addEventListener('input', filterOptions);
        input.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                moveActive(event.key === 'ArrowDown' ? 1 : -1);
            } else if (event.key === 'Home' || event.key === 'End') {
                const visible = visibleOptions();
                if (visible.length) {
                    event.preventDefault();
                    setActive(event.key === 'Home' ? visible[0] : visible[visible.length - 1]);
                }
            } else if (event.key === 'Enter') {
                event.preventDefault();
                runOption(activeOption, event.ctrlKey || event.metaKey);
            }
        });
        dialog.addEventListener('click', event => {
            if (event.target === dialog) {
                closePalette();
                return;
            }
            const option = event.target.closest('[role="option"]');
            if (option) {
                runOption(option, event.ctrlKey || event.metaKey);
            }
        });
        dialog.addEventListener('pointermove', event => {
            const option = event.target.closest('[role="option"]');
            if (option && option !== activeOption) {
                setActive(option);
            }
        });
        document.querySelectorAll('[data-shell-palette-open]').forEach(button => {
            button.addEventListener('click', openPalette);
        });
        document.addEventListener('keydown', event => {
            const isPaletteShortcut = (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k';
            if (isPaletteShortcut && !event.target.isContentEditable) {
                event.preventDefault();
                if (dialog.open) {
                    closePalette();
                } else {
                    openPalette();
                }
                return;
            }
            if (event.key === '/' && !dialog.open && !isTextEntry(event.target) && !event.ctrlKey && !event.metaKey && !event.altKey) {
                event.preventDefault();
                openPalette();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCommandPalette);
    } else {
        initCommandPalette();
    }
})();
