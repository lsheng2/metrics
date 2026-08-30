from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def forward_to_canonical(skill_name: str, script_name: str) -> int:
    script_path = Path.home() / ".copilot" / "skills" / skill_name / "scripts" / script_name
    if not script_path.exists():
        raise SystemExit(f"Canonical script not found: {script_path}")

    result = subprocess.run([sys.executable, str(script_path), *sys.argv[1:]], cwd=script_path.parents[1])
    return result.returncode
