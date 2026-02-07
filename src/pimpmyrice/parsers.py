import logging
import os
from pathlib import Path
from typing import Any, Union

from pimpmyrice.config_paths import CLIENT_OS
from pimpmyrice.files import load_json, load_yaml, save_json, save_yaml
from pimpmyrice.migrations import migrate_module_dict, migrate_theme_dict
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme, Wallpaper

log = logging.getLogger(__name__)


def parse_wallpaper(
    wallpaper: Union[dict[str, Any], str], theme_path: Path
) -> Wallpaper:
    """Parse a wallpaper entry into a Wallpaper model."""
    match wallpaper:
        case str(wallpaper):
            return Wallpaper(path=theme_path / wallpaper)
        case dict(wallpaper):
            return Wallpaper(**{**wallpaper, "path": theme_path / wallpaper["path"]})
        case _:
            raise Exception("wallpaper must be a string or a dict")


def parse_theme(path: Path) -> Theme:
    """
    Parse a theme directory (theme.json + assets) into a Theme model.

    Automatically migrates old syntax (pre-0.5.0) to new format if needed.

    Args:
        path: Theme directory path.

    Returns:
        Parsed Theme model.
    """
    name = path.name
    theme_file = path / "theme.json"

    data = load_json(theme_file)

    migrated = migrate_theme_dict(data)
    if migrated is not None:
        log.info(f"migrating theme '{name}' to new syntax")
        save_json(theme_file, migrated)
        data = migrated

    data["last_modified"] = os.path.getmtime(theme_file) * 1000

    data["wallpaper"] = parse_wallpaper(data["wallpaper"], path)

    modes = data.get("modes")
    if isinstance(modes, dict):
        for mode_name, mode in modes.items():
            mode["name"] = mode_name
            if isinstance(mode, dict):
                if "wallpaper" not in mode:
                    mode["wallpaper"] = data.get("wallpaper")
                else:
                    mode["wallpaper"] = parse_wallpaper(mode["wallpaper"], path)

    return Theme(**data, name=name, path=path)


def _inject_module_name_into_actions(data: dict[str, Any], module_name: str) -> None:
    """Add module_name to all actions in the module data for context."""

    def add_name(actions: Any) -> None:
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict):
                    action["module_name"] = module_name
        elif isinstance(actions, dict):
            actions["module_name"] = module_name

    if "on_events" in data and isinstance(data["on_events"], dict):
        for actions in data["on_events"].values():
            add_name(actions)

    if "scripts" in data and isinstance(data["scripts"], dict):
        for actions in data["scripts"].values():
            add_name(actions)


def parse_module(module_path: Path) -> Module:
    """
    Parse a module directory from YAML/JSON definition into a Module.

    Automatically migrates old syntax (pre-0.5.0) to new format if needed.

    Args:
        module_path: Module directory path.

    Returns:
        Parsed Module model.
    """
    module_name = module_path.name
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
        raise Exception("module.{json,yaml} not found")

    migrated = migrate_module_dict(data)
    if migrated is not None:
        log.info(f"migrating module '{module_name}' to new syntax")
        save_func(file_path, migrated)
        data = migrated

    _inject_module_name_into_actions(data, module_name)

    module = Module(**data, name=module_name)

    if CLIENT_OS not in module.os:
        module.enabled = False
        log.warning(f'module "{module.name}" disabled: not compatible with {CLIENT_OS}')

    return module


def clean_module_dump(data: dict[str, Any]) -> dict[str, Any]:
    """
    Remove empty/default values from module dump for cleaner YAML output.

    Removes:
    - enabled: true (default)
    - os with all OS values (default)
    - Empty on_events sub-fields
    - Empty scripts dict
    - Empty lists and dicts

    Args:
        data: Module dump data.

    Returns:
        Cleaned data.
    """
    from pimpmyrice.config_paths import Os

    cleaned: dict[str, Any] = {}

    for key, value in data.items():
        if key == "name":
            continue

        if key == "enabled" and value is True:
            continue

        if key == "os":
            if isinstance(value, list) and set(value) == set(Os):
                continue

        if key == "on_events" and isinstance(value, dict):
            cleaned_on_events: dict[str, Any] = {}
            for event_name, actions in value.items():
                if actions:
                    cleaned_on_events[event_name] = actions
            if cleaned_on_events:
                cleaned[key] = cleaned_on_events
            continue

        if key == "scripts" and not value:
            continue

        if value in ([], {}):
            continue

        cleaned[key] = value

    return cleaned
