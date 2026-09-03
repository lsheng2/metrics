from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class WorkbenchPane:
    pane_id: str
    title: str
    capability: str
    source_type: str
    target_route: str
    default_placement: str
    allowed_placements: tuple[str, ...]

    def to_dict(self, target_url: str) -> dict:
        return {
            'id': self.pane_id,
            'title': self.title,
            'capability': self.capability,
            'source_type': self.source_type,
            'target': target_url,
            'default_placement': self.default_placement,
            'allowed_placements': list(self.allowed_placements),
        }


@dataclass(frozen=True, slots=True)
class WorkbenchServiceStatus:
    service_id: str
    label: str
    status: str
    target_url: str
    reason: str = ''
    next_action: str = ''
    checked_at: str = ''


def default_workbench_panes() -> Sequence[WorkbenchPane]:
    return (
        WorkbenchPane(
            pane_id='chart',
            title='Quality Chart',
            capability='chart',
            source_type='django_page',
            target_route='ui_web:bug_trend',
            default_placement='primary',
            allowed_placements=('primary', 'utility'),
        ),
        WorkbenchPane(
            pane_id='evidence',
            title='Ticket Evidence',
            capability='evidence',
            source_type='django_partial',
            target_route='ui_web:bug_trend_evidence',
            default_placement='bottom',
            allowed_placements=('bottom', 'utility'),
        ),
        WorkbenchPane(
            pane_id='ai-assistant',
            title='AI Assistant',
            capability='ai',
            source_type='django_page',
            target_route='ui_web:ai_dashboard_workflow',
            default_placement='right',
            allowed_placements=('right', 'utility'),
        ),
        WorkbenchPane(
            pane_id='settings',
            title='Settings',
            capability='settings',
            source_type='django_page',
            target_route='ui_web:bug_trend_scope_library',
            default_placement='utility',
            allowed_placements=('utility', 'right'),
        ),
        WorkbenchPane(
            pane_id='publish-audit',
            title='Publish And Audit',
            capability='publish_audit',
            source_type='json_api',
            target_route='ui_web:ai_dashboard_publish_history_api',
            default_placement='utility',
            allowed_placements=('utility', 'right'),
        ),
        WorkbenchPane(
            pane_id='diagnostics',
            title='Diagnostics',
            capability='diagnostics',
            source_type='django_page',
            target_route='ui_web:data_health',
            default_placement='utility',
            allowed_placements=('utility', 'right'),
        ),
    )
