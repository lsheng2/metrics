"""Phase dispatcher for Windows host qualification."""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", required=True, choices=("conformance", "performance"))
    parser.add_argument("--mode", choices=("pilot", "diagnostic", "certify"))
    args = parser.parse_args(argv)
    if args.phase == "performance":
        if args.mode is None:
            parser.error("--phase performance requires --mode pilot|diagnostic|certify")
        producer = importlib.import_module("scripts.validation.windows_host_performance")
        return producer.main(["--mode", args.mode, "--inputs", args.inputs, "--output", args.output])
    if args.mode is not None:
        parser.error("--mode is only valid with --phase performance")
    from scripts.validation import windows_host_conformance

    return windows_host_conformance.main(["--inputs", args.inputs, "--output", args.output])


if __name__ == "__main__":
    raise SystemExit(main())
