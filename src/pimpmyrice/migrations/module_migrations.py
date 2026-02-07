"""
Module migration utilities for transforming old module.yaml syntax to new format.

Migration from pre-0.5.0 to 0.5.0+:
- init → on_events.module_install
- pre_run → on_events.before_theme_apply
- run → on_events.theme_apply
- commands → scripts (actions wrapped in lists)
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def _has_old_syntax(data: dict[str, Any]) -> bool:
    """Check if module data uses pre-0.5.0 syntax."""
    if "on_events" in data:
        return False
    old_keys = {"run", "pre_run", "init", "commands"}
    return bool(old_keys & data.keys())


def _is_init_action(action: dict[str, Any]) -> bool:
    """Check if action should be in module_install."""
    return action.get("action", "") in ("link", "append")


def _migrate_python_action(action: dict[str, Any], module_name: str) -> dict[str, Any]:
    """Migrate old PythonAction syntax to new syntax."""
    if "function" in action and "py_file_path" not in action:
        func = action.pop("function")
        if "." in func:
            parts = func.rsplit(".", 1)
            action["py_file_path"] = parts[0].replace(".", "/") + ".py"
            action["function_name"] = parts[1]
        else:
            action["py_file_path"] = f"{module_name}.py"
            action["function_name"] = func
        action["action"] = "python"
    return action


def migrate_module_dict(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Migrate module data from old syntax to on_events/scripts format.

    Returns migrated data if old syntax detected, None if already current.

    Args:
        data: Module data with possible old syntax.

    Returns:
        Migrated dict or None if no migration needed.
    """
    if not _has_old_syntax(data):
        return None

    migrated: dict[str, Any] = {}
    module_name = data.get("name", "")

    def convert_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for action in actions:
            if action.get("action") == "python":
                action = _migrate_python_action(action, module_name)
            converted.append(action)
        return converted

    for key, value in data.items():
        if key == "name":
            continue
        if key in ("enabled", "os"):
            migrated[key] = value
            continue

        if key == "init":
            on_events = migrated.setdefault("on_events", {})
            on_events["module_install"] = convert_actions(value)

        elif key == "pre_run":
            on_events = migrated.setdefault("on_events", {})
            on_events["before_theme_apply"] = convert_actions(value)

        elif key == "run":
            on_events = migrated.setdefault("on_events", {})
            on_events["theme_apply"] = convert_actions(value)

        elif key == "commands":
            migrated["scripts"] = {}
            for script_name, script_value in value.items():
                script_value["action"] = "python"
                migrated["scripts"][script_name] = [convert_actions([script_value])[0]]

        else:
            migrated[key] = value

    return migrated
