#!/usr/bin/env python3
"""Configurable file-size limit checker for repository files.

Every selected file must be claimed by a limit rule or by an explicit exemption: an unclaimed
file fails, so a new source family cannot grow without a cap. Files that were already above
their cap may carry a legacy allowance. In changed-file mode such a file may not grow more than
the allowance over the --base revision; explicit-path and --all runs stay strict so the
remaining debt stays visible.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(".github/file-size-limits.json")
GIT = ("git", "-c", "core.quotepath=off")


@dataclass(frozen=True, slots=True)
class LimitRule:
    name: str
    patterns: tuple[str, ...]
    max_lines: int


@dataclass(frozen=True, slots=True)
class ExemptionRule:
    name: str
    patterns: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class LegacyAllowanceRule:
    name: str
    patterns: tuple[str, ...]
    max_added_lines: int
    reason: str


@dataclass(frozen=True, slots=True)
class FileSizeConfig:
    include_untracked: bool
    rules: tuple[LimitRule, ...]
    exemptions: tuple[ExemptionRule, ...]
    legacy_allowances: tuple[LegacyAllowanceRule, ...]


@dataclass(frozen=True, slots=True)
class FileSizeFinding:
    path: Path
    line_count: int
    max_lines: int
    rule_name: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class FileSizeReport:
    checked: int
    findings: tuple[FileSizeFinding, ...]
    unclaimed: tuple[Path, ...]
    legacy_passes: tuple[FileSizeFinding, ...]


def main() -> None:
    parser = argparse.ArgumentParser(description="Check configured line-count limits for repository files.")
    parser.add_argument("paths", nargs="*", help="Explicit files to check strictly. Defaults to changed files.")
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Git base for changed-file discovery and legacy allowances. Default: HEAD.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Strictly check every repository file, including legacy debt. "
            "Combine with --include-untracked to cover new files."
        ),
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to file-size limit JSON config.")
    parser.add_argument("--include-untracked", dest="include_untracked", action="store_true", default=None)
    parser.add_argument("--no-include-untracked", dest="include_untracked", action="store_false")
    args = parser.parse_args()

    repo_root = repo_root_path()
    try:
        config = load_config(repo_root / args.config)
    except FileNotFoundError as exc:
        print(f"FAIL {exc}")
        raise SystemExit(1) from exc
    include_untracked = config.include_untracked if args.include_untracked is None else args.include_untracked
    paths = select_paths(
        repo_root,
        explicit=args.paths,
        base=args.base,
        check_all=args.all,
        include_untracked=include_untracked,
    )
    report = check_paths(
        repo_root,
        paths,
        config,
        base=args.base,
        allow_legacy_delta=not args.all and not args.paths,
    )
    for finding in report.legacy_passes:
        print(f"LEGACY {finding.path.as_posix()}: {finding.line_count} lines > limit {finding.max_lines} [{finding.detail}]")
    for path in report.unclaimed:
        print(
            f"FAIL {path.as_posix()}: no file-size rule or exemption claims this file; "
            "add a rule for its source family or an exemption with a reason"
        )
    for finding in report.findings:
        detail = f" [{finding.detail}]" if finding.detail else ""
        print(
            f"FAIL {finding.path.as_posix()}: {finding.line_count} lines > "
            f"limit {finding.max_lines} ({finding.rule_name}){detail}"
        )
    if report.findings or report.unclaimed:
        raise SystemExit(1)
    if report.checked == 0:
        print("FAIL file-size limits checked=0 (no files selected; widen --base or pass explicit paths)")
        raise SystemExit(1)
    print(f"PASS file-size limits checked={report.checked}")


def load_config(path: Path) -> FileSizeConfig:
    if not path.is_file():
        raise FileNotFoundError(f"file-size limit config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(
        LimitRule(
            name=str(item["name"]),
            patterns=tuple(str(pattern) for pattern in item.get("patterns", [])),
            max_lines=int(item["max_lines"]),
        )
        for item in payload.get("rules", [])
    )
    exemptions = tuple(
        ExemptionRule(
            name=str(item["name"]),
            patterns=tuple(str(pattern) for pattern in item.get("patterns", [])),
            reason=str(item.get("reason") or "not specified"),
        )
        for item in payload.get("exemptions", [])
    )
    legacy_allowances = tuple(
        LegacyAllowanceRule(
            name=str(item["name"]),
            patterns=tuple(str(pattern) for pattern in item.get("patterns", [])),
            max_added_lines=int(item["max_added_lines"]),
            reason=str(item.get("reason") or "not specified"),
        )
        for item in payload.get("legacy_over_limit_allowances", [])
    )
    return FileSizeConfig(
        include_untracked=bool(payload.get("include_untracked", True)),
        rules=rules,
        exemptions=exemptions,
        legacy_allowances=legacy_allowances,
    )


def check_paths(
    repo_root: Path,
    paths: list[Path],
    config: FileSizeConfig,
    *,
    base: str = "HEAD",
    allow_legacy_delta: bool = True,
) -> FileSizeReport:
    checked = 0
    findings: list[FileSizeFinding] = []
    unclaimed: list[Path] = []
    legacy_passes: list[FileSizeFinding] = []
    for relative_path in paths:
        path = normalize_relative_path(repo_root, relative_path)
        absolute_path = repo_root / path
        if not absolute_path.is_file() or is_exempt(path, config):
            continue
        rule = matching_rule(path, config)
        if rule is None:
            unclaimed.append(path)
            continue
        checked += 1
        line_count = line_count_for(absolute_path)
        if line_count <= rule.max_lines:
            continue
        finding = FileSizeFinding(path=path, line_count=line_count, max_lines=rule.max_lines, rule_name=rule.name)
        allowance = legacy_allowance_for(path, config)
        if allowance is None:
            findings.append(finding)
            continue
        verdict, detail = legacy_verdict(
            repo_root,
            path,
            allowance,
            base=base,
            line_count=line_count,
            max_lines=rule.max_lines,
            allow_legacy_delta=allow_legacy_delta,
        )
        target = legacy_passes if verdict else findings
        target.append(FileSizeFinding(path, line_count, rule.max_lines, rule.name, detail))
    return FileSizeReport(
        checked=checked,
        findings=tuple(findings),
        unclaimed=tuple(unclaimed),
        legacy_passes=tuple(legacy_passes),
    )


def legacy_verdict(
    repo_root: Path,
    path: Path,
    allowance: LegacyAllowanceRule,
    *,
    base: str,
    line_count: int,
    max_lines: int,
    allow_legacy_delta: bool,
) -> tuple[bool, str]:
    if not allow_legacy_delta:
        return False, f"legacy allowance {allowance.name} applies to changed-file mode only; split the file"
    base_count = git_file_line_count(repo_root, base, path)
    if base_count is None or base_count <= max_lines:
        return False, f"legacy allowance {allowance.name} covers only files already over the limit at {base}"
    allowed = base_count + allowance.max_added_lines
    detail = f"legacy allowance {allowance.name}: {base} has {base_count} lines, at most {allowed} allowed"
    return line_count <= allowed, detail


def matching_rule(path: Path, config: FileSizeConfig) -> LimitRule | None:
    normalized = path.as_posix()
    for rule in config.rules:
        if any(matches(normalized, pattern) for pattern in rule.patterns):
            return rule
    return None


def is_exempt(path: Path, config: FileSizeConfig) -> bool:
    normalized = path.as_posix()
    return any(matches(normalized, pattern) for exemption in config.exemptions for pattern in exemption.patterns)


def legacy_allowance_for(path: Path, config: FileSizeConfig) -> LegacyAllowanceRule | None:
    normalized = path.as_posix()
    for allowance in config.legacy_allowances:
        if any(matches(normalized, pattern) for pattern in allowance.patterns):
            return allowance
    return None


def repo_root_path() -> Path:
    output = subprocess.check_output([*GIT, "rev-parse", "--show-toplevel"], text=True).strip()
    return Path(output)


def select_paths(
    repo_root: Path,
    *,
    explicit: list[str],
    base: str,
    check_all: bool,
    include_untracked: bool,
) -> list[Path]:
    if explicit:
        return sorted({normalize_relative_path(repo_root, Path(item)) for item in explicit})
    if check_all:
        every = set(git_paths(repo_root, ["ls-files"]))
        if include_untracked:
            every.update(git_paths(repo_root, ["ls-files", "--others", "--exclude-standard"]))
        return sorted(every)
    changed = set(git_paths(repo_root, ["diff", "--name-only", base]))
    changed.update(git_paths(repo_root, ["diff", "--cached", "--name-only"]))
    if include_untracked:
        changed.update(git_paths(repo_root, ["ls-files", "--others", "--exclude-standard"]))
    return sorted(changed)


def git_paths(repo_root: Path, arguments: list[str]) -> list[Path]:
    output = subprocess.check_output([*GIT, *arguments], cwd=repo_root, text=True, encoding="utf-8")
    return [Path(line.strip()) for line in output.splitlines() if line.strip()]


def git_file_line_count(repo_root: Path, base: str, path: Path) -> int | None:
    try:
        output = subprocess.check_output(
            [*GIT, "show", f"{base}:{path.as_posix()}"],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    return len(output.splitlines())


def normalize_relative_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve().relative_to(repo_root.resolve())
    return path


def matches(normalized_path: str, pattern: str) -> bool:
    return pattern_regex(pattern).match(normalized_path) is not None


@functools.lru_cache(maxsize=None)
def pattern_regex(pattern: str) -> re.Pattern[str]:
    # fnmatch lets `*` cross `/`, which silently widens a rule to nested files it was never
    # written for. Here `**/` spans zero or more directories, `**` spans anything, and `*`/`?`
    # stay inside one path segment.
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts) + r"\Z")


def line_count_for(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    main()
