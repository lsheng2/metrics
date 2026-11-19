from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_file_size_limits.py"
SPEC = importlib.util.spec_from_file_location("check_file_size_limits", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
size_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = size_gate
SPEC.loader.exec_module(size_gate)


def _write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["line"] * count), encoding="utf-8")


def _config(*rules, exemptions=(), legacy_allowances=()) -> object:
    return size_gate.FileSizeConfig(
        include_untracked=True,
        rules=tuple(rules),
        exemptions=tuple(exemptions),
        legacy_allowances=tuple(legacy_allowances),
    )


def _legacy_config(max_added_lines: int) -> object:
    return _config(
        size_gate.LimitRule("stylesheet", ("web/css/**/*.css",), 5),
        legacy_allowances=(
            size_gate.LegacyAllowanceRule("legacy-css", ("web/css/main.css",), max_added_lines, "Owner: x. Split plan: y."),
        ),
    )


def test_first_matching_rule_judges_the_file(tmp_path: Path) -> None:
    _write_lines(tmp_path / "web" / "css" / "page.css", 4)
    config = _config(
        size_gate.LimitRule("page-css", ("web/css/*.css",), 3),
        size_gate.LimitRule("any-css", ("**/*.css",), 10),
    )

    report = size_gate.check_paths(tmp_path, [Path("web/css/page.css")], config)

    assert report.checked == 1
    assert report.findings == (size_gate.FileSizeFinding(Path("web/css/page.css"), 4, 3, "page-css"),)


def test_exempt_file_is_neither_checked_nor_unclaimed(tmp_path: Path) -> None:
    _write_lines(tmp_path / "vendor" / "lib.js", 50)
    config = _config(
        size_gate.LimitRule("js", ("**/*.js",), 1),
        exemptions=(size_gate.ExemptionRule("vendored", ("vendor/**",), "third party"),),
    )

    report = size_gate.check_paths(tmp_path, [Path("vendor/lib.js")], config)

    assert (report.checked, report.findings, report.unclaimed) == (0, (), ())


def test_file_without_rule_or_exemption_is_reported_unclaimed(tmp_path: Path) -> None:
    _write_lines(tmp_path / "web" / "css" / "page.css", 9000)
    config = _config(size_gate.LimitRule("python", ("**/*.py",), 400))

    report = size_gate.check_paths(tmp_path, [Path("web/css/page.css")], config)

    assert report.checked == 0
    assert report.unclaimed == (Path("web/css/page.css"),)


def test_star_stays_inside_one_segment_while_doublestar_spans_directories() -> None:
    matches = size_gate.matches

    assert matches("ui_web/frontend/scripts/build.mjs", "ui_web/frontend/scripts/*.mjs")
    assert not matches("ui_web/frontend/scripts/nested/build.mjs", "ui_web/frontend/scripts/*.mjs")
    assert matches("pytest.ini", "*.ini")
    assert not matches("tools/pytest.ini", "*.ini")
    assert matches("README.md", "**/*.md")
    assert matches("openspec/docs/current-baseline/ui.md", "**/*.md")
    assert matches("ui_web/templates/base.html", "**/templates/**/*.html")
    assert matches("ui_web/templates/partials/a/b.html", "**/templates/**/*.html")
    assert not matches("ui_web/static/a.html", "**/templates/**/*.html")


def test_changed_mode_allows_only_bounded_growth_of_legacy_file(tmp_path: Path, monkeypatch) -> None:
    legacy_file = tmp_path / "web" / "css" / "main.css"
    _write_lines(legacy_file, 12)
    monkeypatch.setattr(size_gate, "git_file_line_count", lambda _root, _base, _path: 10)
    config = _legacy_config(max_added_lines=2)

    passing = size_gate.check_paths(tmp_path, [Path("web/css/main.css")], config, base="HEAD^")

    assert passing.findings == ()
    assert [finding.path for finding in passing.legacy_passes] == [Path("web/css/main.css")]

    _write_lines(legacy_file, 13)
    failing = size_gate.check_paths(tmp_path, [Path("web/css/main.css")], config, base="HEAD^")

    assert [(finding.line_count, finding.max_lines) for finding in failing.findings] == [(13, 5)]
    assert "HEAD^ has 10 lines, at most 12 allowed" in failing.findings[0].detail


@pytest.mark.parametrize("base_count", [None, 4, 5])
def test_allowance_never_covers_a_file_that_was_under_cap_at_base(tmp_path: Path, monkeypatch, base_count) -> None:
    _write_lines(tmp_path / "web" / "css" / "main.css", 6)
    monkeypatch.setattr(size_gate, "git_file_line_count", lambda _root, _base, _path: base_count)

    report = size_gate.check_paths(tmp_path, [Path("web/css/main.css")], _legacy_config(max_added_lines=50))

    assert [finding.path for finding in report.findings] == [Path("web/css/main.css")]
    assert "only files already over the limit" in report.findings[0].detail


def test_explicit_path_and_all_mode_ignore_legacy_allowances(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_lines(tmp_path / "web" / "css" / "main.css", 12)
    selected_modes: list[tuple[tuple[str, ...], bool]] = []

    def fake_select_paths(repo_root, *, explicit, base, check_all, include_untracked):
        selected_modes.append((tuple(explicit), check_all))
        return [Path("web/css/main.css")]

    monkeypatch.setattr(size_gate, "repo_root_path", lambda: tmp_path)
    monkeypatch.setattr(size_gate, "load_config", lambda _path: _legacy_config(max_added_lines=20))
    monkeypatch.setattr(size_gate, "select_paths", fake_select_paths)
    monkeypatch.setattr(size_gate, "git_file_line_count", lambda _root, _base, _path: 10)

    for argv in (["gate", "web/css/main.css"], ["gate", "--all"]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exit_info:
            size_gate.main()
        assert exit_info.value.code == 1
        assert "FAIL web/css/main.css: 12 lines > limit 5 (stylesheet)" in capsys.readouterr().out

    assert selected_modes == [(("web/css/main.css",), False), ((), True)]


def _repository_config() -> object:
    return size_gate.load_config(ROOT / ".github" / "file-size-limits.json")


def test_every_tracked_repository_file_is_claimed_by_a_rule_or_an_exemption() -> None:
    config = _repository_config()
    tracked = size_gate.select_paths(ROOT, explicit=[], base="HEAD", check_all=True, include_untracked=False)

    unclaimed = sorted(
        path.as_posix()
        for path in tracked
        if size_gate.matching_rule(path, config) is None and not size_gate.is_exempt(path, config)
    )

    assert unclaimed == [], f"add a rule for the source family or an exemption with a reason: {unclaimed}"


def test_legacy_allowances_name_an_owner_and_still_cover_over_cap_files() -> None:
    config = _repository_config()
    stale: list[str] = []
    for allowance in config.legacy_allowances:
        assert "Owner:" in allowance.reason and "Split plan:" in allowance.reason, allowance.name
        for pattern in allowance.patterns:
            path = ROOT / pattern
            rule = size_gate.matching_rule(Path(pattern), config)
            if not path.is_file() or rule is None or size_gate.line_count_for(path) <= rule.max_lines:
                stale.append(pattern)

    assert stale == [], f"delete legacy allowances for files that are gone or back under their cap: {stale}"
