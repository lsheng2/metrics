from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme


def same_origin_next(request):
    next_url = request.POST.get('next') or reverse('ui_web:projects')
    if not safe_local_next(next_url, request):
        return reverse('ui_web:projects')
    return project_get_return_url(next_url)


def safe_local_next(next_url, request):
    if not isinstance(next_url, str) or not next_url.startswith('/'):
        return False
    if any(ord(char) < 32 for char in next_url) or '\\' in next_url or next_url.startswith('///'):
        return False
    return url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


def project_get_return_url(next_url):
    try:
        match = resolve(next_url.split('?', 1)[0])
    except Resolver404:
        return reverse('ui_web:projects')
    if match.app_name != 'ui_web':
        return reverse('ui_web:projects')
    if match.url_name in {'project_stage_preview', 'project_stage_confirm', 'project_archive'}:
        return reverse('ui_web:project_detail', kwargs={'project_id': match.kwargs['project_id']})
    if match.url_name == 'report_draft_create':
        return reverse('ui_web:project_stage_reports', kwargs={
            'project_id': match.kwargs['project_id'],
            'stage_id': match.kwargs['stage_id'],
        })
    if match.url_name in {'report_draft_save', 'report_draft_finalize', 'report_draft_resume'}:
        return reverse('ui_web:report_draft_edit', kwargs={
            'project_id': match.kwargs['project_id'],
            'stage_id': match.kwargs['stage_id'],
            'draft_id': match.kwargs['draft_id'],
        })
    if match.url_name in {'project_run_submit', 'project_run_cancel', 'project_run_resume'}:
        return reverse('ui_web:project_run_status', kwargs={
            'project_id': match.kwargs['project_id'],
            'stage_id': match.kwargs['stage_id'],
            'operation_id': match.kwargs.get('operation_id'),
        }) if match.kwargs.get('operation_id') else reverse('ui_web:project_stage_reports', kwargs={
            'project_id': match.kwargs['project_id'],
            'stage_id': match.kwargs['stage_id'],
        })
    if match.url_name == 'report_publication_revision':
        return reverse('ui_web:report_publication', kwargs={
            'project_id': match.kwargs['project_id'],
            'stage_id': match.kwargs['stage_id'],
            'publication_id': match.kwargs['publication_id'],
        })
    if match.url_name in {'projects', 'project_detail', 'project_stage_reports',
                          'project_run_status',
                          'report_draft_edit', 'report_publication'}:
        return next_url
    return reverse('ui_web:projects')
