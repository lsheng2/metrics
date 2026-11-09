"""Ordered static assets that base.html loads on every dashboard page.

Stylesheet order is cascade order: normalize and fonts, design tokens, foundation primitives,
icons, the application shell, then feature styles. Script order is dependency order: vendor
runtimes, the chart theme bridge, the shell (which publishes window.DashboardShell), then
features. Each feature module wraps itself in DOMContentLoaded and registers its own
htmx:afterSwap re-initialisation, so FEATURE_SCRIPTS order is also the init and after-swap
order. Browser tests inline STYLESHEETS and FEATURE_SCRIPTS, so a new or split file is
registered here once.
"""

STYLESHEETS = (
    'vendor/modern-normalize/modern-normalize.css',
    'vendor/fonts/fonts.css',
    'css/theme.css',
    'css/foundation/base.css',
    'css/foundation/layout.css',
    'css/foundation/typography.css',
    'css/foundation/buttons.css',
    'css/foundation/forms.css',
    'css/foundation/tables.css',
    'css/foundation/disclosure.css',
    'css/foundation/feedback.css',
    'css/foundation/page-patterns.css',
    'css/foundation/charts.css',
    'css/foundation/status.css',
    'css/foundation/work-items.css',
    'css/foundation/helpers.css',
    'vendor/iconoir/iconoir.css',
    'css/shell/frame.css',
    'css/shell/sidebar.css',
    'css/shell/topbar.css',
    'css/shell/palette.css',
    'css/shell/statusbar.css',
    'css/shell/responsive.css',
    'css/shell/standalone.css',
    'css/pages/common.css',
    'css/pages/home.css',
    'css/pages/dense-tables.css',
    'css/pages/scope-config.css',
    'css/pages/scope-query.css',
    'css/pages/scope-library.css',
    'css/pages/editor-forms.css',
    'css/pages/provider-setup.css',
    'css/pages/provider-editor.css',
    'css/pages/editor-responsive.css',
    'css/pages/delivery-views.css',
    'css/pages/projects.css',
    'css/pages/report-templates.css',
    'css/pages/project-reports.css',
    'css/pages/workbench-shell.css',
    'css/pages/workbench-panes.css',
    'css/pages/workbench-evidence.css',
)

VENDOR_SCRIPTS = (
    'vendor/htmx/htmx.min.js',
    'vendor/chartjs/chart.umd.min.js',
    'vendor/chartjs/chartjs-adapter-date-fns.bundle.min.js',
    'vendor/chartjs/chartjs-plugin-annotation.min.js',
)

PLATFORM_SCRIPTS = (
    'js/charts.js',
    'js/shell.js',
    'js/command-palette.js',
)

FEATURE_SCRIPTS = (
    'js/table-interactions.js',
    'js/navigation-menus.js',
    'js/searchable-pickers.js',
    'js/scope-source-modes.js',
    'js/editor-forms.js',
    'js/form-validation.js',
    'js/workbench-state.js',
    'js/pane-layout.js',
    'js/workbench-evidence.js',
    'js/grafana-embeds.js',
    'js/htmx-lifecycle.js',
)

SCRIPTS = VENDOR_SCRIPTS + PLATFORM_SCRIPTS + FEATURE_SCRIPTS
