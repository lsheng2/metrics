from project_management.services.report_sources import ReportSourceReader
from project_management.services.report_publication_reads import ReportPublicationReader


class ReportArchiveReads:
    def read_report_material(self, actor, project_id, stage_id, selection, *, contract, limits=None):
        return ReportSourceReader(self, contract, limits).read(actor, project_id, stage_id, selection)

    def list_report_publications(self, actor, project_id, stage_id):
        with self._report_repository(actor, project_id, stage_id, write=False) as repository:
            return ReportPublicationReader(repository).list()

    def read_report_publication(self, actor, project_id, stage_id, publication_id):
        with self._report_repository(actor, project_id, stage_id, write=False) as repository:
            return ReportPublicationReader(repository).get(publication_id, actor.subject)
