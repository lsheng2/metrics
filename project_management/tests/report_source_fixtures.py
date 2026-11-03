from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import json
import uuid

from project_management.app.api.capture_archive import MembershipInput, PartCoverage
from project_management.tests.summary_fixtures import SummaryScenario


@dataclass(frozen=True, slots=True)
class CapturedSummarySource:
    source_key: object
    capture_id: str
    page_id: str
    snapshot: object
    source_hash: str


class ReportSourceScenario(SummaryScenario):
    def capture_summary_source(self, archive, *, snapshot=None, item=None, complete_membership=True):
        _, initial = self.summary_source()
        selected = snapshot or initial
        if item is not None:
            selected = replace(selected, identity=item)
        intent = replace(self.intent(), required_parts=('facts', 'comments', 'history'))
        archive.prepare(self.actor, intent)
        page = archive.append_page(self.actor, intent, self.page(item=selected.identity))
        source = replace(selected, raw_page_ids=(page.page_id,))
        reference = archive.append_snapshot(self.actor, intent, source)
        complete_source = source.consistent and all(
            getattr(source.coverage, part).state == 'complete' for part in intent.required_parts
        )
        membership_state = 'complete' if complete_membership else 'partial'
        membership = MembershipInput(
            (source.identity,),
            PartCoverage(membership_state, 'source-version-1', 1, 1, None),
            (page.page_id,),
        )
        archive.finalize(
            self.actor,
            intent,
            membership,
            complete=complete_source and complete_membership,
            failure_code=None if complete_source and complete_membership else 'SOURCE_INCOMPLETE',
        )
        return CapturedSummarySource(
            self.source_key(intent, source.identity),
            intent.capture_id,
            page.page_id,
            source,
            reference.source_hash,
        )

    def accept_summary(self, archive, source_key):
        prepared = archive.prepare_analysis(
            self.actor,
            self.project.id,
            self.stage.id,
            source_key,
            self.contract,
            self.backend(),
            datetime.now(UTC) + timedelta(minutes=5),
        )
        attempt = prepared.attempt
        archive.claim_analysis_dispatch(self.actor, self.project.id, self.stage.id, attempt.attempt_id)
        snapshot, result = self.responses(attempt)
        accepted = archive.accept_analysis(
            self.actor,
            self.project.id,
            self.stage.id,
            attempt.attempt_id,
            snapshot,
            result,
            self.contract,
        )
        return attempt, accepted

    def read_report_source(self, archive, capture_id, *, limits=None, baseline_publication_id=None):
        from project_management.app.api.reports import ReportSelection

        selection = ReportSelection(
            capture_id=capture_id,
            baseline_publication_id=baseline_publication_id,
        )
        return archive.read_report_material(
            self.actor,
            self.project.id,
            self.stage.id,
            selection,
            contract=self.contract,
            limits=limits,
        )

    def archive_head(self, root):
        return self.git_text(self.archive_path(root), 'rev-parse', 'main')

    def archive_files(self, root):
        text = self.git_text(self.archive_path(root), 'ls-tree', '-r', '--name-only', 'main')
        return tuple(text.splitlines()) if text else ()

    def archive_status(self, root):
        return self.git_text(self.archive_path(root), 'status', '--short')

    def corrupt_accepted_candidate(self, root):
        archive_root = self.archive_path(root)
        names = [name for name in self.archive_files(root) if name.startswith('accepted_summaries/')]
        accepted_path = archive_root / names[0]
        payload = json.loads(accepted_path.read_text(encoding='utf-8'))
        payload['payload']['summary']['candidate']['what'] = 'Spoofed text from a stored candidate.'
        accepted_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')), encoding='utf-8')
        self.git(archive_root, 'add', '--', names[0])
        self.git(archive_root, 'commit', '-m', 'corrupt accepted summary')

    def recaptured_snapshot(self, snapshot, **facts):
        if not facts:
            return snapshot
        return replace(snapshot, facts=dict(snapshot.facts, **facts))

    def new_item(self, stable_id, display_key):
        return replace(self.item(), stable_id=stable_id, display_key=display_key)

    def random_publication_id(self):
        return str(uuid.uuid4())
