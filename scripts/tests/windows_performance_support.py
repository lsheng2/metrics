from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ASSET = {"url": "/static/app.js", "status": 200, "bytes": 42, "sha256": "a" * 64}


def performance_page_payload(*, blocks: int = 4, per_block: int = 40) -> dict:
    pages, block_rows = {}, []
    cell_index = 0
    for mode in ("seq", "c4"):
        pages[mode] = {}
        for page in ("home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend"):
            pages[mode][page] = {}
            for block in range(blocks):
                order = (
                    ("baseline", "candidate", "candidate_saturated")
                    if block % 2 == 0 else
                    ("candidate_saturated", "candidate", "baseline")
                )
                for arm in order:
                    block_start = 201.0 + cell_index * 0.05
                    block_end = block_start + 0.04
                    block_rows.append({
                        "mode": mode, "page": page, "block": block, "arm": arm,
                        "started": block_start, "ended": block_end,
                    })
                    cell_index += 1
            for arm in ("baseline", "candidate", "candidate_saturated"):
                ms = 10.0 if arm == "baseline" else 11.0
                pages[mode][page][arm] = [
                    {
                        "block": block,
                        "sample": sample,
                        "ms": ms,
                        "html_ms": 2.0,
                        "status": 200,
                        "started": _sample_started(block_rows, mode, page, block, arm, sample),
                        "ended": _sample_started(block_rows, mode, page, block, arm, sample) + ms / 1000,
                        "assets": [deepcopy(ASSET)],
                    }
                    for block in range(blocks)
                    for sample in range(per_block)
                ]
    return {"pages": pages, "blocks": block_rows}


def _sample_started(block_rows, mode, page, block, arm, sample):
    block_row = next(
        row for row in block_rows
        if (row["mode"], row["page"], row["block"], row["arm"]) == (mode, page, block, arm)
    )
    return block_row["started"] + sample * 0.0005


def performance_transport_payload(*, spacing_events: int = 50, slots: int = 10, asset_prefix: str = "/ai/assets/") -> dict:
    started = 100.0
    saturation_start = 200.0
    probes = []
    for slot in range(slots):
        scheduled = saturation_start + slot
        probes.append({
            "slot": slot,
            "kind": "loop_short",
            "resource": "/ai/apps/metrics/api/qualification/echo",
            "scheduled": scheduled,
            "started": scheduled + 0.01,
            "ended": scheduled + 0.03,
            "ms": 20.0,
            "status": 200,
        })
        probes.append({
            "slot": slot,
            "kind": "direct_asset",
            "resource": f"{asset_prefix}runtime.js",
            "scheduled": scheduled,
            "started": scheduled + 0.04,
            "ended": scheduled + 0.06,
            "ms": 20.0,
            "status": 200,
            "content_sha256": "b" * 64,
            "etag": '"sha256-bbbbbbbbbbbb"',
        })
        if slot % 5 == 0:
            probes.append({
                "slot": slot,
                "kind": "excess_stream",
                "resource": "/ai/apps/metrics/api/qualification/active",
                "scheduled": scheduled,
                "started": scheduled + 0.07,
                "ended": scheduled + 0.09,
                "ms": 20.0,
                "status": 503,
                "retry_after": "2",
            })
    return {
        "spacing": {
            "started": started,
            "arrivals": [started + 0.05 + index / 10 for index in range(spacing_events)],
            "indices": list(range(spacing_events)),
        },
        "saturation": {
            "started": saturation_start,
            "ended": saturation_start + slots,
            "opened": ["active", "idle", "idle", "idle"],
            "closed": 4,
            "errors": [],
            "after": {"streamInFlightCount": 0, "shortInFlightCount": 0},
            "probes": probes,
        },
    }


def performance_measurement_payload(*, blocks: int = 4, per_block: int = 40, warmup: int = 10) -> dict:
    payload = performance_page_payload(blocks=blocks, per_block=per_block)
    payload["sanity"] = {
        arm: {page: deepcopy(arms[arm][0]) for page, arms in payload["pages"]["seq"].items()}
        for arm in ("baseline", "candidate", "candidate_saturated")
    }
    payload.update(performance_transport_payload())
    payload["recipe"] = {
        "blocks": blocks,
        "per_block": per_block,
        "warmup": warmup,
        "spacing_events": 50,
        "require_direct_asset": True,
    }
    return payload


def resolved_inputs_payload(
    *, production: bool = False, asset_prefix: str = "/ai/assets/",
    warmup: int = 10, blocks: int = 4, per_block: int = 40,
) -> dict:
    return {
        "mode": "certify",
        "phase": "production" if production else "development",
        "recipe_id": "windows-mdb2-s0b-r2",
        "settings": {
            "debug": not production,
            "production": production,
            "collected_static_files": 3 if production else 0,
        },
        "recipe": {
            "warmup": warmup,
            "blocks": blocks,
            "per_block": per_block,
            "spacing_events": 50,
            "require_direct_asset": True,
        },
        "asset_prefix": asset_prefix,
        "arms": {
            arm: {
                "base_url": f"http://127.0.0.1:{8100 + index}",
                "role": "baseline" if arm == "baseline" else "candidate",
                "pages": {
                    page: f"/{page}/" for page in (
                        "home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend"
                    )
                },
                "assets": {"/static/app.js": {"sha256": "a" * 64, "bytes": 42}},
                "worker_started": True,
                "worker_executed": [],
            }
            for index, arm in enumerate(("baseline", "candidate", "candidate_saturated"))
        },
        "direct_asset": {"url": f"{asset_prefix}runtime.js", "sha256": "b" * 64, "bytes": 12},
    }


def write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def artifact_ref(path: Path, payload: dict) -> dict:
    from scripts.validation.windows_qualification_inputs import digest_file

    write_json(path, payload)
    return {"path": str(path), "sha256": digest_file(path)}


def performance_identity_payloads(repo: Path, owned: Path) -> dict:
    from scripts.validation.windows_qualification_inputs import digest_file

    source_file = repo / "frozen.txt"
    source_file.write_text("frozen source\n", encoding="utf-8")
    fixture = write_json(owned / "fixtures" / "fixture.json", {"fixture": "stable"})
    vector = write_json(owned / "fixtures" / "fixture-vector.json", {
        "files": [{"path": str(fixture), "sha256": digest_file(fixture)}],
    })
    marker = write_json(owned / "owner.json", {
        "owner": "mdb2-windows-closure",
        "root": str(owned),
        "repository": str(repo),
    })
    return {
        "source": {
            "kind": "commit",
            "commit": "dashboard-source",
            "repository": str(repo),
            "files": [{"path": "frozen.txt", "sha256": digest_file(source_file)}],
        },
        "owned_root": {"path": str(owned), "marker": str(marker), "owner": "mdb2-windows-closure"},
        "fixtures": {
            "fixture_vector": {"path": str(vector), "sha256": digest_file(vector)},
            "fixture_vector_sha256": digest_file(vector),
            "files": [{"path": str(fixture), "sha256": digest_file(fixture)}],
        },
    }


def performance_driver_request(tmp_path: Path) -> dict:
    from scripts.tests.test_windows_performance_inputs import functional_acceptance_payload, performance_policy_payload
    from scripts.validation.windows_host_performance_contract import FUNCTIONAL_RELATIVE, POLICY_RELATIVE

    repo = tmp_path / "repo"
    repo.mkdir()
    identity = performance_identity_payloads(repo, tmp_path)
    proof = tmp_path / "functional-proof.json"
    artifact_ref(proof, {"status": "PASS"})
    inputs = tmp_path / "inputs.json"
    python = tmp_path / "venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("python", encoding="utf-8")
    environment = artifact_ref(tmp_path / "environment.json", environment_payload(python, tmp_path / "venv"))
    request = {
        "schema_version": 1,
        "acceptance_profile": "full",
        "performance": {"recipe_id": "windows-mdb2-s0b-r2", "mode": "certify"},
        "source": identity["source"],
        "python": {"candidate": str(python), "version": "3.13.7", "environments": {"candidate": environment}},
        "candidate": {
            "version": "1.0.0",
            "wheel": str(tmp_path / "wheels" / "ai_base_runtime-1.0.0-py3-none-any.whl"),
            "wheel_sha256": "c" * 64,
            "source_commit": "aib-source",
        },
        "owned_root": identity["owned_root"],
        "fixtures": identity["fixtures"],
        "_paths": {"inputs": inputs, "output": tmp_path / "out.json", "owned_root": tmp_path, "python": python},
    }
    request["performance"].update(
        policy_ref=artifact_ref(repo / POLICY_RELATIVE, performance_policy_payload(request)),
        functional_acceptance_ref=artifact_ref(repo / FUNCTIONAL_RELATIVE, functional_acceptance_payload(request, proof)),
    )
    artifact_ref(inputs, {key: value for key, value in request.items() if key != "_paths"})
    return request


def seal_receipt(receipt):
    import hashlib

    run = Path(receipt["run_directory"])
    path = run / "receipt.json"
    write_json(path, receipt)
    witness_path = run / "receipt-write-witness.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    witness["receipt_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(witness_path, witness)


def shift_measurement(value, offset):
    if isinstance(value, list):
        return [shift_measurement(row, offset) for row in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, child in value.items():
        if key in {"started", "ended", "scheduled"} and isinstance(child, (int, float)):
            result[key] = child + offset
        elif key == "arrivals":
            result[key] = [item + offset for item in child]
        else:
            result[key] = shift_measurement(child, offset)
    return result


def performance_phase_cleanup():
    services, observations = {}, {}
    for index, arm in enumerate(("baseline", "candidate", "candidate_saturated")):
        pid, port = 1000 + index, 8100 + index
        services[arm] = {
            "name": arm, "port": port, "pid": pid, "stopped": True,
            "forced": False, "force_requested": False, "reason": "stop_command",
            "exit_code": 0,
        }
        observations[arm] = {
            "pid": pid, "host": "127.0.0.1", "port": port,
            "process_running": False, "listener_pids": [], "observation_errors": [],
            "owned_processes": {
                str(pid): {
                    "pid": pid, "role": "service_root", "terminal_exit_code": 0, "process_running": False,
                    "native_creation": 90000 + index, "native_handle_opened": True, "native_handle_closed": True,
                }
            },
        }
    return {
        "services": services,
        "observations": observations,
        "normal": True,
        "owned_descendants_absent": True,
        "listeners_absent": True,
    }


def environment_payload(python, prefix):
    return {
        "executable": str(python),
        "python": "3.13.7",
        "packages": {"ai-base-runtime": {"version": "1.0.0", "location": str(prefix)}},
        "shadowed_distributions": {},
        "selected_imports": {"ai_base_runtime": str(prefix / "Lib/site-packages/ai_base_runtime/__init__.py")},
        "sys_path": [str(prefix / "Lib/site-packages")],
    }


def import_probe_payload(prefix, source):
    from scripts.validation.windows_install_smoke import PINS

    return {
        "prefix": str(prefix),
        "base_prefix": str(prefix.parent / "base-python"),
        "user_site": False,
        "legacy_sdk": False,
        "paths": [str(prefix / "Lib/site-packages"), str(source)],
        "versions": dict(PINS),
        "modules": {name: str(prefix / "Lib/site-packages" / name / "__init__.py") for name in PINS},
        "distributions": {name: str(prefix / "Lib/site-packages") for name in PINS},
        "unowned_pth": [],
    }
