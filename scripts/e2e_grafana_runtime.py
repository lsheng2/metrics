from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

INFINITY_DATASOURCE_PLUGIN_ID = "yesoreyeram-infinity-datasource"
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
    ensure_grafana_state_directories(workspace)
    runtime_directory = workspace / "state" / "grafana" / "runtime"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    target = runtime_directory / f"grafana-e2e-{grafana_port}.ini"
    content = source.read_text(encoding="utf-8") if source.exists() else default_grafana_config_content(workspace, grafana_port)
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


def ensure_grafana_state_directories(workspace: Path) -> None:
    grafana_state = workspace / "state" / "grafana"
    for directory in (
        grafana_state / "data",
        grafana_state / "data" / "plugins",
        grafana_state / "logs",
        grafana_state / "conf" / "provisioning",
        grafana_state / "conf" / "provisioning" / "alerting",
        grafana_state / "conf" / "provisioning" / "dashboards",
        grafana_state / "conf" / "provisioning" / "datasources",
        grafana_state / "conf" / "provisioning" / "plugins",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def default_grafana_config_content(workspace: Path, grafana_port: int) -> str:
    grafana_state = workspace / "state" / "grafana"
    plugins_path = resolve_grafana_plugins_path(workspace)
    return "\n".join([
        "[server]",
        "http_addr = 127.0.0.1",
        f"http_port = {grafana_port}",
        "domain = localhost",
        f"root_url = http://127.0.0.1:{grafana_port}/",
        "",
        "[paths]",
        f"data = {(grafana_state / 'data').as_posix()}",
        f"logs = {(grafana_state / 'logs').as_posix()}",
        f"plugins = {plugins_path.as_posix()}",
        f"provisioning = {(grafana_state / 'conf' / 'provisioning').as_posix()}",
        "",
        "[security]",
        "admin_user = admin",
        "admin_password = admin",
        "allow_embedding = true",
        "",
        "[auth.anonymous]",
        "enabled = true",
        "org_role = Admin",
        "",
        "[plugins]",
        "allow_loading_unsigned_plugins = yesoreyeram-infinity-datasource",
        "preinstall_disabled = true",
        "check_for_plugin_updates = false",
    ])


def resolve_grafana_plugins_path(workspace: Path) -> Path:
    configured = os.environ.get("GRAFANA_PLUGINS_PATH") or os.environ.get("GF_PATHS_PLUGINS")
    if configured:
        return Path(configured).resolve()
    local_plugins = workspace / "state" / "grafana" / "data" / "plugins"
    if (local_plugins / INFINITY_DATASOURCE_PLUGIN_ID).exists():
        return local_plugins
    shared_plugins = shared_worktree_grafana_plugins_path(workspace)
    if shared_plugins and (shared_plugins / INFINITY_DATASOURCE_PLUGIN_ID).exists():
        return shared_plugins
    return local_plugins


def shared_worktree_grafana_plugins_path(workspace: Path) -> Path | None:
    if workspace.parent.name != ".worktrees":
        return None
    return workspace.parent.parent / "state" / "grafana" / "data" / "plugins"


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
