#!/usr/bin/env python3
"""Whitespace gate that includes untracked text files."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
}


@dataclass(frozen=True, slots=True)
class WhitespaceFinding:
    path: Path
    line_number: int
    message: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whitespace errors in tracked diffs and untracked text files.")
    parser.add_argument("paths", nargs="*", help="Optional file or directory paths to limit untracked-file checks.")
    parser.add_argument("--include-untracked", action="store_true", help="Also inspect untracked text files.")
    args = parser.parse_args()

    repo_root = repo_root_path()
    tracked_failed = run_git_diff_check(["git", "diff", "--check"])
    cached_failed = run_git_diff_check(["git", "diff", "--cached", "--check"])
    findings = check_untracked_files(repo_root, args.paths) if args.include_untracked else []

    for finding in findings:
        print(f"FAIL {finding.path}:{finding.line_number}: {finding.message}")

    if tracked_failed or cached_failed or findings:
        raise SystemExit(1)

    print("PASS diff whitespace")


def repo_root_path() -> Path:
    output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    return Path(output)


def run_git_diff_check(command: list[str]) -> bool:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode != 0


def check_untracked_files(repo_root: Path, path_filters: list[str]) -> list[WhitespaceFinding]:
    untracked = git_paths(["git", "ls-files", "--others", "--exclude-standard"])
    selected = [path for path in untracked if is_selected(repo_root, path, path_filters)]
    findings: list[WhitespaceFinding] = []
    for relative_path in selected:
        if not should_check(relative_path):
            continue
        findings.extend(check_text_file(repo_root / relative_path, relative_path))
    return findings


def git_paths(command: list[str]) -> list[Path]:
    output = subprocess.check_output(command, text=True)
    return [Path(line.strip()) for line in output.splitlines() if line.strip()]


def is_selected(repo_root: Path, relative_path: Path, path_filters: list[str]) -> bool:
    if not path_filters:
        return True
    absolute_path = repo_root / relative_path
    for item in path_filters:
        filter_path = Path(item)
        if filter_path.is_absolute():
            try:
                filter_path = filter_path.resolve().relative_to(repo_root)
            except ValueError:
                continue
        if relative_path == filter_path or filter_path in relative_path.parents:
            return True
        if absolute_path == repo_root / filter_path or (repo_root / filter_path) in absolute_path.parents:
            return True
    return False


def should_check(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def check_text_file(path: Path, relative_path: Path) -> list[WhitespaceFinding]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return []

    findings: list[WhitespaceFinding] = []
    for index, line in enumerate(lines, start=1):
        content = line.rstrip("\r\n")
        if content.endswith((" ", "\t")):
            findings.append(WhitespaceFinding(relative_path, index, "trailing whitespace"))
        if content in {"<<<<<<<", "=======", ">>>>>>>"} or content.startswith(("<<<<<<< ", ">>>>>>> ")):
            findings.append(WhitespaceFinding(relative_path, index, "conflict marker"))
    return findings


if __name__ == "__main__":
    main()
