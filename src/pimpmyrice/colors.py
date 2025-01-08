from __future__ import annotations

import colorsys
import re
from collections import Counter
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Tuple

from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue, SkipJsonSchema
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from pimpmyrice import files
from pimpmyrice.config import PALETTES_DIR
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import run_shell_command
from pimpmyrice.utils import Result, Timer

if TYPE_CHECKING:
    from numpy import uint8
    from numpy.typing import NDArray

log = get_logger(__name__)


class Color:
    _rgba: tuple[int, int, int, int]
    _original: str | tuple[int, int, int] | tuple[int, int, int, int] | "Color"

    def __init__(
        self, value: str | tuple[int, int, int] | tuple[int, int, int, int] | "Color"
    ) -> None:
        self._rgba: tuple[int, int, int, int] = (0, 0, 0, 255)
        self._original = value

        if isinstance(value, (tuple, list)):
            self._rgba = self._parse_tuple(value)
        elif isinstance(value, str):
            self._rgba = self._parse_str(value)
        elif isinstance(value, Color):
            self._rgba = value._rgba
            self._original = value._original
        else:
            raise ValueError(
                "value is not a valid color: value must be a tuple, list, or string"
            )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        field_schema: dict[str, Any] = {}
        field_schema.update(type="string", format="color")
        return field_schema

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: Callable[[Any], CoreSchema]
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_plain_validator_function(
            cls._validate, serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def _validate(cls, __input_value: Any, _: Any) -> Color:
        return cls(__input_value)

    @staticmethod
    def _parse_tuple(
        value: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        if len(value) == 3:
            return tuple(value) + (255,)  # type: ignore
        elif len(value) == 4:
            return tuple(value)  # type: ignore
        else:
            raise ValueError("Invalid tuple length for RGBA value")

    @staticmethod
    def _parse_str(value: str) -> tuple[int, int, int, int]:
        if value.startswith("#"):
            return Color._parse_hex(value)
        elif value.startswith("hsl("):
            return Color._parse_hsl(value)
        raise ValueError(f'Invalid color string format: "{value}"')

    @staticmethod
    def _parse_hex(value: str) -> tuple[int, int, int, int]:
        value = value[1:]
        if len(value) == 6:
            return tuple(int(value[i : i + 2], 16) for i in range(0, 6, 2)) + (255,)  # type: ignore
        elif len(value) == 8:
            return tuple(int(value[i : i + 2], 16) for i in range(0, 8, 2))  # type: ignore
        else:
            raise ValueError("Invalid hex string format")

    @staticmethod
    def _parse_hsl(value: str) -> tuple[int, int, int, int]:
        hsl_match = re.match(r"hsl\((\d+),\s*(\d+)%\s*,\s*(\d+)%\s*\)", value)
        if not hsl_match:
            raise ValueError("Invalid HSL string format")

        hue = int(hsl_match.group(1))
        saturation = int(hsl_match.group(2))
        lightness = int(hsl_match.group(3))

        r, g, b = colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
        rgb = tuple(int(x * 255) for x in (r, g, b))

        return rgb + (255,)  # type: ignore

    @property
    def alpha(self) -> int:
        return self.rgba[3]

    def rgb(self, include_alpha: bool = False) -> tuple[int, ...]:
        return self.rgba if include_alpha else self.rgba[:3]

    def rgb_string(self, include_alpha: bool = False) -> str:
        result = self.rgba if include_alpha else self.rgba[:3]
        return f"rgb({','.join(map(str, result))})"

    def hsl(self, include_alpha: bool = False) -> tuple[int, ...]:
        rgb = self.rgba
        h, l, s = colorsys.rgb_to_hls(*[x / 255 for x in rgb[:3]])
        hsl = (int(h * 360), int(s * 100), int(l * 100))
        return hsl + (rgb[3],) if include_alpha else hsl

    def hsl_string(self, include_alpha: bool = False) -> str:
        result = self.hsl(include_alpha)
        return f"hsl({','.join(map(str, result))})"

    def hex(self, include_alpha: bool = False) -> str:
        hex_value = "".join(f"{hex(x)[2:]:0>2}" for x in self.rgba[:3])
        if include_alpha:
            hex_value += f"{hex(self.rgba[3])[2:]:0>2}"
        return f"#{hex_value}"

    def hsv(self, include_alpha: bool = False) -> tuple[int, ...]:
        rgb = self.rgba
        h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in rgb[:3]])
        hsv = (int(h * 360), s, v)
        return hsv + (rgb[3],) if include_alpha else hsv  # type: ignore

    def hsv_string(self, include_alpha: bool = False) -> str:
        result = self.hsv(include_alpha)
        return f"hsv({','.join(map(str, result))})"

    @property
    def rgba(self) -> tuple[int, int, int, int]:
        return self._rgba

    @property
    def nohash(self) -> str:
        return self.hex()[1:]

    @property
    def alt(self) -> "Color":
        h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in self._rgba[:3]])
        if v > 0.5:
            v -= 0.1
        else:
            v += 0.1
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        rgb = tuple(int(x * 255) for x in (r, g, b))
        clr = Color(rgb)  # type: ignore
        return clr

    @property
    def maxsat(self) -> "Color":
        hsl = f"hsl({self.hsl()[0]}, 100%, 50%)"
        clr = Color(hsl)
        return clr

    def __str__(self) -> str:
        return self.hex()

    def __repr__(self) -> str:
        return f"Color({self.hex()})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Color) and self.rgba == other.rgba


class TermColors(BaseModel):
    color0: Color
    color1: Color
    color2: Color
    color3: Color
    color4: Color
    color5: Color
    color6: Color
    color7: Color
    color8: Color
    color9: Color
    color10: Color
    color11: Color
    color12: Color
    color13: Color
    color14: Color
    color15: Color


class BgFgColors(BaseModel):
    bg: Color
    fg: Color


class Palette(BaseModel):
    term: TermColors
    normal: BgFgColors
    panel: BgFgColors
    dialog: BgFgColors
    input: BgFgColors
    muted: BgFgColors
    primary: BgFgColors
    secondary: BgFgColors
    accent: BgFgColors
    destructive: BgFgColors
    border: dict[Literal["active"] | Literal["inactive"], Color]


class LinkPalette(BaseModel):
    from_global: str


class GlobalPalette(Palette):
    name: str
    path: SkipJsonSchema[Path | None] = Field(default=None, exclude=True)


def get_palettes() -> dict[str, GlobalPalette]:
    palettes = {}
    for file in PALETTES_DIR.iterdir():
        try:
            palette = files.load_json(file)
            palettes[file.stem] = GlobalPalette(name=file.stem, path=file, **palette)
        except Exception as e:
            log.exception(e)
            log.error(f'Failed to load palette "{file.stem}"')
    return palettes


def palette_display_string(colors: Any) -> str:
    circles = []
    for i in range(16):
        circles.append(f"[{Color(colors[f'color{i}']).hex}]🔘[/]")

    palette_string = " ".join(circles[0:8]) + "\r\n" + " ".join(circles[8:])

    return palette_string


def kmeans(
    pixels: NDArray[uint8],
    num_clusters: int = 6,
    max_iter: int = 100,
    tol: float = 1e-4,
) -> list[tuple[tuple[int, int, int], int]]:
    import numpy as np
    from PIL import Image

    np.random.seed(42)
    indices = np.random.choice(len(pixels), num_clusters, replace=False)
    cluster_centers = pixels[indices]

    for iteration in range(max_iter):
        distances = np.linalg.norm(pixels[:, np.newaxis] - cluster_centers, axis=2)
        labels = np.argmin(distances, axis=1)

        new_cluster_centers: Any = []
        cluster_sizes = []

        for k in range(num_clusters):
            cluster_pixels = pixels[labels == k]
            if len(cluster_pixels) == 0:
                new_center = pixels[np.random.choice(len(pixels))]
            else:
                new_center = cluster_pixels.mean(axis=0)
            new_cluster_centers.append(new_center)
            cluster_sizes.append(len(cluster_pixels))

        new_cluster_centers = np.array(new_cluster_centers)

        if np.linalg.norm(new_cluster_centers - cluster_centers) < tol:
            break
        cluster_centers = new_cluster_centers

    sorted_clusters = sorted(
        zip(cluster_centers, cluster_sizes), key=lambda x: x[1], reverse=True
    )

    sorted_cluster_centers = [
        (tuple(center.astype(int)), size) for center, size in sorted_clusters
    ]

    return sorted_cluster_centers


@cache
def extract_colors(
    image_path: Path, num_colors: int = 6, resize_factor: float = 0.2
) -> list[tuple[Color, int]]:
    import numpy as np
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    img = img.resize((int(width * resize_factor), int(height * resize_factor)))

    img_array: NDArray[np.uint8] = np.array(img)
    pixels: NDArray[np.uint8] = img_array.reshape(-1, 3)

    sorted_colors_with_freq = kmeans(pixels, num_clusters=num_colors)

    result = [(Color(color), count // 100) for color, count in sorted_colors_with_freq]

    return result


async def exp_gen_palette(img: Path, light: bool = False) -> Palette:
    # TODO refactor everything
    # hsv: 340.32, 0.9, 0.9

    def apply_rule(clr: Tuple[float, ...], rule: dict[str, float]) -> Tuple[float, ...]:
        h, s, v = clr

        if s < rule["min_sat"]:
            s = rule["min_sat"]
        elif s > rule["max_sat"]:
            s = rule["max_sat"]

        if v < rule["min_val"]:
            v = rule["min_val"]
        elif v > rule["max_val"]:
            v = rule["max_val"]

        return h, s, v

    def are_hues_close(h1: float, h2: float, r: int = 30) -> bool:
        if abs(h1 - h2) < r:
            return True
        elif h1 - r < 0 and h1 + 360 - h2 < r:
            return True
        elif h2 - r < 0 and h2 + 360 - h1 < r:
            return True
        return False

    timer = Timer()

    extracted_colors = extract_colors(img)
    extracted_hsv_colors = [(c.hsv(), f) for c, f in extracted_colors]

    main_color = extracted_hsv_colors[0][0]

    by_sat = sorted(extracted_hsv_colors, reverse=True, key=lambda x: x[0][1])
    by_sat_no_dark = [c for c in by_sat if c[0][2] > 0.3]

    saturated_colors = [
        c[0] for c in sorted(by_sat_no_dark, reverse=True, key=lambda x: x[1])
    ]

    if are_hues_close(saturated_colors[0][0], main_color[0]):
        saturated_colors.pop(0)

    primary = saturated_colors[0] if len(saturated_colors) > 0 else by_sat.pop(0)[0]
    secondary = saturated_colors[1] if len(saturated_colors) > 1 else by_sat.pop(0)[0]
    accent = saturated_colors[2] if len(saturated_colors) > 2 else by_sat.pop(0)[0]

    most_saturated = primary

    dark_rules: dict[str, Any] = {
        "normal": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "panel": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.15, "max_val": 0.2},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "dialog": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "primary": {
            "color": primary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "secondary": {
            "color": secondary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "term": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
        "input": {
            "color": primary,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "border": {
            "color": primary,
            "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.5, "max_val": 0.9},
            "inactive": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.2},
        },
        "accent": {
            "color": accent,
            "bg": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "muted": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.3, "min_val": 0.8, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "destructive": {
            "color": accent,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
    }

    light_rules: dict[str, Any] = {
        "normal": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.95},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "panel": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.85, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "dialog": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "primary": {
            "color": primary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "secondary": {
            "color": secondary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "term": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.3, "max_val": 0.5},
        "input": {
            "color": primary,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "border": {
            "color": primary,
            "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.6, "max_val": 0.9},
            "inactive": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.9},
        },
        "accent": {
            "color": accent,
            "bg": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.45, "max_val": 0.65},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "muted": {
            "color": main_color,
            "bg": {"min_sat": 0.3, "max_sat": 0.5, "min_val": 0.45, "max_val": 0.65},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "destructive": {
            "color": accent,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
    }

    rules = light_rules if light else dark_rules

    palette: dict[str, Any] = {}

    for outer_name, outer in rules.items():
        if outer_name == "term":
            palette["term"] = {
                "color0": apply_rule(main_color, rules["normal"]["bg"]),
                "color15": apply_rule(main_color, rules["normal"]["fg"]),
            }
            continue
        if outer_name not in palette:
            palette[outer_name] = {}
        for inner_name, rule in outer.items():
            if inner_name == "color":
                continue
            palette[outer_name][inner_name] = apply_rule(outer["color"], rule)

    for k, v in palette.items():
        if "bg" in v and "fg" in v:
            if v["bg"][2] > 0.7 and v["bg"][2] - v["fg"][2] < 0.65:
                new_fg_v = v["bg"][2] - 0.65
                if new_fg_v < 0.1:
                    new_fg_v = 0.1
                v["fg"] = (v["fg"][0], v["fg"][1], new_fg_v)
            elif v["bg"][2] < 0.7 and v["fg"][2] - v["bg"][2] < 0.65:
                new_fg_v = v["bg"][2] + 0.65
                if new_fg_v > 0.9:
                    new_fg_v = 0.9
                v["fg"] = (v["fg"][0], v["fg"][1], new_fg_v)

    base = palette["term"]["color0"]
    palette["term"][f"color{8}"] = apply_rule(
        (base[0], 0.3, base[2] + (-0.3 if light else 0.3)), rules["term"]
    )

    for i in range(1, 8):
        hue = most_saturated[0] + 45 * (i - 1)
        if hue > 360:
            hue -= 360

        palette["term"][f"color{i}"] = apply_rule(
            (hue, most_saturated[1], most_saturated[2]),
            rules["term"],
        )

    for i in range(9, 15):
        h, s, v = palette["term"][f"color{i-8}"]

        palette["term"][f"color{i}"] = apply_rule(
            (
                h,
                s - 0.1,
                v - 0.1,
            ),
            rules["term"],
        )

    def to_color(d: dict[str, Any]) -> dict[str, Any]:
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = to_color(v)
            else:
                r, g, b = [
                    int(x * 255) for x in colorsys.hsv_to_rgb(v[0] / 360, v[1], v[2])
                ]
                d[k] = Color((r, g, b))

        return d

    palette = to_color(palette)

    p = Palette(**palette)

    log.info(
        f'{"light" if light else "dark"} colors for "{img.name}" generated in {timer.elapsed():.2f} seconds'
    )

    return p
