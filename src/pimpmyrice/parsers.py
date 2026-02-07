import logging
import os
from pathlib import Path
from typing import Any, Union

from pimpmyrice.config_paths import CLIENT_OS
from pimpmyrice.files import load_json, load_yaml, save_json, save_yaml
from pimpmyrice.migrations import is_old_syntax, migrate_module_dict
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme, Wallpaper

log = logging.getLogger(__name__)


def parse_wallpaper(
    wallpaper: Union[dict[str, Any], str], theme_path: Path
) -> Wallpaper:
    """
    Parse a wallpaper entry into a `Wallpaper` model.

    Args:
        wallpaper (dict[str, Any] | str): Wallpaper config or relative path.
        theme_path (Path): Theme directory used to resolve relative paths.

    Returns:
        Wallpaper: Parsed wallpaper model.
    """
    match wallpaper:
        case str(wallpaper):
            return Wallpaper(path=theme_path / wallpaper)
        case dict(wallpaper):
            return Wallpaper(**{**wallpaper, "path": theme_path / wallpaper["path"]})
        case _:
            raise Exception('"wallpaper" must be a string or a dict')


def parse_theme(
    path: Path,
) -> Theme:
    """
    Parse a theme directory (theme.json + assets) into a `Theme` model.

    Args:
        path (Path): Theme directory path.

    Returns:
        Theme: Parsed theme model.
    """
    name = path.name
    theme_file = path / "theme.json"

    data = load_json(theme_file)

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

    theme = Theme(**data, name=name, path=path)
    return theme


def _inject_module_name_into_actions(data: dict[str, Any], module_name: str) -> None:
    """Add module_name to all actions in the module data for context."""

    def add_name(actions: Any) -> None:
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict):
                    action["module_name"] = module_name
        elif isinstance(actions, dict):
            actions["module_name"] = module_name

    # Process on_events
    if "on_events" in data and isinstance(data["on_events"], dict):
        for actions in data["on_events"].values():
            add_name(actions)

    # Process scripts
    if "scripts" in data and isinstance(data["scripts"], dict):
        for actions in data["scripts"].values():
            add_name(actions)


def parse_module(module_path: Path) -> Module:
    """
    Parse a module directory from YAML/JSON definition into a `Module`.

    Automatically migrates old syntax (pre-0.5.0) to new format if needed.

    Args:
        module_path (Path): Module directory path.

    Returns:
        Module: Parsed module model.
    """
    module_name = module_path.name
    module_yaml = module_path / "module.yaml"
    module_json = module_path / "module.json"

    if module_yaml.exists():
        data = load_yaml(module_yaml)
    elif module_json.exists():
        data = load_json(module_json)
    else:
        raise Exception("module.{json,yaml} not found")

    if is_old_syntax(data):
        log.info(f"migrating module '{module_name}' to new syntax")
        data = migrate_module_dict(data)
        if module_yaml.exists():
            save_yaml(module_yaml, data)
        elif module_json.exists():
            save_json(module_json, data)

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
        data (dict[str, Any]): Module dump data.

    Returns:
        dict[str, Any]: Cleaned data.
    """
    from pimpmyrice.config_paths import Os

    cleaned: dict[str, Any] = {}

    for key, value in data.items():
        # Skip excluded fields
        if key == "name":
            continue

        # Skip enabled if true (default)
        if key == "enabled" and value is True:
            continue

        # Skip os if it contains all OS values (default)
        if key == "os":
            if isinstance(value, list) and set(value) == set(Os):
                continue

        # Skip empty on_events sub-fields
        if key == "on_events" and isinstance(value, dict):
            cleaned_on_events: dict[str, Any] = {}
            for event_name, actions in value.items():
                if actions:  # Only keep non-empty lists
                    cleaned_on_events[event_name] = actions
            if cleaned_on_events:
                cleaned[key] = cleaned_on_events
            continue

        # Skip empty scripts
        if key == "scripts" and not value:
            continue

        # Skip empty lists and dicts
        if value in ([], {}):
            continue

        cleaned[key] = value

    return cleaned
