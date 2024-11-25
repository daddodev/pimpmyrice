from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from docopt import formal_usage, parse_defaults, parse_pattern, printable_usage
from infi.docopt_completion.common import (CommandParams, build_command_tree,
                                           get_options_descriptions)
from infi.docopt_completion.docopt_completion import _autodetect_generators
from pydantic import BaseModel, create_model

from pimpmyrice.config import JSON_SCHEMA_DIR
from pimpmyrice.doc import __doc__ as cli_doc
from pimpmyrice.files import save_json
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme
from pimpmyrice.utils import Result

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager


def create_dynamic_model(name: str, source: dict[str, Any]) -> BaseModel:
    fields: dict[str, Any] = {}
    for key, value in source.items():
        if isinstance(value, dict):
            nested_model = create_dynamic_model(f"{name}_{key}", value)
            fields[key] = (nested_model, {})
        else:
            fields[key] = (type(value), value)

    model: BaseModel = create_model(name, **fields)

    return model


def generate_theme_json_schema(tm: ThemeManager) -> Result:
    res = Result()

    base_style = deepcopy(tm.base_style)

    for module in tm.mm.modules:
        if module not in base_style["modules_styles"]:
            base_style["modules_styles"][module] = {}

    style_model = create_dynamic_model("Style", base_style)
    style_schema = style_model.model_json_schema()

    theme_schema = Theme.model_json_schema()

    tags_schema = {
        "default": [],
        "items": {
            "anyOf": [
                {"type": "string"},
                {
                    "const": "",
                    "enum": list(tm.tags),
                    "type": "string",
                },
            ]
        },
        "title": "Tags",
        "type": "array",
        "uniqueItems": True,
    }

    theme_schema["properties"]["tags"] = tags_schema

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    theme_schema["$defs"]["Mode"]["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["properties"]["style"] = {"$ref": "#/$defs/Style"}

    schema_path = JSON_SCHEMA_DIR / "theme.json"
    save_json(schema_path, theme_schema)

    return res.debug(f'theme schema saved to "{schema_path}"')


def generate_module_json_schema() -> Result:
    res = Result()

    module_schema = Module.model_json_schema()

    schema_path = JSON_SCHEMA_DIR / "module.json"
    save_json(schema_path, module_schema)

    return res.debug(f'module schema saved to "{schema_path}"')


def generate_shell_suggestions(tm: ThemeManager) -> None:
    # TODO fork docopt_completion

    doc = cli_doc.replace("THEME", f'({"|".join(tm.themes.keys())})')
    doc = doc.replace("TAGS", f'({"|".join(tm.tags)})')
    doc = re.sub(r"\bMODULES?\b", f'({"|".join(tm.mm.modules.keys())})', doc)
    # TODO add command suggestions
    doc = doc.replace("COMMAND [COMMAND_ARGS...]", "")

    options = parse_defaults(doc)
    pattern = parse_pattern(formal_usage(printable_usage(doc)), options)
    param_tree = CommandParams()
    build_command_tree(pattern, param_tree)
    option_help = dict(list(get_options_descriptions(doc)))

    generators_to_use = _autodetect_generators()
    for generator in generators_to_use:
        generator.generate(os.path.basename("pimp"), param_tree, option_help)
