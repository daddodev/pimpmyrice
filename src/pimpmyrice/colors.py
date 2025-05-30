from __future__ import annotations

import colorsys
import logging
import re
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue, SkipJsonSchema
from pydantic_core import CoreSchema, core_schema

from pimpmyrice.config_paths import PALETTES_DIR
from pimpmyrice.files import load_json

log = logging.getLogger(__name__)


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

    @staticmethod
    def _parse_tuple(
        value: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        # TODO parse hsl, hsla, hsv(a)
        if len(value) == 3:
            return tuple(value) + (255,)  # type: ignore
        elif len(value) == 4:
            return tuple(value)  # type: ignore
        else:
            raise ValueError("Invalid tuple length for RGBA value")

    @staticmethod
    def _parse_str(value: str) -> tuple[int, int, int, int]:
        # TODO parse rgb(a), hsla, hsva
        if value.startswith("#"):
            return Color._parse_hex(value)
        elif value.startswith("hsl("):
            return Color._parse_hsl(value)
        elif value.startswith("hsv("):
            return Color._parse_hsv(value)
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

    @staticmethod
    def _parse_hsv(value: str) -> tuple[int, int, int, int]:
        hsv_match = re.match(r"hsv\((\d+),\s*(\d+)%?,\s*(\d+)%?\)", value)
        if not hsv_match:
            raise ValueError("Invalid HSV string format")

        h = int(hsv_match.group(1))
        s = int(hsv_match.group(2))
        v = int(hsv_match.group(3))

        r, g, b = colorsys.hsv_to_rgb(h / 360, s / 100, v / 100)
        rgb = tuple(int(x * 255) for x in (r, g, b))

        return rgb + (255,)  # type: ignore

    @property
    def alpha(self) -> int:
        return self._rgba[3]

    @property
    def hex(self) -> str:
        return f"#{''.join(self.hex_tuple())}"

    @property
    def hexa(self) -> str:
        return f"#{''.join(self.hex_tuple(alpha=True))}"

    @property
    def nohash(self) -> str:
        return self.hex[1:]

    @property
    def nohasha(self) -> str:
        return self.hexa[1:]

    def hex_tuple(self, alpha: bool = False) -> tuple[str, ...]:
        return tuple(
            f"{hex(x)[2:]:0>2}" for x in (self._rgba if alpha else self._rgba[:3])
        )

    @property
    def rgb(self) -> str:
        return f"rgb({', '.join(map(str, self._rgba[:3]))})"

    @property
    def rgba(self) -> str:
        return f"rgba({', '.join(map(str, self._rgba))})"

    def rgb_tuple(self, alpha: bool = False) -> tuple[int, ...]:
        return self._rgba if alpha else self._rgba[:3]

    @property
    def hsl(self) -> str:
        return f"hsl({', '.join(map(str, self.hsl_tuple()))})"

    @property
    def hsla(self) -> str:
        return f"hsla({', '.join(map(str, self.hsl_tuple(alpha=True)))})"

    def hsl_tuple(self, alpha: bool = False) -> tuple[int, ...]:
        h, l, s = colorsys.rgb_to_hls(*[x / 255 for x in self._rgba[:3]])
        hsl = (int(h * 360), int(s * 100), int(l * 100))
        return hsl + (self._rgba[3],) if alpha else hsl

    @property
    def hsv(self) -> str:
        return f"hsv({', '.join(map(str, self.hsv_tuple()))})"

    @property
    def hsva(self) -> str:
        return f"hsva({', '.join(map(str, self.hsv_tuple(alpha=True)))})"

    def hsv_tuple(self, alpha: bool = False) -> tuple[int, ...]:
        h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in self._rgba[:3]])
        hsv = (int(h * 360), int(s * 100), int(v * 100))
        return hsv + (self._rgba[3],) if alpha else hsv

    def contrasting(self, base: Color | None = None, val_delta: int = 75) -> Color:
        h, s, v = self.hsv_tuple()

        if base:
            base_h, base_s, base_v = base.hsv_tuple()
            if base_v < 50:
                v = min(base_v + val_delta, 100)
            else:
                v = max(base_v - val_delta, 0)
        else:
            if v < 50:
                v = min(v + val_delta, 100)
            else:
                v = max(v - val_delta, 0)

        return Color(f"hsv({h}, {s}%, {v}%)")

    def adjusted(
        self,
        hue: int | str | None = None,  # example: "+10", "-10", 30, None
        min_hue: int | None = None,
        max_hue: int | None = None,
        sat: int | str | None = None,
        min_sat: int | None = None,
        max_sat: int | None = None,
        val: int | str | None = None,
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> "Color":
        """
        using HSV
        """

        def _adjust(
            value: int,
            adjustment: int | str | None,
            min_val: int | None,
            max_val: int | None,
            wrap_basis: int | None,
        ) -> int:
            if isinstance(adjustment, str):
                if adjustment.startswith("+"):
                    value += int(adjustment[1:])
                elif adjustment.startswith("-"):
                    value -= int(adjustment[1:])
                else:
                    raise ValueError(f'invalid adjustment format: "{adjustment}"')
            elif isinstance(adjustment, int):
                value = adjustment

            if min_val is not None:
                value = max(min_val, value)
            if max_val is not None:
                value = min(max_val, value)

            if wrap_basis:
                value %= wrap_basis
                return max(0, min(wrap_basis, value))
            else:
                return max(0, min(100, value))

        h, s, v = self.hsv_tuple()
        h = _adjust(h, hue, min_hue, max_hue, 360)
        s = _adjust(s, sat, min_sat, max_sat, None)
        v = _adjust(v, val, min_val, max_val, None)

        clr = Color(f"hsv({h}, {s}%, {v}%)")
        clr._rgba = clr._rgba[:3] + (self._rgba[3],)
        return clr

    def copy(self) -> "Color":
        return Color(self)

    def __str__(self) -> str:
        return self.hex if self.alpha == 255 else self.hexa

    def __repr__(self) -> str:
        return f"Color({self.hex})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Color) and self._rgba == other._rgba

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
    primary: BgFgColors
    secondary: BgFgColors


class LinkPalette(BaseModel):
    from_global: str


class GlobalPalette(Palette):
    name: str
    path: SkipJsonSchema[Path | None] = Field(default=None, exclude=True)


def get_palettes() -> dict[str, GlobalPalette]:
    palettes = {}
    for file in PALETTES_DIR.iterdir():
        try:
            palette = load_json(file)
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
