/*
 * Sidebar navigation menus: submenu toggles, expanding the group that holds the active page,
 * and keeping the active item in sync with htmx menu links and browser history.
 */

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

    document.querySelectorAll('.menu-toggle').forEach(toggle => {
        toggle.addEventListener('click', handleMenuToggle);
    });
    expandInitialActiveMenus();

    document.querySelectorAll('.menu-list a').forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.hasAttribute('hx-get') || this.hasAttribute('hx-post')) {
                setActiveMenuItem(this);
            }
        });
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
