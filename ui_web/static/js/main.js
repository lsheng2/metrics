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
                    const childToggle = row.querySelector('.task-toggle i[class*="iconoir"]');
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
            const fields = Array.from(form.querySelectorAll('input[name], textarea[name], select[name]'))
                .filter(field => field.type !== 'hidden' && field.type !== 'submit');

            fields.forEach(field => {
                field.dataset.initialValue = field.type === 'checkbox' ? String(field.checked) : field.value;
            });

            function markDirtyFields() {
                let formIsDirty = false;
                fields.forEach(field => {
                    const currentValue = field.type === 'checkbox' ? String(field.checked) : field.value;
                    const fieldIsDirty = currentValue !== field.dataset.initialValue;
                    formIsDirty = formIsDirty || fieldIsDirty;
                    const label = field.id ? form.querySelector(`label[for="${field.id}"]`) : null;
                    if (!label) {
                        return;
                    }
                    let marker = label.querySelector('[data-dirty-marker]');
                    if (fieldIsDirty && !marker) {
                        marker = document.createElement('span');
                        marker.className = 'tag is-warning is-light ml-2';
                        marker.dataset.dirtyMarker = 'true';
                        marker.textContent = 'Modified';
                        label.appendChild(marker);
                    }
                    if (!fieldIsDirty && marker) {
                        marker.remove();
                    }
                });
                if (banner) {
                    banner.classList.toggle('is-hidden', !formIsDirty);
                }
                form.dataset.dirty = String(formIsDirty);
            }

            fields.forEach(field => {
                field.addEventListener('input', markDirtyFields);
                field.addEventListener('change', markDirtyFields);
            });

            form.querySelectorAll('[data-dirty-guard]').forEach(link => {
                link.addEventListener('click', event => {
                    if (form.dataset.dirty === 'true' && !window.confirm('Discard unsaved changes?')) {
                        event.preventDefault();
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
                }
            });
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
    initializeDirtyForms();
    initializeConfirmForms();
    
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