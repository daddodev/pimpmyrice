"""
Module migration utilities for transforming old module.yaml syntax to new format.

Migration from pre-0.5.0 to 0.5.0+:
- init → on_events.module_install
- pre_run → on_events.before_theme_apply
- run → on_events.theme_apply
- commands → scripts (actions wrapped in lists)
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from pimpmyrice.config_paths import MODULES_DIR
from pimpmyrice.files import load_json, load_yaml, save_json, save_yaml

log = logging.getLogger(__name__)


def is_old_syntax(data: dict[str, Any]) -> bool:
    """
    Check if module data uses pre-0.5.0 syntax.

    Old syntax indicators:
    - Has 'run', 'pre_run', 'init', or 'commands' keys
    - Does NOT have 'on_events' key

    Args:
        data (dict[str, Any]): Module data dictionary.

    Returns:
        bool: True if old syntax detected.
    """
    if "on_events" in data:
        return False

    old_keys = {"run", "pre_run", "init", "commands"}
    return bool(old_keys & data.keys())


def _is_init_action(action: dict[str, Any]) -> bool:
    """Check if action should be in module_install (init actions)."""
    action_type = action.get("action", "")
    return action_type in ("link", "append")


def _is_lifecycle_action(action: dict[str, Any]) -> bool:
    """Check if action is a lifecycle action (run in theme_apply)."""
    action_type = action.get("action", "")
    return action_type in ("shell", "file", "python", "if_running", "wait_for")


def _migrate_python_action(action: dict[str, Any], module_name: str) -> dict[str, Any]:
    """
    Migrate old PythonAction syntax to new syntax.

    Old syntax: {function: "module_name.function_name"}
    New syntax: {action: "python", py_file_path: "path/to/file.py", function_name: "function_name"}

    Args:
        action (dict[str, Any]): Python action dict.
        module_name (str): Module name for default py_file_path.

    Returns:
        dict[str, Any]: Migrated action.
    """
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


def migrate_module_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Transform old module syntax to new on_events/scripts format.

    Mappings:
    - init → on_events.module_install
    - pre_run → on_events.before_theme_apply
    - run → on_events.theme_apply
    - commands → scripts (single actions wrapped in lists)

    Args:
        data (dict[str, Any]): Module data with old syntax.

    Returns:
        dict[str, Any]: Migrated module data with new syntax.
    """
    migrated: dict[str, Any] = {}
    module_name = data.get("name", "")

    def migrate_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Migrate a list of actions, handling PythonAction syntax changes."""
        migrated_actions = []
        for action in actions:
            if action.get("action") == "python":
                action = _migrate_python_action(action, module_name)
            migrated_actions.append(action)
        return migrated_actions

    for key, value in data.items():
        if key == "name":
            continue
        if key in ("enabled", "os"):
            migrated[key] = value
            continue

        if key == "init":
            on_events = migrated.setdefault("on_events", {})
            on_events["module_install"] = migrate_actions(value)
            log.debug(
                f"migrated 'init' → 'on_events.module_install' ({len(value)} actions)"
            )

        elif key == "pre_run":
            on_events = migrated.setdefault("on_events", {})
            on_events["before_theme_apply"] = migrate_actions(value)
            log.debug(
                f"migrated 'pre_run' → 'on_events.before_theme_apply' ({len(value)} actions)"
            )

        elif key == "run":
            on_events = migrated.setdefault("on_events", {})
            on_events["theme_apply"] = migrate_actions(value)
            log.debug(
                f"migrated 'run' → 'on_events.theme_apply' ({len(value)} actions)"
            )

        elif key == "commands":
            migrated["scripts"] = {}
            for k, v in value.items():
                v["action"] = "python"  # Old commands were always Python actions
                migrated["scripts"][k] = [migrate_actions([v])[0]]
            log.debug(f"migrated 'commands' → 'scripts' ({len(value)} scripts)")

        else:
            migrated[key] = value

    return migrated


def migrate_module_file(module_path: Path, backup: bool = True) -> bool:
    """
    Migrate a module file from old to new syntax if needed.

    Args:
        module_path (Path): Path to module directory.
        backup (bool): Create .bak backup before migrating. Default: True.

    Returns:
        bool: True if migration was performed, False if already current.
    """
    module_yaml = module_path / "module.yaml"
    module_json = module_path / "module.json"

    if module_yaml.exists():
        data = load_yaml(module_yaml)
        file_path = module_yaml
        save_func = save_yaml
    elif module_json.exists():
        data = load_json(module_json)
        file_path = module_json
        save_func = save_json
    else:
        raise Exception(f"module.yaml or module.json not found in {module_path}")

    if not is_old_syntax(data):
        log.debug(f"module '{module_path.name}' already using current syntax")
        return False

    log.info(f"migrating module '{module_path.name}' to new syntax")

    if backup:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        log.debug(f"backup created: {backup_path}")

    migrated_data = migrate_module_dict(data)
    save_func(file_path, migrated_data)
    log.info(f"module '{module_path.name}' migrated successfully")

    return True


def migrate_and_parse(module_path: Path) -> tuple[dict[str, Any], bool]:
    """
    Load a module file, auto-migrating if needed, and return the migrated data.

    Args:
        module_path (Path): Path to module directory.

    Returns:
        tuple[dict[str, Any], bool]: (migrated_data, was_migrated)
    """
    module_yaml = module_path / "module.yaml"
    module_json = module_path / "module.json"

    if module_yaml.exists():
        data = load_yaml(module_yaml)
    elif module_json.exists():
        data = load_json(module_json)
    else:
        raise Exception(f"module.yaml or module.json not found in {module_path}")

    if is_old_syntax(data):
        was_migrated = migrate_module_file(module_path, backup=True)
        data = migrate_module_dict(data)
    else:
        was_migrated = False

    return data, was_migrated


def migrate_all_modules(
    modules_dir: Path | None = None, backup: bool = True
) -> dict[str, int]:
    """
    Migrate all modules in a directory to new syntax.

    Args:
        modules_dir (Path | None): Directory containing modules. Defaults to MODULES_DIR.
        backup (bool): Create backups before migrating. Default: True.

    Returns:
        dict[str, int]: Migration statistics {'migrated': N, 'skipped': N, 'errors': N}.
    """
    if modules_dir is None:
        modules_dir = MODULES_DIR

    stats = {"migrated": 0, "skipped": 0, "errors": 0}

    if not modules_dir.exists():
        log.warning(f"modules directory not found: {modules_dir}")
        return stats

    for module_path in sorted(modules_dir.iterdir()):
        if not module_path.is_dir():
            continue

        try:
            migrated = migrate_module_file(module_path, backup=backup)
            if migrated:
                stats["migrated"] += 1
            else:
                stats["skipped"] += 1
        except Exception as e:
            log.error(f"error migrating module '{module_path.name}': {e}")
            stats["errors"] += 1

    log.info(
        f"migration complete: {stats['migrated']} migrated, "
        f"{stats['skipped']} skipped, {stats['errors']} errors"
    )

    return stats
