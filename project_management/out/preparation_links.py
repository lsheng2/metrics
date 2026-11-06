from django.urls import reverse


class DjangoPreparationLinkBuilder:
    def links(self, project_id, stage_id, draft_id, publication_id=None):
        result = {
            'draft': reverse('ui_web:report_draft_edit', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'draft_id': draft_id,
            }),
        }
        if publication_id is not None:
            result['publication'] = reverse('ui_web:report_publication', kwargs={
                'project_id': project_id,
                'stage_id': stage_id,
                'publication_id': publication_id,
            })
        return result
