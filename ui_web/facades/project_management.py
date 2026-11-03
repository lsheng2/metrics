from project_management.app.api import ScopeSelection


class ProjectManagementFacade:
    def __init__(self, api, source_choices):
        self.api = api
        self.source_choices = source_choices

    def list_projects(self, actor, *, offset: int):
        projects = self.api.list_projects(actor, limit=50, offset=offset)
        return {
            'projects': projects,
            'offset': offset,
            'previous_offset': max(offset - 50, 0) if offset > 0 else None,
            'next_offset': offset + 50 if len(projects) == 50 else None,
        }

    def create_project(self, actor, *, key, name):
        return self.api.create_project(actor, key=key, name=name)

    def get_project(self, actor, project_id):
        return {
            'detail': self.api.get_project(actor, project_id),
            'source_choices': self.source_choices.list_choices(),
        }

    def preview_stage(self, actor, project_id, *, key, name, selection):
        return self.api.preview_stage(actor, project_id, key=key, name=name, selection=selection)

    def confirm_stage(self, actor, project_id, preview_data):
        selection_data = dict(preview_data['selection'])
        return self.api.add_stage(
            actor,
            project_id,
            key=preview_data['key'],
            name=preview_data['name'],
            selection=ScopeSelection(selection_data['profile_id'], selection_data.get('scope_id')),
            expected_definition_hash=preview_data['definition_hash'],
        )

    def archive_project(self, actor, project_id):
        return self.api.archive_project(actor, project_id)
