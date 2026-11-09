"""Single source of the pixel-level UI geometry thresholds that ui_web browser tests enforce.

Tests import these constants for Python assertions and pass ``browser_limits()`` to
``page.evaluate`` as ``limits`` so measurement JavaScript reads ``limits.<KEY>`` instead of
repeating literals. Change a threshold only here and only with design approval.
``python ui_web/tests/ui_geometry_contract.py`` prints the contract as Markdown by surface.
"""
from dataclasses import dataclass

# Shared by every surface.
OVERFLOW_TOLERANCE = 1
ALIGNMENT_TOLERANCE = 1
HEIGHT_DELTA_MAX = 1
BUTTON_FONT_WEIGHT_MAX = 500

# Tables.
TABLE_CELL_PADDING_BLOCK_MAX = 12
DENSE_ROW_HEIGHT_MAX = 72

# Provider tabs shared by the provider profile editor and the scope config editor.
PROVIDER_CHECK_MIN_WIDTH = 14
TAB_ATTACHMENT_GAP_MAX = 2
PROVIDER_CHOICE_HEIGHT_MAX = 82
HAIRLINE_BORDER_WIDTH_MAX = 1

# Editor action bars shared by the provider profile editor and the scope config editor.
EDITOR_ACTION_GAP_MIN = 8
ACTIONS_TO_SIGNATURE_GAP_MIN = 12

# Provider setup inventory and provider profile editor.
PROVIDER_ROW_MENU_PANEL_MIN_HEIGHT = 100
ADVANCED_SUMMARY_MIN_HEIGHT = 32

# Scope library.
ROW_ACTION_BUTTON_HEIGHT = 28
ROW_ACTION_BUTTON_MIN_WIDTH = 44
ROW_ACTION_BUTTON_WIDTH_DELTA_MAX = 2
HELP_TIP_ANCHOR_WIDTH_MAX = 1
ICON_HELP_TIP_MIN_WIDTH = 12
SCOPE_LIFECYCLE_GUIDE_HEIGHT_MAX = 58
SCOPE_LIBRARY_ROW_HEIGHT_MAX = 40
SCOPE_ACTION_OFFSET_DELTA_MAX = 2

# Workbench.
WORKBENCH_AI_PANE_MIN_WIDTH = 280
WORKBENCH_SHELL_TOP_MAX = 10
WORKBENCH_COLLAPSED_AI_WIDTH_MAX = 42
WORKBENCH_STATUS_BAR_MIN_HEIGHT = 24
WORKBENCH_TOOLBAR_LABEL_TOP_GAP_MIN = 4
WORKBENCH_PHONE_CHART_MIN_HEIGHT = 320

# Report authoring.
REPORT_COMPLETION_MENU_OFFSET_MAX = 48
REPORT_TOOLBAR_ICON_MIN_SIZE = 10
REPORT_PHONE_PAGE_WIDTH_MAX = 390

COMPARISONS = {
    'max': 'measured <= limit',
    'max-exclusive': 'measured < limit',
    'min': 'measured >= limit',
    'exact': 'measured == limit',
    'tolerance': 'overflow or edge misalignment of at most limit is still a pass',
}

_TESTS = 'ui_web.tests.'
_METRICS = _TESTS + 'ui_design_browser_metrics_support'
_BASELINE = _TESTS + 'test_ui_design_baseline_gate'
_PROVIDER_SUPPORT = _TESTS + 'provider_setup_view_test_support'
_SCOPE_SUPPORT = _TESTS + 'bug_trend_scope_config_test_support'
_WORKBENCH_SUPPORT = _TESTS + 'workbench_browser_test_support'
_PROVIDER_VIEWS = _TESTS + 'test_provider_setup_views'
_SCOPE_CONFIG_VIEWS = _TESTS + 'test_bug_trend_scope_config_views'
_SCOPE_PROVIDER_VIEWS = _TESTS + 'test_bug_trend_scope_provider_views'
_SCOPE_ACTION_VIEWS = _TESTS + 'test_bug_trend_scope_action_views'
_WORKBENCH_BROWSER = _TESTS + 'test_workbench_high_density_browser'

_BASELINE_VIEWPORTS = ('1440x900', '390x900')


@dataclass(slots=True, frozen=True)
class GeometryRule:
    key: str
    limit: float
    unit: str
    comparison: str
    surface: str
    measures: str
    viewports: tuple[str, ...]
    enforced_by: tuple[str, ...]


GEOMETRY_RULES: tuple[GeometryRule, ...] = (
    GeometryRule(
        'OVERFLOW_TOLERANCE', OVERFLOW_TOLERANCE, 'px', 'tolerance', 'shared',
        'Pixels scrollWidth or scrollHeight may exceed the client size before the page, a table box, the'
        ' signature grid or values, a button or a workbench toolbar label counts as overflowing or clipped;'
        ' also how far a stacked Workbench ticket detail or AI pane may run under the top bar or status bar.',
        (),
        (
            _METRICS, _BASELINE, _PROVIDER_SUPPORT, _SCOPE_SUPPORT, _WORKBENCH_SUPPORT, _WORKBENCH_BROWSER,
            _TESTS + 'test_data_health_views',
        ),
    ),
    GeometryRule(
        'ALIGNMENT_TOLERANCE', ALIGNMENT_TOLERANCE, 'px', 'tolerance', 'shared',
        'Pixels two edges that must line up may differ: same-row action buttons, the connection test result'
        ' above the editor actions, toolbar labels inside their field, workbench panes flush with the viewport,'
        ' stacked phone workbench panes as wide as their grid with even side gutters,'
        ' the first column of a flush card table and its card title.',
        (),
        (_METRICS, _BASELINE, _PROVIDER_SUPPORT, _SCOPE_SUPPORT, _WORKBENCH_SUPPORT, _WORKBENCH_BROWSER),
    ),
    GeometryRule(
        'HEIGHT_DELTA_MAX', HEIGHT_DELTA_MAX, 'px', 'max', 'shared',
        'Height spread (max - min) of buttons or controls that share an action group, form, action bar,'
        ' row-action cell or table.',
        (),
        (_METRICS, _BASELINE, _PROVIDER_VIEWS, _SCOPE_PROVIDER_VIEWS, _SCOPE_ACTION_VIEWS),
    ),
    GeometryRule(
        'BUTTON_FONT_WEIGHT_MAX', BUTTON_FONT_WEIGHT_MAX, 'font-weight', 'max', 'shared',
        'Computed font-weight of every visible .button (Meridian medium weight token).',
        _BASELINE_VIEWPORTS,
        (_METRICS, _BASELINE),
    ),
    GeometryRule(
        'TABLE_CELL_PADDING_BLOCK_MAX', TABLE_CELL_PADDING_BLOCK_MAX, 'px', 'max', 'tables',
        'padding-top + padding-bottom of th and data-row td cells in every visible table.',
        _BASELINE_VIEWPORTS,
        (_METRICS, _BASELINE),
    ),
    GeometryRule(
        'DENSE_ROW_HEIGHT_MAX', DENSE_ROW_HEIGHT_MAX, 'px', 'max', 'tables',
        'Body row height in every .dashboard-dense-table.',
        _BASELINE_VIEWPORTS,
        (_METRICS, _BASELINE),
    ),
    GeometryRule(
        'PROVIDER_CHECK_MIN_WIDTH', PROVIDER_CHECK_MIN_WIDTH, 'px', 'min', 'provider-tabs',
        'Width at which the selected provider tab .provider-tab-check counts as visible.',
        _BASELINE_VIEWPORTS,
        (_METRICS, _BASELINE, _PROVIDER_SUPPORT, _SCOPE_SUPPORT),
    ),
    GeometryRule(
        'TAB_ATTACHMENT_GAP_MAX', TAB_ATTACHMENT_GAP_MAX, 'px', 'tolerance', 'provider-tabs',
        'Distance between the selected provider tab bottom and the .provider-tab-body top.',
        ('1440x900',),
        (_PROVIDER_SUPPORT, _SCOPE_SUPPORT),
    ),
    GeometryRule(
        'PROVIDER_CHOICE_HEIGHT_MAX', PROVIDER_CHOICE_HEIGHT_MAX, 'px', 'max', 'provider-tabs',
        'Tallest .provider-setup-choice provider tab.',
        ('1440x900',),
        (_PROVIDER_VIEWS, _SCOPE_PROVIDER_VIEWS),
    ),
    GeometryRule(
        'HAIRLINE_BORDER_WIDTH_MAX', HAIRLINE_BORDER_WIDTH_MAX, 'px', 'max', 'provider-tabs',
        'Left border width of .provider-context-panel and .scope-provider-detail-panel (no accent rail).',
        ('1440x900',),
        (_PROVIDER_VIEWS, _SCOPE_PROVIDER_VIEWS),
    ),
    GeometryRule(
        'EDITOR_ACTION_GAP_MIN', EDITOR_ACTION_GAP_MIN, 'px', 'min', 'editors',
        'column-gap of .provider-editor-actions and .scope-editor-actions.',
        ('1280x820',),
        (_PROVIDER_VIEWS, _SCOPE_ACTION_VIEWS),
    ),
    GeometryRule(
        'ACTIONS_TO_SIGNATURE_GAP_MIN', ACTIONS_TO_SIGNATURE_GAP_MIN, 'px', 'min', 'editors',
        'Gap from the editor action bar bottom to the .dashboard-signature-grid top.',
        ('1280x820',),
        (_PROVIDER_VIEWS, _SCOPE_CONFIG_VIEWS),
    ),
    GeometryRule(
        'PROVIDER_ROW_MENU_PANEL_MIN_HEIGHT', PROVIDER_ROW_MENU_PANEL_MIN_HEIGHT, 'px', 'min', 'provider-setup',
        'Height of the opened .provider-row-menu panel in the provider inventory.',
        ('1660x760',),
        (_PROVIDER_VIEWS,),
    ),
    GeometryRule(
        'ADVANCED_SUMMARY_MIN_HEIGHT', ADVANCED_SUMMARY_MIN_HEIGHT, 'px', 'min', 'provider-editor',
        'Height of the .provider-advanced-config summary toggle.',
        ('1280x820',),
        (_PROVIDER_VIEWS,),
    ),
    GeometryRule(
        'ROW_ACTION_BUTTON_HEIGHT', ROW_ACTION_BUTTON_HEIGHT, 'px', 'exact', 'scope-library',
        'The one rounded height shared by the primary row-action buttons in .scope-primary-actions.',
        ('1280x900',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'ROW_ACTION_BUTTON_MIN_WIDTH', ROW_ACTION_BUTTON_MIN_WIDTH, 'px', 'min', 'scope-library',
        'Rounded width of each primary row-action button in .scope-primary-actions.',
        ('1280x900',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'ROW_ACTION_BUTTON_WIDTH_DELTA_MAX', ROW_ACTION_BUTTON_WIDTH_DELTA_MAX, 'px', 'max', 'scope-library',
        'Width spread (max - min) of the primary row-action buttons in .scope-primary-actions.',
        ('1280x900',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'HELP_TIP_ANCHOR_WIDTH_MAX', HELP_TIP_ANCHOR_WIDTH_MAX, 'px', 'max', 'scope-library',
        'Rounded width of the text .help-tip anchor; its hover bubble is the ::after pseudo-element.',
        ('1280x900',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'ICON_HELP_TIP_MIN_WIDTH', ICON_HELP_TIP_MIN_WIDTH, 'px', 'min', 'scope-library',
        'Rounded width of the .help-tip.is-icon trigger.',
        ('1280x900',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'SCOPE_LIFECYCLE_GUIDE_HEIGHT_MAX', SCOPE_LIFECYCLE_GUIDE_HEIGHT_MAX, 'px', 'max', 'scope-library',
        'Height of .scope-lifecycle-guide.',
        ('1532x768',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'SCOPE_LIBRARY_ROW_HEIGHT_MAX', SCOPE_LIBRARY_ROW_HEIGHT_MAX, 'px', 'max', 'scope-library',
        'Tallest .scope-library-table body row.',
        ('1532x768',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'SCOPE_ACTION_OFFSET_DELTA_MAX', SCOPE_ACTION_OFFSET_DELTA_MAX, 'px', 'max', 'scope-library',
        'Spread across rows of the .scope-primary-actions left offset inside td.scope-col-actions.',
        ('1532x768',),
        (_SCOPE_CONFIG_VIEWS,),
    ),
    GeometryRule(
        'WORKBENCH_AI_PANE_MIN_WIDTH', WORKBENCH_AI_PANE_MIN_WIDTH, 'px', 'min', 'workbench',
        '--workbench-ai-width after collapsing the AI pane and pressing ArrowLeft on its splitter.',
        ('1280x900',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'WORKBENCH_SHELL_TOP_MAX', WORKBENCH_SHELL_TOP_MAX, 'px', 'max', 'workbench',
        'Top of .workbench-shell in the viewport.',
        ('1280x900',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'WORKBENCH_COLLAPSED_AI_WIDTH_MAX', WORKBENCH_COLLAPSED_AI_WIDTH_MAX, 'px', 'max', 'workbench',
        'Rendered width of the collapsed [data-workbench-pane="ai-assistant"] pane.',
        ('1280x900',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'WORKBENCH_STATUS_BAR_MIN_HEIGHT', WORKBENCH_STATUS_BAR_MIN_HEIGHT, 'px', 'min', 'workbench',
        'Height of [data-workbench-status-bar].',
        ('1280x900',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'WORKBENCH_TOOLBAR_LABEL_TOP_GAP_MIN', WORKBENCH_TOOLBAR_LABEL_TOP_GAP_MIN, 'px', 'min', 'workbench',
        'Smallest distance from the .workbench-toolbar top to a toolbar field label top.',
        ('1280x900',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'WORKBENCH_PHONE_CHART_MIN_HEIGHT', WORKBENCH_PHONE_CHART_MIN_HEIGHT, 'px', 'min', 'workbench',
        'Height of .bug-trend-chart-frame once the Workbench panes stack in the page flow below 1024px.',
        ('390x844',),
        (_WORKBENCH_BROWSER,),
    ),
    GeometryRule(
        'REPORT_COMPLETION_MENU_OFFSET_MAX', REPORT_COMPLETION_MENU_OFFSET_MAX, 'px', 'max-exclusive', 'reports',
        'Horizontal distance between the .report-completion-menu left edge and the completed token left edge.',
        ('1440x1000',),
        (_TESTS + 'test_report_completion_browser',),
    ),
    GeometryRule(
        'REPORT_TOOLBAR_ICON_MIN_SIZE', REPORT_TOOLBAR_ICON_MIN_SIZE, 'px', 'min', 'reports',
        'Width and height of every iconoir icon in .report-editor-toolbar.',
        ('1440x1000',),
        (_TESTS + 'test_report_authoring_edit_runtime_browser',),
    ),
    GeometryRule(
        'REPORT_PHONE_PAGE_WIDTH_MAX', REPORT_PHONE_PAGE_WIDTH_MAX, 'px', 'max', 'reports',
        'document scrollWidth of the report editor after it is resized to the phone viewport.',
        ('390x844',),
        (_TESTS + 'test_report_query_browser',),
    ),
)


def browser_limits() -> dict[str, float]:
    return {rule.key: rule.limit for rule in GEOMETRY_RULES}


def markdown_table() -> str:
    lines = [
        '# UI geometry contract',
        '',
        'Comparisons: ' + '; '.join(f'{name} = {meaning}' for name, meaning in COMPARISONS.items()) + '.',
        f'Viewports are width x height; enforced_by modules live in `{_TESTS.rstrip(".")}`.',
    ]
    for surface in dict.fromkeys(rule.surface for rule in GEOMETRY_RULES):
        lines += ['', f'## {surface}', '', '| key | limit | unit | comparison | measures | enforced_by |']
        lines.append('| --- | --- | --- | --- | --- | --- |')
        for rule in (rule for rule in GEOMETRY_RULES if rule.surface == surface):
            viewports = f' Viewports: {", ".join(rule.viewports)}.' if rule.viewports else ''
            modules = ', '.join(module.removeprefix(_TESTS) for module in rule.enforced_by)
            cells = (rule.key, str(rule.limit), rule.unit, rule.comparison, rule.measures + viewports, modules)
            lines.append('| ' + ' | '.join(cell.replace('|', '\\|') for cell in cells) + ' |')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(markdown_table())
