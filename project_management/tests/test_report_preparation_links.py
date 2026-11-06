import importlib

from django.test import override_settings
from django.urls import clear_url_caches, resolve, reverse

from project_management.out.preparation_links import DjangoPreparationLinkBuilder


def test_should_resolve_preparation_links_with_configured_base_prefix():
    import metrics.urls
    import ui_web.urls

    project_id = '70000000-0000-4000-8000-000000000001'
    stage_id = '70000000-0000-4000-8000-000000000002'
    draft_id = '71000000-0000-4000-8000-000000000003'
    publication_id = '72000000-0000-4000-8000-000000000004'
    try:
        with override_settings(METRICS_BASE_URL='/metrics-ui'):
            importlib.reload(ui_web.urls)
            importlib.reload(metrics.urls)
            clear_url_caches()
            expected_draft = reverse('ui_web:report_draft_edit', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'draft_id': draft_id,
            })
            expected_publication = reverse('ui_web:report_publication', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'publication_id': publication_id,
            })
            links = DjangoPreparationLinkBuilder().links(project_id, stage_id, draft_id, publication_id)
            draft_match = resolve(links['draft'])
            publication_match = resolve(links['publication'])
    finally:
        importlib.reload(ui_web.urls)
        importlib.reload(metrics.urls)
        clear_url_caches()

    assert links['draft'] == expected_draft
    assert links['publication'] == expected_publication
    assert draft_match.url_name == 'report_draft_edit'
    assert publication_match.url_name == 'report_publication'
    assert {key: str(value) for key, value in draft_match.kwargs.items()} == {
        'project_id': project_id,
        'stage_id': stage_id,
        'draft_id': draft_id,
    }
    assert {key: str(value) for key, value in publication_match.kwargs.items()} == {
        'project_id': project_id,
        'stage_id': stage_id,
        'publication_id': publication_id,
    }
