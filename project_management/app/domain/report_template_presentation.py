from project_management.app.domain.report_contracts import ReportError


RENDERER_VERSION = 'template-document/1'
STANDUP_RENDERER_VERSION = 'template-document/2'
MANDATORY_DATA = ('key_messages', 'changes', 'register', 'coverage')


def template_renderer_version(document):
    if 'presentation_profile' not in document:
        return RENDERER_VERSION
    if document.get('schema_version') != 2 or document['presentation_profile'] != 'standup/1':
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return STANDUP_RENDERER_VERSION


def is_pinned_renderer(value):
    return type(value) is str and value in {RENDERER_VERSION, STANDUP_RENDERER_VERSION}


def template_readiness(document):
    sources = [block['source'] for block in document['blocks'] if block['kind'] == 'data']
    concise = document.get('presentation_profile') == 'standup/1'
    required = [] if concise else list(MANDATORY_DATA)
    if document['report_kind'] == 'weekly' and not concise:
        required.append('weekly_timeline')
    if document['schema_version'] == 2:
        required.append('meeting_matrix')
    codes = []
    for source in required:
        count = sources.count(source)
        if count == 0:
            codes.append('TEMPLATE_MISSING_DATA_' + source.upper())
        elif count > 1:
            codes.append('TEMPLATE_DUPLICATE_DATA_' + source.upper())
    return ('draft' if codes else 'ready'), tuple(codes)
