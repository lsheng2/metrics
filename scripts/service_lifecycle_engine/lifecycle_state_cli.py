from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit

from .engine import ServiceLifecycleEngine
from .live_status import read_process_started_at
from .models import LifecycleState, ProcessProvenance, ProvenanceCapability
from .state_recording import build_external_service_state


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record external launcher service lifecycle state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepared", "ready", "aborted", "stopped"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--workspace-root", required=True)
        command_parser.add_argument("--project-name", required=True)
        command_parser.add_argument("--instance-name", default="default")
        command_parser.add_argument("--service-id", required=True)
        command_parser.add_argument("--base-url", default="")
        command_parser.add_argument("--host", default="127.0.0.1")
        command_parser.add_argument("--port", type=int)
        command_parser.add_argument("--process-id", type=int)
        command_parser.add_argument("--listener-process-id", type=int)
        command_parser.add_argument("--started-at", default="")
        command_parser.add_argument("--stdout-log", default="")
        command_parser.add_argument("--stderr-log", default="")
        command_parser.add_argument("--health-url", default="")
        command_parser.add_argument("--launcher-id", default="")
        command_parser.add_argument("--launch-mode", default="")
        command_parser.add_argument("--process-start-time-ticks", default="")
        command_parser.add_argument("--command-fingerprint", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    host, port = _resolve_host_port(args)
    engine = ServiceLifecycleEngine(
        project_name=args.project_name,
        workspace=Path(args.workspace_root),
        instance_name=args.instance_name,
    )
    prior_state = engine.read_state().get(args.service_id)
    service_state = build_external_service_state(
        service_name=args.service_id,
        lifecycle_state=LifecycleState(args.command),
        host=host,
        port=port,
        pid=args.process_id or args.listener_process_id,
        started_at=_resolve_started_at(args),
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
        health_url=args.health_url or None,
        provenance=_provenance_from_args(args),
        prior_state=prior_state,
    )
    engine.record_service_state(service_state)
    return 0


def _resolve_host_port(args: argparse.Namespace) -> tuple[str, int]:
    if args.base_url:
        parsed = urlsplit(args.base_url.rstrip("/"))
        if not parsed.hostname or parsed.port is None:
            raise ValueError(f"{args.service_id} base-url must include host and port: {args.base_url}")
        return parsed.hostname, int(parsed.port)
    if args.port is None:
        raise ValueError(f"{args.service_id} requires --port when --base-url is not provided")
    return str(args.host or "127.0.0.1"), int(args.port)


def _resolve_started_at(args: argparse.Namespace) -> str:
    if args.started_at:
        return str(args.started_at)
    if args.command == "stopped":
        return ""
    process_id = args.listener_process_id or args.process_id
    if process_id:
        return read_process_started_at(process_id) or ""
    return ""


def _provenance_from_args(args: argparse.Namespace) -> ProcessProvenance | None:
    if not args.process_id and not args.listener_process_id:
        return None
    if args.command == "stopped" and not args.listener_process_id and not args.process_start_time_ticks and not args.command_fingerprint:
        return None
    capability = ProvenanceCapability.ENDPOINT_GRADE if args.listener_process_id else ProvenanceCapability.REGISTERED_PROCESS
    return ProcessProvenance(
        wrapper_pid=args.process_id,
        listener_pid=args.listener_process_id,
        process_start_marker=args.process_start_time_ticks,
        start_time=args.started_at,
        command_fingerprint=args.command_fingerprint,
        command_line=json.dumps(
            {"launcher_id": args.launcher_id, "launch_mode": args.launch_mode},
            sort_keys=True,
        ),
        capability=capability,
    )


if __name__ == "__main__":
    raise SystemExit(main())
