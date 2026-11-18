"""Phase dispatcher for Windows host qualification."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", required=True, choices=("conformance", "performance"))
    args = parser.parse_args(argv)
    if args.phase == "performance":
        print(
            "windows_host_qualification: performance phase is deferred to PERF.PROBE/PERF.CERTIFY; "
            "no benchmark helpers were imported or executed.",
            file=sys.stderr,
        )
        return 1
    from scripts.validation import windows_host_conformance

    return windows_host_conformance.main(["--inputs", args.inputs, "--output", args.output])


if __name__ == "__main__":
    raise SystemExit(main())
