from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


DISABLED_DEMO_GRAFANA_PLUGINS = (
    "elasticsearch",
    "grafana-postgresql-datasource",
    "grafana-pyroscope-datasource",
    "influxdb",
    "jaeger",
    "loki",
    "mssql",
    "mysql",
    "opentsdb",
    "stackdriver",
    "tempo",
    "zipkin",
)


def write_runtime_grafana_config(workspace: Path, grafana_port: int) -> Path:
    source = workspace / "state" / "grafana" / "grafana.ini"
    runtime_directory = workspace / "state" / "grafana" / "runtime"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    ensure_grafana_provisioning_directories(workspace)
    target = runtime_directory / f"grafana-e2e-{grafana_port}.ini"
    content = source.read_text(encoding="utf-8")
    lines = []
    for line in content.splitlines():
        if line.strip().startswith("http_port"):
            lines.append(f"http_port = {grafana_port}")
        elif line.strip().startswith("root_url"):
            lines.append(f"root_url = http://127.0.0.1:{grafana_port}/")
        else:
            lines.append(line)
    lines = set_ini_values(
        lines,
        "analytics",
        {
            "check_for_updates": "false",
            "check_for_plugin_updates": "false",
        },
    )
    lines = set_ini_values(
        lines,
        "auth.anonymous",
        {
            "org_role": "Viewer",
        },
    )
    lines = set_ini_values(
        lines,
        "unified_alerting",
        {
            "enabled": "false",
            "execute_alerts": "false",
        },
    )
    lines = set_ini_values(
        lines,
        "unified_alerting.state_history",
        {
            "enabled": "false",
        },
    )
    lines = set_ini_values(
        lines,
        "plugins",
        {
            "disable_plugins": ",".join(DISABLED_DEMO_GRAFANA_PLUGINS),
            "preinstall_disabled": "true",
            "preinstall_auto_update": "false",
        },
    )
    tighten_sqlite_file_mode(workspace)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def ensure_grafana_provisioning_directories(workspace: Path) -> None:
    root = workspace / "state" / "grafana" / "conf" / "provisioning"
    for name in ("alerting", "dashboards", "datasources", "plugins"):
        (root / name).mkdir(parents=True, exist_ok=True)


def tighten_sqlite_file_mode(workspace: Path) -> None:
    database_path = workspace / "state" / "grafana" / "data" / "grafana.db"
    if not database_path.exists():
        return
    try:
        os.chmod(database_path, 0o640)
    except OSError:
        return


def set_ini_values(lines: list[str], section: str, values: Mapping[str, str]) -> list[str]:
    output = list(lines)
    section_header = f"[{section}]"
    section_index = next((index for index, line in enumerate(output) if line.strip().lower() == section_header.lower()), -1)
    if section_index < 0:
        output.extend(["", section_header])
        for key, value in values.items():
            output.append(f"{key} = {value}")
        return output

    next_section_index = next((index for index in range(section_index + 1, len(output)) if output[index].strip().startswith("[") and output[index].strip().endswith("]")), len(output))
    for key, value in values.items():
        key_prefix = f"{key}="
        spaced_key_prefix = f"{key} "
        replacement = f"{key} = {value}"
        replaced = False
        for index in range(section_index + 1, next_section_index):
            normalized = output[index].strip().lower().replace(" ", "")
            if normalized.startswith(key_prefix.lower()) or output[index].strip().lower().startswith(spaced_key_prefix.lower()):
                output[index] = replacement
                replaced = True
                break
        if not replaced:
            output.insert(next_section_index, replacement)
            next_section_index += 1
    return output
