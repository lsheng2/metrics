"""Navigation registry for the dashboard shell.

The sidebar, the topbar breadcrumb and the command palette all render from this one
registry, so adding a page means adding one ``NavItem`` here.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True, slots=True)
class NavItem:
    key: str
    label: str | Promise
    url_name: str
    icon: str
    description: str | Promise = ''
    active_url_names: frozenset[str] = frozenset()
    active_url_prefixes: tuple[str, ...] = ()
    partial_url_name: str = ''
    member_group_filter: bool = False
    keywords: str = ''

    def matches(self, url_name: str) -> bool:
        if not url_name:
            return False
        if url_name == self.url_name or url_name in self.active_url_names:
            return True
        return bool(self.active_url_prefixes) and url_name.startswith(self.active_url_prefixes)


@dataclass(frozen=True, slots=True)
class NavGroup:
    key: str
    label: str | Promise
    items: tuple[NavItem, ...]


@dataclass(frozen=True, slots=True)
class NavLink:
    item: NavItem
    href: str
    partial_href: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class NavSection:
    group: NavGroup
    links: tuple[NavLink, ...]


@dataclass(frozen=True, slots=True)
class NavActive:
    group: NavGroup
    link: NavLink


NAVIGATION: tuple[NavGroup, ...] = (
    NavGroup('overview', _('Overview'), (
        NavItem(
            'home', _('Home'), 'homepage', 'iconoir-home-simple',
            _('Workspace overview, health and shortcuts'), keywords='start landing overview',
        ),
        NavItem(
            'workbench', _('Workbench'), 'workbench', 'iconoir-dashboard-dots',
            _('Chart, evidence and AI assistant in one view'),
            active_url_names=frozenset({'workbench_grafana_selection'}), keywords='chart evidence ai grafana',
        ),
    )),
    NavGroup('delivery', _('Delivery'), (
        NavItem(
            'projects', _('Projects'), 'projects', 'iconoir-folder',
            _('Projects, stage reports and publications'),
            active_url_prefixes=('project_', 'report_'), keywords='report weekly daily stage publication',
        ),
        NavItem(
            'current_tasks', _('Current Tasks'), 'current_tasks', 'iconoir-task-list',
            _('Active sprint work by member group'),
            active_url_names=frozenset({'current_tasks_with_team', 'partials_tasks'}),
            partial_url_name='partials_tasks', member_group_filter=True, keywords='sprint jira issues',
        ),
        NavItem(
            'pull_requests', _('Pull Requests'), 'pull_requests', 'iconoir-git-pull-request',
            _('Open pull requests and review state'),
            active_url_names=frozenset({'partials_pull_requests'}),
            partial_url_name='partials_pull_requests', member_group_filter=True, keywords='pr review azure github',
        ),
        NavItem(
            'task_forecast', _('Task Forecast'), 'task_forecast', 'iconoir-hourglass',
            _('Completion forecast from historical throughput'), keywords='prediction eta delivery',
        ),
    )),
    NavGroup('velocity', _('Velocity'), (
        NavItem(
            'team_velocity', _('Team Velocity'), 'team_velocity', 'iconoir-community',
            _('Team throughput and story points per sprint'),
            active_url_names=frozenset({'team_velocity_with_team'}),
            partial_url_name='team_velocity', member_group_filter=True, keywords='sprint story points throughput',
        ),
        NavItem(
            'dev_velocity', _('Dev Velocity'), 'dev_velocity', 'iconoir-graph-up',
            _('Per-developer throughput and story points'),
            active_url_names=frozenset({'dev_velocity_with_team'}),
            partial_url_name='dev_velocity', member_group_filter=True, keywords='developer member story points',
        ),
    )),
    NavGroup('quality', _('Quality'), (
        NavItem(
            'bug_trend', _('Bug Trend'), 'bug_trend', 'iconoir-bug',
            _('Bug inflow, outflow and open backlog per scope'), keywords='defect quality jira trend',
        ),
        NavItem(
            'ai_workflow', _('AI Workflow'), 'ai_dashboard_workflow', 'iconoir-sparks',
            _('AI-generated dashboard intents and publishing'), keywords='assistant grafana publish',
        ),
    )),
    NavGroup('configuration', _('Configuration'), (
        NavItem(
            'scope_library', _('Scope Library'), 'bug_trend_scope_library', 'iconoir-filter-list',
            _('Saved provider scopes and their configuration'),
            active_url_names=frozenset({'bug_trend_scope_config', 'bug_trend_scope_audit'}),
            keywords='scope jql config audit',
        ),
        NavItem(
            'provider_setup', _('Provider Setup'), 'provider_setup', 'iconoir-plug-type-a',
            _('Provider profiles, credentials and bindings'), keywords='jira azure github connection',
        ),
        NavItem(
            'data_health', _('Data Health'), 'data_health', 'iconoir-activity',
            _('Sync freshness, cursors and calculation runs'), keywords='sync status cursor freshness',
        ),
    )),
)


def _reverse(url_name: str) -> str:
    if not url_name:
        return ''
    try:
        return reverse(f'ui_web:{url_name}')
    except NoReverseMatch:
        return ''


def build_navigation(current_url_name: str) -> tuple[tuple[NavSection, ...], NavActive | None]:
    sections: list[NavSection] = []
    active: NavActive | None = None
    for group in NAVIGATION:
        links: list[NavLink] = []
        for item in group.items:
            href = _reverse(item.url_name)
            if not href:
                continue
            link = NavLink(
                item=item,
                href=href,
                partial_href=_reverse(item.partial_url_name),
                is_active=active is None and item.matches(current_url_name),
            )
            if link.is_active:
                active = NavActive(group=group, link=link)
            links.append(link)
        if links:
            sections.append(NavSection(group=group, links=tuple(links)))
    return tuple(sections), active
