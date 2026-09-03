import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from port_lifecycle.platform_ops import creation_flags


def test_windows_creationFlagsStartServicesWithoutConsoleWindow():
    flags = creation_flags()
    if sys.platform == "win32":
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
        assert flags & subprocess.CREATE_NO_WINDOW
        assert not flags & subprocess.DETACHED_PROCESS
    else:
        assert flags == 0
