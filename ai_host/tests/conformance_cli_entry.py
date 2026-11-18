from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.exit_inventory import install_exit_capture
install_exit_capture()
runner = runpy.run_path(str(ROOT / 'scripts/validation/run_report_authoring_tests.py'))
temporary_root, port = Path(sys.argv[1]), sys.argv[2]
runner['run_tests'].__globals__['ROOT'] = temporary_root


def invoke_serve(arguments):
    sys.argv = ['manage.py', 'serve', '--host', '127.0.0.1', '--port', port]
    runpy.run_path(str(ROOT / 'manage.py'), run_name='__main__')
    return 0


runner['pytest'].main = invoke_serve
raise SystemExit(runner['run_tests']([]))
