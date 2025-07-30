import os
from typing import Any

import jinja2

from pimpmyrice.config_paths import CONFIG_DIR, HOME_DIR, MODULES_DIR, PIMP_CONFIG_DIR
from pimpmyrice.exceptions import ReferenceNotFound


def process_template(template: str, values: dict[str, Any]) -> str:
    # get_template_keywords(template)
    templ = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(template)
    rendered: str = templ.render(**values)
    return rendered


def process_keyword_template(value: str, theme_map: dict[str, Any]) -> Any:
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
    # TODO capitalize

    d = {"home_dir": HOME_DIR,
         "config_dir": CONFIG_DIR,
         "pimp_config_dir": PIMP_CONFIG_DIR
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
