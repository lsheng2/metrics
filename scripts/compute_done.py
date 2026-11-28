"""Report which acceptance features of an OpenSpec change are done.

Usage: python scripts/compute_done.py <feature_list.json> <junit.xml> [<junit.xml> ...]

A feature is done only when it names acceptance tests and every one of them passed in the
given JUnit reports; skipped or missing tests keep it open. Exit 0 when every feature is
done, 1 when any feature is open or none is listed, and 2 on a usage error.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SEVERITY = {"pass": 0, "skipped": 1, "fail": 2}


def junit_key(test_id: str) -> str:
    """Return the 'classname::name' key that pytest writes to JUnit XML for a test id.

    Ids that do not start with a ``.py`` path, such as eval cases, are already keys.
    """
    path, _, tail = test_id.partition("::")
    if not path.endswith(".py"):
        return test_id
    name_part, bracket, params = tail.partition("[")
    names = [path.replace("/", ".").removesuffix(".py"), *name_part.split("::")]
    names[-1] += bracket + params
    return ".".join(names[:-1]) + "::" + names[-1]


def load_results(reports: list[Path]) -> dict[str, str]:
    results: dict[str, str] = {}
    for report in reports:
        for case in ET.parse(report).getroot().iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                status = "fail"
            elif case.find("skipped") is not None:
                status = "skipped"
            else:
                status = "pass"
            key = f"{case.get('classname')}::{case.get('name')}"
            # A test reported more than once keeps its worst status.
            if key not in results or SEVERITY[status] > SEVERITY[results[key]]:
                results[key] = status
    return results


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    features = json.loads(Path(argv[1]).read_text(encoding="utf-8-sig"))["features"]
    results = load_results([Path(arg) for arg in argv[2:]])
    open_count = 0
    for feature in features:
        tests = feature.get("acceptance_tests", [])
        statuses = {test: results.get(junit_key(test), "missing") for test in tests}
        done = bool(tests) and all(status == "pass" for status in statuses.values())
        open_count += not done
        print(f"{'DONE' if done else 'OPEN'}  {feature['id']}  {feature['behavior']}")
        if not tests:
            print("      no acceptance tests")
        for test, status in statuses.items():
            if status != "pass":
                print(f"      {status:<8}{test}")
    print(f"{len(features) - open_count}/{len(features)} features done")
    return 1 if open_count or not features else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
