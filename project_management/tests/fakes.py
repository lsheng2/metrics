from project_management.app.domain.contracts import ProjectError, ScopeDescriptor


class FixedCatalog:
    def __init__(self):
        self.descriptor = ScopeDescriptor(
            provider_id='jira', profile_id='alpha-jira', endpoint='https://tracker.example.test',
            source_ref='scope:1', query_kind='jql', query='project = ALPHA', source_version='version-1',
        )
        self.available = True

    def resolve(self, selection):
        if not self.available:
            raise ProjectError('SOURCE_UNAVAILABLE')
        return self.descriptor
