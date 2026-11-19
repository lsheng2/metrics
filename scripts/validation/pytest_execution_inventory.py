"""Observe pytest execution without changing collection or outcomes."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from _pytest.junitxml import bin_xml_escape, mangle_test_address
from _pytest.stash import StashKey
from _pytest.subtests import SubtestReport
import pytest


_PLUGIN_KEY = StashKey["ExecutionInventoryPlugin"]()
INVENTORY_KIND = "pytest-execution-inventory"


def junit_identity(nodeid: str) -> str:
    names = mangle_test_address(nodeid)
    return bin_xml_escape(".".join(names[:-1])) + "::" + bin_xml_escape(names[-1])


def output_paths_match(args, raw: Path, inventory: Path) -> bool:
    for option, expected in (("--junitxml", raw), ("--execution-inventory", inventory)):
        if args.count(option) != 1:
            return False
        index = args.index(option) + 1
        if index >= len(args) or Path(args[index]) != expected:
            return False
    return True


class ExecutionInventoryPlugin:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.collected: dict[str, str] = {}
        self.collected_order: list[str] = []
        self.primary: Counter[str] = Counter()
        self.subtests: Counter[str] = Counter()
        self.nonpass_reports: list[dict[str, Any]] = []
        self.collection_reports: list[dict[str, Any]] = []
        self.deselected: list[str] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            self.collected[item.nodeid] = junit_identity(item.nodeid)
            self.collected_order.append(item.nodeid)

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected.extend(item.nodeid for item in items)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.passed:
            return
        self.collection_reports.append(
            {
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "longrepr": str(report.longrepr),
            }
        )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        wasxfail = getattr(report, "wasxfail", None)
        is_subtest = isinstance(report, SubtestReport)
        if report.outcome != "passed" or hasattr(report, "wasxfail"):
            self.nonpass_reports.append(
                {
                    "nodeid": report.nodeid,
                    "when": report.when,
                    "outcome": report.outcome,
                    "report_type": "subtest" if is_subtest else "primary",
                    "wasxfail": wasxfail,
                }
            )
            return
        if report.when != "call":
            return
        if is_subtest:
            self.subtests[report.nodeid] += 1
        else:
            self.primary[report.nodeid] += 1

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "kind": INVENTORY_KIND,
            "exitstatus": int(exitstatus),
            "pytest_args": [str(item) for item in session.config.invocation_params.args],
            "rootdir": str(session.config.rootpath),
            "inventory_path": str(self.output),
            "collected": self.collected,
            "collected_order": self.collected_order,
            "primary": dict(self.primary),
            "subtests": dict(self.subtests),
            "nonpass_reports": self.nonpass_reports,
            "collection_reports": self.collection_reports,
            "deselected": self.deselected,
        }
        with self.output.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("execution inventory")
    group.addoption(
        "--execution-inventory",
        action="store",
        default=None,
        help="Write a fail-closed pytest execution inventory JSON file.",
    )


def pytest_configure(config: pytest.Config) -> None:
    option = config.getoption("execution_inventory")
    if not option:
        return
    output = Path(option)
    if not output.is_absolute():
        raise pytest.UsageError("--execution-inventory output must be absolute")
    if output.exists():
        raise pytest.UsageError("--execution-inventory output must be fresh")
    plugin = ExecutionInventoryPlugin(output)
    config.stash[_PLUGIN_KEY] = plugin
    config.pluginmanager.register(plugin, "execution-inventory")


def pytest_unconfigure(config: pytest.Config) -> None:
    plugin = config.stash.get(_PLUGIN_KEY, None)
    if plugin is not None:
        config.pluginmanager.unregister(plugin)
