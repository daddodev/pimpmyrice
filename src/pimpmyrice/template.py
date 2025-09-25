import os
from pathlib import Path
from typing import Any

import jinja2

from pimpmyrice.config_paths import CONFIG_DIR, HOME_DIR, MODULES_DIR, PIMP_CONFIG_DIR
from pimpmyrice.exceptions import ReferenceNotFound


def process_template(template: str, values: dict[str, Any]) -> str:
    """
    Render a Jinja2 template string with strict undefined.

    Args:
        template (str): Template string.
        values (dict[str, Any]): Variables to render into the template.

    Returns:
        str: Rendered string.
    """
    # get_template_keywords(template)
    templ = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(template)
    rendered: str = templ.render(**values)
    return rendered


def render_template_file(
    template_path: Path,
    values: dict[str, Any],
    search_paths: list[Path] | None = None,
) -> str:
    """
    Render a Jinja2 template file with optional search paths.

    Args:
        template_path (Path): Template file path.
        values (dict[str, Any]): Variables to render.
        search_paths (list[Path] | None): Additional template search paths.

    Returns:
        str: Rendered output.
    """
    fs_paths: list[Path] = [template_path.parent]
    if search_paths:
        fs_paths.extend(search_paths)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(searchpath=[str(p) for p in fs_paths]),
        undefined=jinja2.StrictUndefined,
    )
    templ = env.get_template(template_path.name)
    rendered: str = templ.render(**values)
    return rendered


def process_keyword_template(value: str, theme_map: dict[str, Any]) -> Any:
    """
    Evaluate a single Jinja2 expression and return its value.

    Args:
        value (str): Template expression inside "{{ ... }}".
        theme_map (dict[str, Any]): Variables for evaluation.

    Returns:
        Any: Evaluated value.

    Raises:
        ReferenceNotFound: If the result is still an unresolved Jinja2 variable.
    """
    output: list[Any] = []

    def capture_j2_var(v: Any) -> Any:
        if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
            raise ReferenceNotFound(f'reference for "{v}" not found')
        output.append(v)

    template_str = "{%- set parsed = " + value[2:-2] + "-%} {{capture_j2_var(parsed)}}"
    templ = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(
        template_str
    )
    templ.render(capture_j2_var=capture_j2_var, **theme_map)

    return output[0]


def parse_string_vars(
    string: str,
    theme_dict: dict[str, Any] | None = None,
    module_name: str | None = None,
) -> str:
    """
    Expand variables and user paths in a string.

    Args:
        string (str): Input string possibly containing template vars.
        theme_dict (dict[str, Any] | None): Extra variables. Defaults to None.
        module_name (str | None): Module context for dir paths. Defaults to None.

    Returns:
        str: Expanded string.
    """
    # TODO capitalize

    d = {
        "home_dir": HOME_DIR,
        "config_dir": CONFIG_DIR,
        "pimp_config_dir": PIMP_CONFIG_DIR,
    }
    if module_name:
        d["module_dir"] = MODULES_DIR / module_name
        d["templates_dir"] = MODULES_DIR / module_name / "templates"
        d["files_dir"] = MODULES_DIR / module_name / "files"
    if not theme_dict:
        theme_dict = d
    else:
        theme_dict |= d
    res = process_template(string, theme_dict)
    expanded: str = os.path.expanduser(res)
    return expanded
