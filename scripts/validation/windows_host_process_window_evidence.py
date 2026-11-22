"""Derive terminal ownership claims from the frozen raw observation evidence."""
from __future__ import annotations

import json
import re

from scripts.validation.windows_host_process_window import owner_registrations_by_instance
from scripts.validation.windows_qualification_inputs import QualificationError


def _json_equal(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _rows(value, label):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise QualificationError(f"invalid process window {label}")
    return value


def check_window_terminal_facts(window: dict) -> list[dict]:
    facts = []
    for snapshot in window.get("snapshots", []):
        facts.extend(_check_snapshot(window, snapshot))
    return facts


def _check_snapshot(window, snapshot):
    from scripts.validation.windows_host_process_identity import RELEVANCE_WORKLOAD, classify_process_observations

    classification = snapshot.get("process_classification") or {}
    claims = _rows(classification.get("processes", []), "classifications")
    raw = _rows(snapshot.get("processes", []), "raw observations")
    declared = _rows(snapshot.get("process_owner_registrations", []), "registrations")
    registrations = owner_registrations_by_instance(declared, window.get("id"))
    if len(registrations) != len(declared):
        raise QualificationError("invalid native owner registration")
    owned = snapshot.get("observed_owned_identities")
    if (not isinstance(owned, list) or any(not isinstance(value, str) or not value for value in owned)
            or len(set(owned)) != len(owned)):
        raise QualificationError("process admission input is missing or malformed")
    facts = _rows(snapshot.get("process_resolution_facts", []), "resolution facts")
    if "process_resolution_facts" in classification and not _json_equal(classification["process_resolution_facts"], facts):
        raise QualificationError("contradictory process resolution mirror")
    seen_pids = set()
    for row in raw:
        pid = row.get("pid")
        if type(pid) is not int or pid < 0:
            raise QualificationError("invalid native census PID")
        if pid in seen_pids:
            raise QualificationError("duplicate native census PID")
        seen_pids.add(pid)
        relevance = row.get("relevance")
        if relevance not in RELEVANCE_WORKLOAD or row.get("metrics_workload") is not RELEVANCE_WORKLOAD[relevance]:
            raise QualificationError("inconsistent process relevance")
        identity = row.get("identity")
        if identity is not None and (not isinstance(identity, str) or not identity):
            raise QualificationError("invalid process identity")
        fingerprint = row.get("command_fingerprint")
        if fingerprint is not None and (
            not isinstance(fingerprint, dict) or not isinstance(fingerprint.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", fingerprint["sha256"])
        ):
            raise QualificationError("invalid observed command fingerprint")
        native = row.get("process_window") or {}
        if native.get("handle_opened") is True and (
            native.get("handle_closed") is not True or native.get("handle_close_error")
        ):
            raise QualificationError("native observation release was not successful")
    replayed = classify_process_observations(
        raw, owned_identities=set(owned), owned_process_facts=declared, current_run_id=window.get("id"),
    )
    if (replayed["certification_blockers"]
            or not _json_equal(classification.get("certification_blockers"), replayed["certification_blockers"])
            or not _json_equal(claims, replayed["processes"])
            or not _json_equal(facts, replayed["process_resolution_facts"])):
        raise QualificationError("process classification differs from raw replay")
    return replayed["process_resolution_facts"]


def check_terminal_resolution_cleanup(window: dict, cleanup: dict) -> None:
    facts = check_window_terminal_facts(window)
    cleanup_rows = [
        row
        for phase in (cleanup.get("services") or {}).values()
        for observed in (phase.get("observations") or {}).values()
        for row in (observed.get("owned_processes") or {}).values()
        if isinstance(row, dict)
    ]
    for fact in facts:
        matched = [
            row for row in cleanup_rows
            if row.get("pid") == fact["pid"] and row.get("native_creation") == fact["native_creation"]
            and row.get("run_id") == fact["run_id"]
            and type(row.get("terminal_exit_code")) is int and row["terminal_exit_code"] == 0
            and row.get("process_running") is False
        ]
        if len(matched) != 1:
            raise QualificationError("terminal process cleanup proof missing")
