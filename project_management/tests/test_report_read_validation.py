from pathlib import Path

import pytest


def test_summary_keeps_first_process_out_of_serial_p95():
    from scripts.validation.profile_report_reads import summarize_samples

    first = {'seconds': 9.0, 'status_code': 200, 'body_sha256': 'a' * 64}
    serial = [
        {'seconds': 1.0, 'status_code': 200, 'body_sha256': 'b' * 64},
        {'seconds': 2.0, 'status_code': 200, 'body_sha256': 'c' * 64},
        {'seconds': 3.0, 'status_code': 200, 'body_sha256': 'd' * 64},
    ]

    summary = summarize_samples(first, serial)

    assert summary['first_process_seconds'] == 9.0
    assert summary['serial_count'] == 3
    assert summary['serial_nearest_rank_p95_seconds'] == 3.0


def test_summary_keeps_redirect_and_failure_samples_but_marks_slo_invalid():
    from scripts.validation.profile_report_reads import summarize_samples

    first = {'seconds': 1.0, 'status_code': 200, 'body_sha256': 'a' * 64, 'error': None}
    serial = [
        {'seconds': 0.1, 'status_code': 302, 'body_sha256': 'b' * 64, 'redirect_only': True, 'error': None},
        {'seconds': 0.2, 'status_code': 500, 'body_sha256': 'c' * 64, 'redirect_only': False, 'error': None},
        {'seconds': 0.3, 'status_code': 200, 'body_sha256': 'd' * 64, 'redirect_only': False, 'error': 'boom'},
    ]

    summary = summarize_samples(first, serial)

    assert summary['serial_count'] == 3
    assert summary['serial_nearest_rank_p95_seconds'] == 0.3
    assert summary['invalid_for_slo'] is True
    assert summary['failure_count'] == 2
    assert summary['redirect_only_serial_samples'] == 1


def test_output_dir_must_be_under_owned_evidence(tmp_path):
    from scripts.validation.profile_report_reads import validate_output_dir

    run_dir = tmp_path / '00000000-0000-4000-8000-000000000001'
    evidence = run_dir / 'evidence'
    evidence.mkdir(parents=True)

    assert validate_output_dir(run_dir, evidence / 'reads') == evidence / 'reads'
    with pytest.raises(ValueError, match='owned evidence'):
        validate_output_dir(run_dir, tmp_path / 'elsewhere')


def test_manifest_preflight_rejects_wrong_mode_and_repository(tmp_path):
    from scripts.validation.profile_report_reads import preflight_run_manifest

    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'runtime-manifest.json').write_text(
        '{"execution_mode":"manual","repository":"D:/elsewhere","run_dir":"D:/elsewhere/run"}',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='synthetic'):
        preflight_run_manifest(run_dir)


@pytest.mark.django_db(transaction=True)
def test_small_real_git_read_fixture_uses_public_writers(tmp_path):
    from project_management.app.api.report_queries import ReportWorkspaceQuery
    from scripts.validation.report_read_fixtures import create_report_read_fixture

    fixture = create_report_read_fixture(tmp_path, captures=2, publications=3, revisions_per_draft=2)
    page = fixture.query_service.workspace(
        fixture.actor,
        fixture.project_id,
        fixture.stage_id,
        query=ReportWorkspaceQuery(page_size=20),
    )

    assert len(page.captures.items) == 2
    assert len(page.drafts.items) == 3
    assert len(page.publications.items) == 3
    assert fixture.fixture_digest
    assert fixture.source_commit == page.archive_head
    assert all(row.state == 'finalized' for row in page.drafts.items)


@pytest.mark.django_db(transaction=True)
def test_standalone_scale_probe_materializes_revision5_native_publications(tmp_path):
    from project_management.app.api.report_queries import ReportWorkspaceQuery
    from project_management.app.domain.capture_values import decode_json
    from scripts.validation.report_read_fixtures import create_standalone_scale_fixture

    fixture = create_standalone_scale_fixture(tmp_path, captures=3, publications=3, revisions_per_draft=5)
    page = fixture.query_service.workspace(
        fixture.actor,
        fixture.project_id,
        fixture.stage_id,
        query=ReportWorkspaceQuery(page_size=20),
    )

    assert len(page.captures.items) == 3
    assert len(page.publications.items) == 3
    assert {row.revision for row in page.drafts.items} == {5}
    for packet in fixture.publication_packets:
        assert packet.publication.manifest.draft_revision == 5
        snapshot = decode_json(packet.files['snapshot.json'])
        assert snapshot['schema_version'] == 1
        assert len(snapshot['rows']) == 3
        assert snapshot['source_commit'] == fixture.source_commit
        assert packet.publication.commit_id == fixture.query_service.drafts.get_publication(
            fixture.actor,
            fixture.project_id,
            fixture.stage_id,
            packet.publication.manifest.publication_id,
        ).commit_id


@pytest.mark.django_db(transaction=True)
def test_s1_scale_fixture_materializes_100_native_publications(tmp_path):
    from project_management.app.api.report_queries import ReportWorkspaceQuery
    from scripts.validation.report_read_fixtures import create_standalone_scale_fixture

    fixture = create_standalone_scale_fixture(tmp_path, captures=100, publications=100, revisions_per_draft=5)
    page = fixture.query_service.workspace(
        fixture.actor,
        fixture.project_id,
        fixture.stage_id,
        query=ReportWorkspaceQuery(page_size=20),
    )

    assert len(fixture.capture_ids) == 100
    assert len(fixture.draft_ids) == 100
    assert len(fixture.publication_ids) == 100
    assert len(fixture.publication_packets) == 100
    assert len(page.captures.items) == 20
    assert len(page.drafts.items) == 20
    assert len(page.publications.items) == 20
    assert {row.revision for row in page.drafts.items} == {5}
    assert all(packet.publication.manifest.draft_revision == 5 for packet in fixture.publication_packets)
