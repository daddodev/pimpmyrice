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
from pimpmyrice.colors import LinkPalette, Palette
from pimpmyrice.config import PALETTE_GENERATORS_DIR
from pimpmyrice.dark_generator import gen_palette as dark_generator
from pimpmyrice.exceptions import ReferenceNotFound
from pimpmyrice.light_generator import gen_palette as light_generator
from pimpmyrice.module_utils import get_func_from_py_file
from pimpmyrice.utils import (
    AttrDict,
    DictOrAttrDict,
    get_thumbnail,
    process_keyword_template,
)

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


Style = dict[str, Any]

PaletteGeneratorType = Callable[[Path], Awaitable[Palette]]


def get_palette_generators() -> dict[str, PaletteGeneratorType]:
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
    theme: str | None = None
    mode: str = "dark"


class Mode(BaseModel):
    name: SkipJsonSchema[str] = Field(exclude=True)
    palette: LinkPalette | Palette
    wallpaper: Wallpaper | None = None
    style: Style = {}


class WallpaperMode(str, Enum):
    FILL = "fill"
    FIT = "fit"

    def __str__(self) -> str:
        return self.value


class Wallpaper(BaseModel):
    path: Path
    mode: WallpaperMode = WallpaperMode.FILL

    @computed_field  # type: ignore
    @property
    def thumb(self) -> Path:
        t = get_thumbnail(self.path)
        return t


class Theme(BaseModel):
    path: Path = Field()
    name: str = Field()
    wallpaper: Wallpaper
    modes: dict[str, Mode] = {}
    style: Style = {}
    tags: set[str] = set()

    @validator("tags", pre=True)
    def coerce_to_set(cls, value: Any) -> Any:  # pylint: disable=no-self-argument
        if isinstance(value, list):
            return set(value)
        return value


def dump_theme_for_file(theme: Theme) -> dict[str, Any]:
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

    # print("dump for file:", json.dumps(dump, indent=4))
    return dump


async def gen_from_img(
    image: Path,
    themes: dict[str, Theme],
    generators: dict[str, PaletteGeneratorType],
    name: str | None = None,
) -> Theme:
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
    if wallpaper.parent != theme_dir and not (theme_dir / wallpaper.name).exists():
        wallpaper = files.import_image(wallpaper, theme_dir)
    return theme_dir / wallpaper.name
