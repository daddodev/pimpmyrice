from __future__ import annotations

import colorsys
from collections import Counter
from pathlib import Path
from typing import Any, Tuple

import cv2
from pydantic import BaseModel, Field
from pydantic.color import Color as PydanticColor
from pydantic.json_schema import SkipJsonSchema
from sklearn.cluster import KMeans

from pimpmyrice import files
from pimpmyrice.config import PALETTES_DIR
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import Timer

log = get_logger(__name__)


class Color(PydanticColor):
    @property
    def alt(self) -> Color:
        h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in self.as_rgb_tuple()])
        if v > 0.5:
            v -= 0.1
        else:
            v += 0.1
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        rgb = tuple(int(x * 255) for x in (r, g, b))
        clr = Color(rgb)  # type:ignore
        return clr

    @property
    def maxsat(self) -> Color:
        h, *_ = self.as_hsl_tuple()
        hsl = f"hsl({int(h*360)}, 100%, 50%)"
        clr = Color(hsl)

        return clr

    @property
    def hex(self) -> str:
        return self.as_hex()

    @property
    def nohash(self) -> str:
        hex = self.as_hex()
        clr = hex[1:]
        return clr

    @property
    def hsv(self) -> tuple[int, float, float]:
        rgb = self.as_rgb_tuple()
        h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in rgb])
        clr = int(h * 360), s, v
        return clr

    # TODO hsl
    # @property
    # def hsl(self) -> tuple[int, float, float]:
    #     return clr

    @property
    def rgb(self) -> str:
        clr = self.as_rgb()
        return clr


class Palette(BaseModel):
    name: SkipJsonSchema[str | None] = Field(default=None, exclude=True)
    path: SkipJsonSchema[Path | None] = Field(default=None, exclude=True)
    term: dict[str, Color] | None = None
    normal: dict[str, Color] | None = None
    panel: dict[str, Color] | None = None
    dialog: dict[str, Color] | None = None
    input: dict[str, Color] | None = None
    border: dict[str, Color] | None = None
    muted: dict[str, Color] | None = None
    primary: dict[str, Color] | None = None
    secondary: dict[str, Color] | None = None
    accent: dict[str, Color] | None = None
    destructive: dict[str, Color] | None = None


def get_palettes() -> dict[str, Palette]:
    palettes = {}
    for file in PALETTES_DIR.iterdir():
        try:
            palette = files.load_json(file)
            palettes[file.stem] = Palette(name=file.stem, path=file, **palette)
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


def exp_extract_colors(img: Path) -> list[tuple[tuple[int, float, float], int]]:
    def preprocess(raw: Any) -> Any:
        image = cv2.resize(raw, (600, 600), interpolation=cv2.INTER_AREA)
        image = image.reshape(image.shape[0] * image.shape[1], 3)
        return image

    def analyze(img: Any) -> list[tuple[tuple[int, float, float], int]]:
        clf = KMeans(n_clusters=5, random_state=0, n_init="auto")
        color_labels = clf.fit_predict(img)
        center_colors = clf.cluster_centers_
        counts = Counter(color_labels)
        ordered_colors = [center_colors[i] for i in counts.keys()]

        color_objects = [
            (
                Color(tuple(ordered_colors[i])).hsv,
                c // 1000,
            )
            for i, c in counts.items()
        ]

        color_objects.sort(key=lambda x: x[1], reverse=True)

        return color_objects

    image = cv2.imread(str(img))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    modified_image = preprocess(image)
    colors = analyze(modified_image)

    return colors


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

    extracted_hsv_colors = exp_extract_colors(img)

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
            (hue, most_saturated[1], most_saturated[2]), rules["term"]
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
