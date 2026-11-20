from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ASSET = {"url": "/static/app.js", "status": 200, "bytes": 42, "sha256": "a" * 64}


def performance_page_payload(*, blocks: int = 4, per_block: int = 40) -> dict:
    pages = {}
    for mode in ("seq", "c4"):
        pages[mode] = {}
        for page in ("home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend"):
            pages[mode][page] = {}
            for arm in ("baseline", "candidate", "candidate_saturated"):
                ms = 10.0 if arm == "baseline" else 11.0
                pages[mode][page][arm] = [
                    {
                        "block": block,
                        "sample": sample,
                        "ms": ms,
                        "html_ms": 2.0,
                        "status": 200,
                        "started": 1000.0 + block * 10 + sample * 0.01,
                        "ended": 1000.01 + block * 10 + sample * 0.01,
                        "assets": [deepcopy(ASSET)],
                    }
                    for block in range(blocks)
                    for sample in range(per_block)
                ]
    return {"pages": pages}


def performance_transport_payload(*, spacing_events: int = 50, slots: int = 10) -> dict:
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
            "resource": "/ai/assets/runtime.js",
            "scheduled": scheduled,
            "started": scheduled + 0.04,
            "ended": scheduled + 0.06,
            "ms": 20.0,
            "status": 200,
            "content_sha256": "b" * 64,
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


def performance_measurement_payload(*, blocks: int = 4, per_block: int = 40) -> dict:
    payload = performance_page_payload(blocks=blocks, per_block=per_block)
    payload.update(performance_transport_payload())
    payload["recipe"] = {
        "blocks": blocks,
        "per_block": per_block,
        "warmup": 10 if blocks == 4 else 1,
        "spacing_events": 50,
    }
    return payload


def write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path

