#!/usr/bin/env python3
"""Configurable file-size limit checker for changed source files."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(".github/file-size-limits.json")


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
class FileSizeConfig:
    include_untracked: bool
    rules: tuple[LimitRule, ...]
    exemptions: tuple[ExemptionRule, ...]


@dataclass(frozen=True, slots=True)
class FileSizeFinding:
    path: Path
    line_count: int
    max_lines: int
    rule_name: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Check configured line-count limits for source files.")
    parser.add_argument("paths", nargs="*", help="Explicit files to check. Defaults to changed files.")
    parser.add_argument("--base", default="HEAD", help="Git base for changed-file discovery. Default: HEAD.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check every repository file instead of changed files. Combine with --include-untracked to cover new files.",
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
    checked, findings = check_paths(repo_root, paths, config)
    for finding in findings:
        print(
            f"FAIL {finding.path}: {finding.line_count} lines > "
            f"limit {finding.max_lines} ({finding.rule_name})"
        )
    if findings:
        raise SystemExit(1)
    if checked == 0:
        print("FAIL file-size limits checked=0 (no files selected; widen --base or pass explicit paths)")
        raise SystemExit(1)
    print(f"PASS file-size limits checked={checked}")


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
    return FileSizeConfig(
        include_untracked=bool(payload.get("include_untracked", True)),
        rules=rules,
        exemptions=exemptions,
    )


def check_paths(repo_root: Path, paths: list[Path], config: FileSizeConfig) -> tuple[int, list[FileSizeFinding]]:
    checked = 0
    findings: list[FileSizeFinding] = []
    for relative_path in paths:
        path = normalize_relative_path(repo_root, relative_path)
        absolute_path = repo_root / path
        if not absolute_path.is_file() or is_exempt(path, config):
            continue
        rule = matching_rule(path, config)
        if rule is None:
            continue
        checked += 1
        line_count = line_count_for(absolute_path)
        if line_count > rule.max_lines:
            findings.append(FileSizeFinding(path=path, line_count=line_count, max_lines=rule.max_lines, rule_name=rule.name))
    return checked, findings


def matching_rule(path: Path, config: FileSizeConfig) -> LimitRule | None:
    normalized = path.as_posix()
    for rule in config.rules:
        if any(matches(normalized, pattern) for pattern in rule.patterns):
            return rule
    return None


def is_exempt(path: Path, config: FileSizeConfig) -> bool:
    normalized = path.as_posix()
    return any(matches(normalized, pattern) for exemption in config.exemptions for pattern in exemption.patterns)


def repo_root_path() -> Path:
    output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
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
        every = set(git_paths(["git", "ls-files"]))
        if include_untracked:
            every.update(git_paths(["git", "ls-files", "--others", "--exclude-standard"]))
        return sorted(every)
    changed = set(git_paths(["git", "diff", "--name-only", base]))
    changed.update(git_paths(["git", "diff", "--cached", "--name-only"]))
    if include_untracked:
        changed.update(git_paths(["git", "ls-files", "--others", "--exclude-standard"]))
    return sorted(changed)


def git_paths(command: list[str]) -> list[Path]:
    output = subprocess.check_output(command, text=True)
    return [Path(line.strip()) for line in output.splitlines() if line.strip()]


def normalize_relative_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve().relative_to(repo_root)
    return path


def matches(normalized_path: str, pattern: str) -> bool:
    candidates = {pattern, pattern.removeprefix("**/")}
    if "/**/" in pattern:
        candidates.add(pattern.replace("/**/", "/"))
    return any(path_pattern_matches(normalized_path, candidate) for candidate in candidates)


def path_pattern_matches(normalized_path: str, pattern: str) -> bool:
    if "/" not in pattern and "/" in normalized_path:
        return False
    return fnmatch.fnmatchcase(normalized_path, pattern)


def line_count_for(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    main()
