from __future__ import annotations

import logging
import string
import unicodedata
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Tuple

from jinja2 import UndefinedError
from pydantic import BaseModel, Field, computed_field, validator
from pydantic.json_schema import SkipJsonSchema

from pimpmyrice import files
from pimpmyrice.colors import Color, LinkPalette, Palette
from pimpmyrice.config_paths import PALETTE_GENERATORS_DIR
from pimpmyrice.exceptions import ReferenceNotFound
from pimpmyrice.module_utils import get_func_from_py_file
from pimpmyrice.palette_generators.dark import gen_palette as dark_generator
from pimpmyrice.palette_generators.light import gen_palette as light_generator
from pimpmyrice.template import process_keyword_template
from pimpmyrice.utils import AttrDict, DictOrAttrDict, get_thumbnail

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


def parse_colors_in_style(style: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively parse color strings to Color objects in a style dictionary.

    Args:
        style (dict[str, Any]): Style dictionary with potential color strings.

    Returns:
        dict[str, Any]: Style dictionary with color strings parsed to Color objects.
    """

    def is_color_string(value: str) -> bool:
        """Check if a string looks like a color."""
        if not isinstance(value, str):
            return False

        value = value.strip()
        if value.startswith("{{") and value.endswith("}}"):
            return False
        return (
            value.startswith("#")
            or value.startswith("rgb")
            or value.startswith("hsl")
            or value.startswith("hsv")
        )

    def parse_value(value: Any) -> Any:
        """Parse a single value, converting color strings to Color objects."""
        if isinstance(value, dict):
            return {k: parse_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [parse_value(item) for item in value]
        elif is_color_string(value):
            try:
                return Color(value)
            except Exception as e:
                log.warning(f'Failed to parse color "{value}": {e}')
                return value
        else:
            return value

    parsed: dict[str, Any] = parse_value(style)

    return parsed


Style = dict[str, Any]

PaletteGeneratorType = Callable[[Path], Awaitable[Palette]]


def get_palette_generators() -> dict[str, PaletteGeneratorType]:
    """
    Discover built-in and user-provided palette generators.

    Returns:
        dict[str, PaletteGeneratorType]: Map of generator name to async function.
    """
    generators: dict[str, PaletteGeneratorType] = {
        "dark": dark_generator,
        "light": light_generator,
    }

    for gen_path in PALETTE_GENERATORS_DIR.iterdir():
        if gen_path.is_file() and gen_path.suffix == ".py":
            try:
                gen_fn = get_func_from_py_file(gen_path, "gen_palette")
            except Exception as e:
                log.error(e, f'error loading palette generator at "{gen_path}"')
                log.exception(e)
                continue

            generators[gen_path.stem] = gen_fn

    return generators


class ThemeConfig(BaseModel):
    """User configuration for theme selection and mode."""

    theme: str | None = None
    mode: str = "dark"


class Mode(BaseModel):
    """Theme mode configuration (palette, wallpaper, and style)."""

    name: SkipJsonSchema[str] = Field(exclude=True)
    palette: LinkPalette | Palette
    wallpaper: Wallpaper | None = None
    style: Style = {}


class WallpaperMode(str, Enum):
    """Wallpaper fit behavior for the display."""

    FILL = "fill"
    FIT = "fit"

    def __str__(self) -> str:
        """Return string value (for serialization/logging)."""
        return self.value


class Wallpaper(BaseModel):
    """Wallpaper resource and display mode."""

    path: Path
    mode: WallpaperMode = WallpaperMode.FILL

    @computed_field  # type: ignore
    @property
    def thumb(self) -> Path:
        """
        Thumbnail path for the wallpaper.

        Returns:
            Path: Path to generated thumbnail image.
        """
        t = get_thumbnail(self.path)
        return t


class Theme(BaseModel):
    """Theme definition: composition of modes, style and metadata."""

    path: Path = Field()
    name: str = Field()
    wallpaper: Wallpaper
    modes: dict[str, Mode] = {}
    style: Style = {}
    tags: set[str] = set()
    last_modified: float = 0

    @validator("tags", pre=True)
    def coerce_to_set(cls, value: Any) -> Any:  # pylint: disable=no-self-argument
        """Ensure tags are stored as a set when parsing from JSON/YAML."""
        if isinstance(value, list):
            return set(value)
        return value


def dump_theme_for_file(theme: Theme) -> dict[str, Any]:
    """
    Serialize a theme for file storage (prune defaults and derived fields).

    Args:
        theme (Theme): Theme to serialize.

    Returns:
        dict[str, Any]: Cleaned theme representation suitable for file output.
    """
    dump = theme.model_dump(
        mode="json",
        exclude={
            "name": True,
            "path": True,
            "wallpaper": {"thumb"},
            "modes": {"__all__": {"wallpaper": {"thumb"}}},
        },
    )

    for mode in dump["modes"].values():
        if not mode["style"]:
            mode.pop("style")

        if mode["wallpaper"] == dump["wallpaper"]:
            mode.pop("wallpaper")
        else:
            mode["wallpaper"]["path"] = str(Path(mode["wallpaper"]["path"]).name)
            if mode["wallpaper"]["mode"] == "fill":
                mode["wallpaper"].pop("mode")

    if not dump["style"]:
        dump.pop("style")

    dump["wallpaper"]["path"] = str(Path(dump["wallpaper"]["path"]).name)

    if dump["wallpaper"]["mode"] == "fill":
        dump["wallpaper"].pop("mode")

    if not dump["tags"]:
        dump.pop("tags")

    dump.pop("last_modified")

    # print("dump for file:", json.dumps(dump, indent=4))
    return dump


async def gen_from_img(
    image: Path,
    themes: dict[str, Theme],
    generators: dict[str, PaletteGeneratorType],
    name: str | None = None,
) -> Theme:
    """
    Generate a theme by running all palette generators on an image.

    Args:
        image (Path): Source image path.
        themes (dict[str, Theme]): Existing themes (for name de-duplication).
        generators (dict[str, PaletteGeneratorType]): Palette generator functions.
        name (str | None): Optional theme name override.

    Returns:
        Theme: Newly generated theme with modes and palettes.
    """
    if not image.is_file():
        raise FileNotFoundError(f'image not found at "{image}"')

    theme_modes: dict[str, Mode] = {}
    for gen_name, gen_fn in generators.items():
        try:
            palette = await gen_fn(image)
        except Exception as e:
            log.exception(e, f'error generating palette for "{gen_name}" mode')
            continue

        mode = Mode(name=gen_name, wallpaper=Wallpaper(path=image), palette=palette)
        theme_modes[gen_name] = mode

    theme_name = valid_theme_name(name or image.stem, themes)
    theme = Theme(
        name=theme_name, path=Path(), wallpaper=Wallpaper(path=image), modes=theme_modes
    )

    return theme


def resolve_refs(
    data: DictOrAttrDict, theme_dict: DictOrAttrDict | None = None
) -> Tuple[DictOrAttrDict, list[str]]:
    """
    Resolve template references recursively in a dict-like structure.

    Args:
        data (DictOrAttrDict): Data with potential "{{...}}" references.
        theme_dict (DictOrAttrDict | None): Context for resolving references.

    Returns:
        tuple[DictOrAttrDict, list[str]]: Resolved data and list of unresolved keys.
    """
    if not theme_dict:
        theme_dict = deepcopy(data)

    unresolved = []

    for key, value in data.items():
        if isinstance(value, dict):
            data[key], pending = resolve_refs(value, theme_dict)
            for p in pending:
                unresolved.append(f"{key}.{p}")
        elif isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            try:
                processed = process_keyword_template(value, theme_dict)
                data[key] = processed
            except (ReferenceNotFound, UndefinedError):
                unresolved.append(f"{key}: {value}")

    return data, unresolved


def gen_theme_dict(
    tm: ThemeManager,
    theme_name: str,
    mode_name: str,
    palette_name: str | None = None,
    styles_names: list[str] | None = None,
) -> AttrDict:
    """
    Build the final theme dictionary to feed modules.

    Args:
        tm (ThemeManager): Theme manager instance.
        theme_name (str): Theme name.
        mode_name (str): Mode to apply.
        palette_name (str | None): Palette override. Defaults to None.
        styles_names (list[str] | None): Extra global styles to merge.

    Returns:
        AttrDict: Theme data including palette, wallpaper, mode, and styles.
    """
    theme = tm.themes[theme_name]

    if mode_name not in theme.modes:
        new_mode = [*theme.modes.keys()][0]
        log.warning(f'"{mode_name}" mode not present in theme, applying "{new_mode}"')
        mode_name = new_mode

    styles: list[Style] = []

    if theme.style:
        if from_global := theme.style.get("from_global"):
            if from_global not in tm.styles:
                raise Exception(
                    f'global style "{from_global}" not found in {list(tm.styles)}'
                )
            theme_style = AttrDict(**tm.styles[from_global]) + theme.style
            styles.append(theme_style)
        else:
            styles.append(theme.style)

    if mode_style := theme.modes[mode_name].style:
        if from_global := mode_style.get("from_global"):
            if from_global not in tm.styles:
                raise Exception(
                    f'global style "{from_global}" not found in {list(tm.styles)}'
                )
            mode_style = AttrDict(**tm.styles[from_global]) + mode_style

        styles.append(mode_style)

    if styles_names:
        for style in styles_names:
            if style not in tm.styles:
                raise Exception(
                    f'global style "{style}" not found in {list(tm.styles)}'
                )
            styles.append(tm.styles[style])

    palette: Palette
    if palette_name:
        if palette_name in tm.palettes:
            palette = tm.palettes[palette_name]
        else:
            raise Exception(f'palette "{palette_name}" not found')
    else:
        mode_palette = theme.modes[mode_name].palette
        if isinstance(mode_palette, LinkPalette):
            from_global = mode_palette.from_global

            if from_global not in tm.palettes:
                raise Exception(
                    f'global style "{from_global}" not found in {list(tm.palettes)}'
                )

            palette = tm.palettes[from_global]
        else:
            palette = mode_palette

    theme = deepcopy(theme)
    styles = deepcopy(styles)
    palette = palette.copy()
    base_style = deepcopy(tm.base_style)

    theme_dict = AttrDict(palette.model_dump())

    theme_dict["theme_name"] = theme.name
    theme_dict["wallpaper"] = theme.modes[mode_name].wallpaper
    theme_dict["mode"] = mode_name

    theme_dict += base_style

    if theme.style:
        theme_dict += theme.style

    if theme.modes[mode_name].style:
        theme_dict += theme.modes[mode_name].style

    if styles:
        for s in styles:
            theme_dict += s

    theme_dict, pending = resolve_refs(theme_dict)
    while len(pending) > 0:
        c = len(pending)
        theme_dict, pending = resolve_refs(theme_dict)
        if len(pending) == c:
            break

    if pending:
        p_string = ", ".join(f'"{p}"' for p in pending)
        raise Exception(f"keyword reference for {p_string} not found")

    return theme_dict


def valid_theme_name(name: str, themes: dict[str, Theme]) -> str:
    """
    Sanitize and de-duplicate a string for use as a theme name.

    Args:
        name (str): Desired theme name.
        themes (dict[str, Theme]): Existing themes to avoid collisions.

    Returns:
        str: Safe, unique theme name.
    """
    whitelist = "-_.() %s%s" % (string.ascii_letters, string.digits)
    char_limit = 20
    cleaned_filename = (
        unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
    )
    cleaned_filename = "".join(c for c in cleaned_filename if c in whitelist)
    name = cleaned_filename[:char_limit].replace(" ", "_").lower().strip()

    tries = 1
    n = name
    while n in themes:
        n = f"{name}_{tries + 1}"
        tries += 1
    return n


def import_image(wallpaper: Path, theme_dir: Path) -> Path:
    """
    Ensure a wallpaper image resides in the theme directory.

    Args:
        wallpaper (Path): Path to the wallpaper image.
        theme_dir (Path): Theme directory where the image should live.

    Returns:
        Path: Path to the wallpaper inside `theme_dir`.
    """
    if wallpaper.parent != theme_dir and not (theme_dir / wallpaper.name).exists():
        wallpaper = files.import_image(wallpaper, theme_dir)
    return theme_dir / wallpaper.name
