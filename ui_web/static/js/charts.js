/*
 * Chart.js theme bridge for the Meridian design system.
 * Defaults (font, text, grid, tooltip, legend, elements) come from theme.css so every chart
 * follows the active light/dark theme. Live charts re-resolve on `dashboard:themechange`.
 * Series colors are owned by tokens only: use scriptable colors such as
 * `() => DashboardCharts.paletteColor(index)` or `() => DashboardCharts.seriesColor(name, index)`.
 * Colors inside server payloads exist for external consumers (Grafana) and are never read here.
 */
(function () {
    'use strict';

    const CHART_PALETTE_SIZE = 8;
    const THEMED_SCALE_PARTS = ['ticks', 'grid', 'border', 'title'];
    const reducedMotion = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    const tokenCache = new Map();

    function chartAvailable() {
        return Boolean(window.Chart && window.Chart.defaults && window.Chart.defaults.font);
    }

    function token(name, fallback) {
        if (!tokenCache.has(name)) {
            tokenCache.set(name, getComputedStyle(document.documentElement).getPropertyValue(name).trim());
        }
        return tokenCache.get(name) || fallback || '';
    }

    function paletteSlot(index) {
        return ((((Number(index) || 0) % CHART_PALETTE_SIZE) + CHART_PALETTE_SIZE) % CHART_PALETTE_SIZE) + 1;
    }

    function paletteColor(index) {
        return token(`--color-chart-${paletteSlot(index)}`);
    }

    function seriesKey(name) {
        return String(name || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    }

    function seriesColor(name, index) {
        const key = seriesKey(name);
        return (key && token(`--color-series-${key}`)) || paletteColor(index);
    }

    function seriesCssColor(name, index) {
        const key = seriesKey(name);
        const palette = `var(--color-chart-${paletteSlot(index)})`;
        return key ? `var(--color-series-${key}, ${palette})` : palette;
    }

    function alpha(color, opacity) {
        const value = String(color || '').trim();
        const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value);
        if (hex) {
            const digits = hex[1].length === 3 ? hex[1].replace(/./g, digit => digit + digit) : hex[1];
            const channels = [0, 2, 4].map(offset => parseInt(digits.slice(offset, offset + 2), 16));
            return `rgba(${channels.join(', ')}, ${opacity})`;
        }
        const functional = /^(rgb|hsl)a?\(([^)]+)\)$/i.exec(value);
        if (functional) {
            const parts = functional[2].split(/\s*[,/]\s*|\s+/).filter(Boolean).slice(0, 3);
            return `${functional[1].toLowerCase()}a(${parts.join(', ')}, ${opacity})`;
        }
        return value;
    }

    function applyDefaults() {
        if (!chartAvailable()) {
            return false;
        }
        const defaults = window.Chart.defaults;
        const textOnInverse = token('--color-on-inverse');
        defaults.font.family = token('--font-sans', defaults.font.family);
        defaults.font.size = 11;
        defaults.color = token('--color-text-secondary');
        defaults.borderColor = token('--color-border-subtle');
        defaults.animation.duration = reducedMotion && reducedMotion.matches ? 0 : 320;

        defaults.elements.line.borderWidth = 2;
        defaults.elements.point.radius = 2.5;
        defaults.elements.point.hoverRadius = 5;
        defaults.elements.point.hitRadius = 6;
        defaults.elements.bar.borderRadius = 3;
        if (defaults.datasets && defaults.datasets.bar) {
            defaults.datasets.bar.maxBarThickness = 32;
        }
        if (defaults.scale) {
            Object.assign(defaults.scale.ticks, { maxRotation: 0, autoSkipPadding: 16, padding: 6 });
            if (defaults.scale.border) {
                defaults.scale.border.display = false;
            }
        }

        const plugins = defaults.plugins || {};
        if (plugins.legend && plugins.legend.labels) {
            Object.assign(plugins.legend.labels, {
                usePointStyle: true,
                boxWidth: 8,
                boxHeight: 8,
                padding: 12,
            });
        }
        if (plugins.tooltip) {
            Object.assign(plugins.tooltip, {
                backgroundColor: token('--color-surface-inverse'),
                titleColor: textOnInverse,
                bodyColor: textOnInverse,
                footerColor: textOnInverse,
                borderWidth: 0,
                padding: 8,
                cornerRadius: 6,
                boxPadding: 4,
                caretSize: 5,
                usePointStyle: true,
                titleFont: { weight: '600' },
            });
        }
        return true;
    }

    // Chart.js copies scale colors from the defaults into each chart's config when the chart is
    // created, so a theme switch must drop those copies before the next update merges them again.
    function forgetThemedScaleColors(chart, previousColors) {
        const scales = chart.config && chart.config.options && chart.config.options.scales;
        Object.values(scales || {}).forEach(scale => {
            THEMED_SCALE_PARTS.forEach(part => {
                const options = scale && scale[part];
                if (options && previousColors.includes(options.color)) {
                    delete options.color;
                }
            });
        });
    }

    function refreshCharts() {
        const previousColors = chartAvailable()
            ? [window.Chart.defaults.color, window.Chart.defaults.borderColor]
            : [];
        tokenCache.clear();
        if (!applyDefaults()) {
            return;
        }
        Object.values(window.Chart.instances || {}).forEach(chart => {
            try {
                forgetThemedScaleColors(chart, previousColors);
                chart.update('none');
            } catch (error) {
                // A chart whose canvas left the DOM mid-swap is destroyed by its own template.
            }
        });
    }

    applyDefaults();
    document.addEventListener('dashboard:themechange', refreshCharts);
    if (reducedMotion) {
        reducedMotion.addEventListener('change', refreshCharts);
    }

    window.DashboardCharts = {
        token,
        alpha,
        paletteColor,
        seriesColor,
        seriesCssColor,
        refresh: refreshCharts,
    };
})();
