from __future__ import annotations

import logging
import subprocess
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, create_model

from pimpmyrice.config_paths import CLIENT_OS, JSON_SCHEMA_DIR, Os
from pimpmyrice.files import save_json
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


def create_dynamic_model(name: str, source: dict[str, Any]) -> BaseModel:
    """
    Create a Pydantic model from a nested dict of example values.

    Args:
        name (str): Base model name.
        source (dict[str, Any]): Example data used to define fields.

    Returns:
        BaseModel: Generated model class instance.
    """
    fields: dict[str, Any] = {}
    for key, value in source.items():
        if isinstance(value, dict):
            nested_model = create_dynamic_model(f"{name}_{key}", value)
            fields[key] = (nested_model, {})
        else:
            fields[key] = (type(value), value)

    model: BaseModel = create_model(name, **fields)

    return model


def get_fonts() -> tuple[list[str], list[str]]:
    """
    Enumerate installed font families and monospaced families.

    Returns:
        tuple[list[str], list[str]]: (all families, monospace families).
    """
    all_families: set[str] = set()
    mono_families: set[str] = set()

    try:
        if CLIENT_OS == Os.WINDOWS:
            ps_script = (
                "$ErrorActionPreference='SilentlyContinue';"
                "$f=(New-Object System.Drawing.Text.InstalledFontCollection).Families;"
                "$f | ForEach-Object { $_.Name } | Sort-Object -Unique"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                raise Exception("PowerShell font enumeration failed")

            for name in proc.stdout.splitlines():
                name = name.strip()
                if not name:
                    continue
                all_families.add(name)
                lowered = name.lower()
                if any(
                    tok in lowered for tok in ["mono", "code", "console", "courier"]
                ):
                    mono_families.add(name)
        else:
            proc = subprocess.run(
                ["fc-list", "-f", "%{family}\t%{spacing}\n"],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                raise Exception("fc-list not available or failed")

            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                # family part can be comma-separated aliases
                try:
                    family_part, spacing_part = line.split("\t", 1)
                except ValueError:
                    family_part, spacing_part = line, "0"
                families = [f.strip() for f in family_part.split(",") if f.strip()]
                try:
                    spacing_val = int(str(spacing_part).strip())
                except ValueError:
                    spacing_val = 0
                for fam in families:
                    all_families.add(fam)
                    if spacing_val >= 100:
                        mono_families.add(fam)
    except Exception as e:
        log.debug(f"Font enumeration failed with error: {e!r}")

    log.debug(f"found {len(all_families)} fonts")
    return list(all_families), list(mono_families)


def generate_theme_json_schema(tm: ThemeManager) -> None:
    """
    Generate and save the JSON Schema for Theme files.

    Args:
        tm (ThemeManager): Theme manager to gather tags and module styles.

    Returns:
        None
    """
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

    sans_fonts, mono_fonts = get_fonts()
    normal_font_schema = {
        "anyOf": [
            {"type": "string"},
            {
                "const": "",
                "enum": sans_fonts,
                "type": "string",
            },
        ],
        "title": "Normal font",
        "default": "",
    }

    mono_font_schema = {
        "anyOf": [
            {"type": "string"},
            {
                "const": "",
                "enum": mono_fonts,
                "type": "string",
            },
        ],
        "title": "Mono font",
        "default": "",
    }

    theme_schema["properties"]["tags"] = tags_schema

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    theme_schema["$defs"]["Mode"]["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["$defs"]["Style_font_normal"]["properties"]["family"] = (
        normal_font_schema
    )
    theme_schema["$defs"]["Style_font_mono"]["properties"]["family"] = mono_font_schema

    theme_schema["properties"].pop("name")
    theme_schema["properties"].pop("path")
    theme_schema["required"].remove("name")
    theme_schema["required"].remove("path")

    schema_path = JSON_SCHEMA_DIR / "theme.json"
    save_json(schema_path, theme_schema)

    log.debug(f'theme schema saved to "{schema_path}"')


def generate_module_json_schema() -> None:
    """
    Generate and save the JSON Schema for Module files.

    Returns:
        None
    """
    module_schema = Module.model_json_schema()

    schema_path = JSON_SCHEMA_DIR / "module.json"
    save_json(schema_path, module_schema)

    log.debug(f'module schema saved to "{schema_path}"')
