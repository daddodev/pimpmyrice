import logging
import os
from pathlib import Path
from typing import Any, Union

from pimpmyrice.config_paths import CLIENT_OS
from pimpmyrice.files import load_json, load_yaml
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


def parse_module(module_path: Path) -> Module:
    """
    Parse a module directory from YAML/JSON definition into a `Module`.

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

    for param in ["init", "pre_run", "run"]:
        for action in data.get(param, []):
            if isinstance(action, dict):
                action["module_name"] = module_name

    for cmd_name, cmd in data.get("commands", {}).items():
        cmd["module_name"] = module_name

    module = Module(**data, name=module_name)

    if CLIENT_OS not in module.os:
        module.enabled = False
        log.warn(f'module "{module.name}" disabled: not compatible with {CLIENT_OS}')

    return module
