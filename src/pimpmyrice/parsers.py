import logging
from pathlib import Path
from typing import Any, Union

from pimpmyrice import files
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme, Wallpaper

log = logging.getLogger(__name__)


def parse_wallpaper(
    wallpaper: Union[dict[str, Any], str], theme_path: Path
) -> Wallpaper:
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
    name = path.name

    data = files.load_json(path / "theme.json")

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
    module_name = module_path.name
    module_yaml = module_path / "module.yaml"
    module_json = module_path / "module.json"

    if module_yaml.exists():
        data = files.load_yaml(module_yaml)
    elif module_json.exists():
        data = files.load_json(module_json)
    else:
        raise Exception("module.{json,yaml} not found")

    for param in ["init", "pre_run", "run"]:
        for action in data.get(param, []):
            if isinstance(action, dict):
                action["module_name"] = module_name

    for cmd_name, cmd in data.get("commands", {}).items():
        cmd["module_name"] = module_name

    module = Module(**data, name=module_name)

    return module
