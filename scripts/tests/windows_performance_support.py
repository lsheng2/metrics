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
        "recipe_id": "windows-mdb2-s0b-r1",
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
                str(pid): {"pid": pid, "role": "service_root", "terminal_exit_code": 0, "process_running": False}
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
