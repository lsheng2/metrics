import json

import pytest
from jsonschema import Draft202012Validator

from project_management.app.api.ai_profiles import load_task_profile, load_task_profiles
from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.summary_contracts import AnalysisError


def test_profiles_are_metrics_owned_versioned_data_without_sdk_wire_pack():
    profiles = load_task_profiles()
    assert {profile.id for profile in profiles} == {
        'metrics.project_summary', 'metrics.report_authoring',
    }
    for profile in profiles:
        assert profile.version == {'metrics.project_summary': '2', 'metrics.report_authoring': '1'}[profile.id]
        assert profile.instructions
        assert profile.output_schema_sha256 == content_hash(profile.output_schema)
        assert profile.definition_sha256 == content_hash(profile.definition)
        for schema in (profile.input_schema, profile.output_schema):
            Draft202012Validator.check_schema(schema)
            assert '"$ref"' not in json.dumps(schema)
            assert 'task-run/1' not in json.dumps(schema)
        assert profile.__class__.__module__.startswith('project_management.')


def test_loaded_profile_schema_does_not_share_mutable_state():
    profile = load_task_profile('metrics.project_summary')
    original = profile.definition_sha256
    schema = profile.input_schema
    schema.clear()
    assert profile.input_schema
    assert profile.definition_sha256 == original


def test_unknown_profile_is_not_replaced_with_a_default():
    with pytest.raises(AnalysisError, match='selected AI contract'):
        load_task_profile('metrics.unknown')


def test_profile_revisions_use_new_exact_business_identity():
    for profile in load_task_profiles():
        serialized = json.dumps(profile.definition)
        assert 'project-reporting.summary@review-1' not in serialized
        assert 'project-reporting.authoring@1' not in serialized
        assert profile.definition['id'] == profile.id
        assert profile.definition['version'] == profile.version
    summary = load_task_profile('metrics.project_summary')
    assert 'metrics.project_summary@2' in json.dumps(summary.input_schema)
    assert 'metrics.project_summary@2' in json.dumps(summary.output_schema)


def test_metrics_package_registers_the_owned_profiles():
    from ai_base_runtime.testkit import check_app_package
    from ai_host.package import METRICS_APP
    from ai_host.settings import build_runtime_settings

    declared = {profile.id: profile for profile in METRICS_APP.task_profiles}
    assert set(declared) == {'metrics.project_summary', 'metrics.report_authoring'}
    for profile in load_task_profiles():
        actual = declared[profile.id]
        assert actual.version == profile.version
        assert actual.definition_digest == profile.definition_sha256
        assert content_hash(actual.input_schema) == content_hash(profile.input_schema)
        assert content_hash(actual.output_schema) == profile.output_schema_sha256
    check_app_package(METRICS_APP, limits=build_runtime_settings().limits)
