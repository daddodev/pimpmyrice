import colorsys
from functools import cache
from pathlib import Path
from typing import Any, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pimpmyrice.colors import Color, Palette
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import Timer

log = get_logger(__name__)


def kmeans(
    pixels: NDArray[np.uint8],
    num_clusters: int = 6,
    max_iter: int = 100,
    tol: float = 1e-4,
) -> list[tuple[tuple[int, int, int], int]]:
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


# TODO change resize_factor to resize_to_size
@cache
def extract_colors(
    image_path: Path, num_colors: int = 6, resize_factor: float = 0.2
) -> list[tuple[Color, int]]:
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    img = img.resize((int(width * resize_factor), int(height * resize_factor)))

    img_array: NDArray[np.uint8] = np.array(img)
    pixels: NDArray[np.uint8] = img_array.reshape(-1, 3)

    sorted_colors_with_count = kmeans(pixels, num_clusters=num_colors)

    result = [(Color(color), count) for color, count in sorted_colors_with_count]

    return result


# wanted
variables = {""}
wanted: dict[str, Any] = {
    "normal": {
        "color": "{{most_common.sort()[0]}}",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "primary": {
        "color": "{{by_sat[0]}}",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "accent": {
        "color": "{{by_sat[0]}}",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "term": {
        "color0": {
            "color": "{{extracted[0]}}",
            "color": "{{most_common.sort()[0]}}",
            "min_sat": 0.1,
            "max_sat": 0.5,
            "min_val": 0,
            "max_val": 0.1,
        },
        "color1": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "color2": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "color3": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
    },
}

dark_rules: dict[str, Any] = {
    "term": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
    "normal": {
        "color": "main",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "panel": {
        "color": "main",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.15, "max_val": 0.2},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "dialog": {
        "color": "main",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "primary": {
        "color": "primary",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "secondary": {
        "color": "secondary",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 1},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "input": {
        "color": "primary",
        "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
        "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "border": {
        "color": "primary",
        "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.5, "max_val": 0.9},
        "inactive": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.2},
    },
    "accent": {
        "color": "accent",
        "bg": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "muted": {
        "color": "main",
        "bg": {"min_sat": 0.1, "max_sat": 0.3, "min_val": 0.8, "max_val": 1},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
    "destructive": {
        "color": "accent",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
    },
}

light_rules: dict[str, Any] = {
    "term": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.3, "max_val": 0.5},
    "normal": {
        "color": "main",
        "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.95},
        "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
    },
    "panel": {
        "color": "main",
        "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.85, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
    },
    "dialog": {
        "color": "main",
        "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
        "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
    },
    "primary": {
        "color": "primary",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
    },
    "secondary": {
        "color": "secondary",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
    },
    "input": {
        "color": "primary",
        "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
        "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
    },
    "border": {
        "color": "primary",
        "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.6, "max_val": 0.9},
        "inactive": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.9},
    },
    "accent": {
        "color": "accent",
        "bg": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.45, "max_val": 0.65},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
    },
    "muted": {
        "color": "main",
        "bg": {"min_sat": 0.3, "max_sat": 0.5, "min_val": 0.45, "max_val": 0.65},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
    },
    "destructive": {
        "color": "accent",
        "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
        "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
    },
}


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


def are_hues_close(hue1: float, hue2: float, tolerance: int = 30) -> bool:
    if abs(hue1 - hue2) < tolerance:
        return True
    elif hue1 - tolerance < 0 and hue1 + 360 - hue2 < tolerance:
        return True
    elif hue2 - tolerance < 0 and hue2 + 360 - hue1 < tolerance:
        return True
    return False


# TODO parallelize, refactor everything
async def gen_palette(img: Path, light: bool = False) -> Palette:
    log.info(f'generating {"light" if light else "dark"} palette for "{img.name}"')
    # hsv: 340.32, 0.9, 0.9

    timer = Timer()

    extracted = extract_colors(img)
    hsv_with_count = [(c.hsv_tuple(), f) for c, f in extracted]

    # print(f"{extracted=}")
    # print(f"{hsv_with_count=}")

    # for mode in

    main_color = hsv_with_count[0][0]

    by_sat = sorted(hsv_with_count, reverse=True, key=lambda x: x[0][1])
    by_sat_no_dark = [c for c in by_sat if c[0][2] > 0.3]

    saturated_colors = [
        c[0] for c in sorted(by_sat_no_dark, reverse=True, key=lambda x: x[1])
    ]

    if are_hues_close(saturated_colors[0][0], main_color[0]):
        saturated_colors.pop(0)

    primary = saturated_colors[0] if len(saturated_colors) > 0 else by_sat.pop(0)[0]
    secondary = saturated_colors[1] if len(saturated_colors) > 1 else by_sat.pop(0)[0]
    accent = saturated_colors[2] if len(saturated_colors) > 2 else by_sat.pop(0)[0]

    pltt = {
        "main": main_color,
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
    }

    # print(f"{pltt}")

    rules = light_rules if light else dark_rules

    palette: dict[str, Any] = {}

    # APPLY RULES

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
            palette[outer_name][inner_name] = apply_rule(pltt[outer["color"]], rule)

    # ENSURE BG/FG CONTRAST

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

    # GENERATE TERM COLORS

    base = palette["term"]["color0"]
    palette["term"][f"color{8}"] = apply_rule(
        (base[0], 0.3, base[2] + (-0.3 if light else 0.3)), rules["term"]
    )

    for i in range(1, 8):
        hue = primary[0] + 45 * (i - 1)
        if hue > 360:
            hue -= 360

        palette["term"][f"color{i}"] = apply_rule(
            (hue, primary[1], primary[2]),
            rules["term"],
        )

    for i in range(9, 15):
        h, s, v = palette["term"][f"color{i - 8}"]

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

    # print(p)

    return p
