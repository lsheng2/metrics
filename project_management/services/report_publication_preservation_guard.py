from project_management.app.domain.report_contracts import ReportError


def verify_no_preservation_review_issues(draft):
    if draft.preservation_review_issues:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
