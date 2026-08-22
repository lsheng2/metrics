#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grafana_artifact_contract import json_artifacts, load_allowlist, validate_artifact_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Grafana artifacts against Metrics-owned data surfaces.")
    parser.add_argument("--artifact-root", required=True, help="Directory containing provisioned Grafana JSON artifacts.")
    parser.add_argument("--allowlist", required=True, help="JSON file describing approved Metrics data surfaces.")
    args = parser.parse_args()

    artifact_root = Path(args.artifact_root)
    allowlist = load_allowlist(Path(args.allowlist))
    findings = validate_artifact_root(artifact_root, allowlist)

    for finding in findings:
        print(f"FAIL {finding.path}: {finding.message}")

    if findings:
        raise SystemExit(1)

    print(f"PASS grafana artifacts checked={len(json_artifacts(artifact_root))}")


if __name__ == "__main__":
    main()
