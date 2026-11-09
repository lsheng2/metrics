/*
 * Grafana embeds: an iframe carries its panel URL in `data-grafana-src` and stays empty until it
 * is shown (its <details> opens), so a collapsed preview never makes the page wait on Grafana.
 * The panel follows the applied dashboard theme and reloads with the new `theme` on
 * `dashboard:themechange`; the server never decides the panel theme.
 */
(function () {
    'use strict';

    const EMBED_SELECTOR = 'iframe[data-grafana-src]';

    function themedSource(frame) {
        const url = new URL(frame.dataset.grafanaSrc, window.location.href);
        url.searchParams.set('theme', document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
        return url.href;
    }

    function load(frame) {
        const source = themedSource(frame);
        if (frame.getAttribute('src') !== source) {
            frame.setAttribute('src', source);
        }
    }

    function isShown(frame) {
        const details = frame.closest('details');
        return !details || details.open;
    }

    function syncEmbeds() {
        document.querySelectorAll(EMBED_SELECTOR).forEach(frame => {
            if (frame.hasAttribute('src') || isShown(frame)) {
                load(frame);
            }
        });
    }

    document.addEventListener('toggle', event => {
        if (event.target instanceof HTMLDetailsElement && event.target.open) {
            event.target.querySelectorAll(EMBED_SELECTOR).forEach(load);
        }
    }, true);
    document.addEventListener('dashboard:themechange', syncEmbeds);
    document.addEventListener('DOMContentLoaded', syncEmbeds);
    document.addEventListener('htmx:afterSwap', syncEmbeds);
})();
