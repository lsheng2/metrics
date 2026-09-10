#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_OVERLAY = Path(".github/skills/lsheng2-ui-design/templates/project-overlay.md")
DEFAULT_MANIFEST = Path(".github/skills/lsheng2-ui-design/visual-regression/manifest.json")
DEFAULT_REPORT_JSON = Path(".github/skills/lsheng2-ui-design/reports/ui-gate-report.json")
JSON_BLOCK_PATTERN = re.compile(r"```json (lsheng2-ui-design-[^\n]+)\n(.*?)\n```", re.DOTALL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep committed lsheng2-ui-design artifacts under repository line limits.")
    parser.add_argument("--project-root", default=".", help="Repository root.")
    parser.add_argument("--skip-overlay", action="store_true")
    parser.add_argument("--skip-manifest", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not args.skip_overlay:
        compact_overlay_blocks(project_root / DEFAULT_OVERLAY)
    if not args.skip_manifest:
        compact_json_file(project_root / DEFAULT_MANIFEST)
    if not args.skip_report:
        compact_json_file(project_root / DEFAULT_REPORT_JSON)
    return 0


def compact_overlay_blocks(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    def compact(match: re.Match) -> str:
        payload = json.loads(match.group(2))
        body = json.dumps(payload, separators=(",", ":"), sort_keys=False)
        return f"```json {match.group(1)}\n{body}\n```"

    path.write_text(JSON_BLOCK_PATTERN.sub(compact, text).rstrip() + "\n", encoding="utf-8", newline="\n")


def compact_json_file(path: Path) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
