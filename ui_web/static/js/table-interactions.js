/*
 * Dense-table interactions shared by data pages, delegated at document level so htmx swaps
 * need no re-binding: task-tree expand/collapse, lazily loaded child-task rows, the avatar
 * photo fallback and row menus that must not be clipped by their scrolling table box.
 */

// Task tree tables (forecast breakdown): rows carry `data-level` and parents a `.task-tree__toggle`
// whose `aria-expanded` is the source of truth. A row is hidden when any ancestor is collapsed.
function syncTaskTree(table) {
    const expandedAncestors = [];
    Array.from(table.tBodies[0].rows).forEach(row => {
        const level = Number(row.dataset.level || 0);
        expandedAncestors.length = level;
        row.hidden = expandedAncestors.includes(false);
        const toggle = row.querySelector('.task-tree__toggle');
        expandedAncestors[level] = !toggle || toggle.getAttribute('aria-expanded') === 'true';
    });
}

document.addEventListener('click', event => {
    const toggle = event.target.closest('.task-tree__toggle');
    if (toggle) {
        toggle.setAttribute('aria-expanded', String(toggle.getAttribute('aria-expanded') !== 'true'));
        syncTaskTree(toggle.closest('table'));
        return;
    }
    // Child-task rows (current tasks): htmx loads the controlled tbody on the first click only;
    // `aria-expanded` stays the source of truth for its `hidden` state.
    const childrenToggle = event.target.closest('.task-children-toggle');
    if (childrenToggle) {
        const expanded = childrenToggle.getAttribute('aria-expanded') !== 'true';
        childrenToggle.setAttribute('aria-expanded', String(expanded));
        const rows = document.getElementById(childrenToggle.getAttribute('aria-controls'));
        if (rows) {
            rows.hidden = !expanded;
        }
        return;
    }
    const bulkToggle = event.target.closest('[data-task-tree-expand]');
    const table = bulkToggle && document.getElementById(bulkToggle.getAttribute('aria-controls'));
    if (!table) {
        return;
    }
    const expanded = String(bulkToggle.dataset.taskTreeExpand === 'all');
    table.querySelectorAll('.task-tree__toggle').forEach(button => button.setAttribute('aria-expanded', expanded));
    syncTaskTree(table);
});

// Provider avatar photos often need a tracker session; a photo that fails to load is removed so the
// initials underneath show. `error` does not bubble, so listen in the capture phase.
document.addEventListener('error', event => {
    if (event.target instanceof HTMLImageElement && event.target.classList.contains('avatar__image')) {
        event.target.remove();
    }
}, true);

// A row menu inside a scrolling table box would be clipped by the box: an open menu flips above its
// summary when only that fits, otherwise the box grows until the panel fits. `toggle` does not bubble.
const TABLE_MENU_GAP_PX = 8;

function fitTableMenu(menu) {
    const box = menu.closest('.table-container');
    const panel = menu.querySelector(':scope > .workbench-menu-panel');
    if (!box || !panel) {
        return;
    }
    menu.classList.remove('is-upward');
    if (!menu.open) {
        if (!box.querySelector('.workbench-menu[open]')) {
            box.style.removeProperty('padding-bottom');
        }
        return;
    }
    box.style.removeProperty('padding-bottom');
    const boxRect = box.getBoundingClientRect();
    const boxInnerTop = boxRect.top + box.clientTop;
    const overflow = panel.getBoundingClientRect().bottom + TABLE_MENU_GAP_PX - (boxInnerTop + box.clientHeight);
    if (overflow <= 0) {
        return;
    }
    const headerHeight = box.querySelector('thead')?.getBoundingClientRect().height || 0;
    const summaryTop = menu.querySelector(':scope > summary').getBoundingClientRect().top;
    if (summaryTop - (boxInnerTop + headerHeight) >= panel.offsetHeight + TABLE_MENU_GAP_PX) {
        menu.classList.add('is-upward');
        return;
    }
    box.style.paddingBottom = `${Math.ceil(overflow)}px`;
}

document.addEventListener('toggle', event => {
    if (event.target instanceof HTMLDetailsElement && event.target.matches('.table-container .workbench-menu')) {
        fitTableMenu(event.target);
    }
}, true);
