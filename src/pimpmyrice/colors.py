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
    _rgba: tuple[float, float, float, float]
    _original: str | Color

    def __init__(self, value: str | "Color") -> None:
        if isinstance(value, str):
            self._rgba = self._parse_str(value.strip())
            self._original = value
        elif isinstance(value, Color):
            self._rgba = value._rgba
            self._original = value._original
        else:
            raise ValueError(
                "value is not a valid color: value must be a string or Color()"
            )

    @staticmethod
    def _parse_str(value: str) -> tuple[float, float, float, float]:
        if value.startswith("#"):
            return Color._parse_hex(value)
        elif value.startswith("rgb"):
            return Color._parse_rgb(value)
        elif value.startswith("hsl"):
            return Color._parse_hsl(value)
        elif value.startswith("hsv"):
            return Color._parse_hsv(value)
        raise ValueError(f'Invalid color string format: "{value}"')

    @staticmethod
    def _parse_rgb(value: str) -> tuple[float, float, float, float]:
        value_string = value.split("(")[1][:-1]
        values = value_string.split(",")

        r = int(values[0]) / 255
        g = int(values[1]) / 255
        b = int(values[2]) / 255
        a = (float(values[3])) if len(values) > 3 else 1.0

        return r, g, b, a

    @staticmethod
    def _parse_hex(value: str) -> tuple[float, float, float, float]:
        value = value[1:]
        parsed = tuple(int(value[i : i + 2], 16) / 255 for i in range(0, len(value), 2))

        if len(parsed) == 4:
            return parsed
        elif len(parsed) == 3:
            return parsed + (1.0,)
        else:
            raise ValueError("Invalid hex string format: {value}")

    @staticmethod
    def _parse_hsl(value: str) -> tuple[float, float, float, float]:
        value_string = value.split("(")[1][:-1]
        values = [x.strip("% ") for x in value_string.split(",")]

        h = int(values[0])
        s = int(values[1])
        l = int(values[2])

        r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        a = (float(values[3])) if len(values) > 3 else 1.0

        return r, g, b, a

    @staticmethod
    def _parse_hsv(value: str) -> tuple[float, float, float, float]:
        value_string = value.split("(")[1][:-1]
        values = [x.strip("% ") for x in value_string.split(",")]

        h = int(values[0])
        s = int(values[1])
        v = int(values[2])

        r, g, b = colorsys.hsv_to_rgb(h / 360, s / 100, v / 100)
        a = (float(values[3])) if len(values) > 3 else 1.0

        return r, g, b, a

    @property
    def alpha(self) -> float:
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
            f"{hex(int(x*255))[2:]:0>2}"
            for x in (self._rgba if alpha else self._rgba[:3])
        )

    @property
    def rgb(self) -> str:
        return f"rgb({', '.join([str(int(v*255)) for v in self._rgba[:3]])})"

    @property
    def rgba(self) -> str:
        return f"rgba({', '.join([str(int(v*255)) for v in self._rgba])})"

    def rgb_tuple(self, alpha: bool = False) -> tuple[float, ...]:
        return self._rgba if alpha else self._rgba[:3]

    @property
    def hsl(self) -> str:
        h, s, l = self.hsl_tuple()
        return f"hsl({int(h * 360)}, {int(s * 100)}%, {int(l * 100)}%)"

    @property
    def hsla(self) -> str:
        h, s, l, a = self.hsl_tuple(alpha=True)
        return f"hsla({int(h * 360)}, {int(s * 100)}%, {int(l * 100)}%, {round(a, 2)})"

    def hsl_tuple(self, alpha: bool = False) -> tuple[float, ...]:
        h, l, s = colorsys.rgb_to_hls(*self._rgba[:3])
        return (h, s, l, self._rgba[3]) if alpha else (h, s, l)

    @property
    def hsv(self) -> str:
        h, s, v = self.hsv_tuple()
        return f"hsv({int(h * 360)}, {int(s * 100)}%, {int(v * 100)}%)"

    @property
    def hsva(self) -> str:
        h, s, v, a = self.hsv_tuple(alpha=True)
        return f"hsva({int(h * 360)}, {int(s * 100)}%, {int(v * 100)}%, {round(a, 2)})"

    def hsv_tuple(self, alpha: bool = False) -> tuple[float, ...]:
        h, s, v = colorsys.rgb_to_hsv(*self._rgba[:3])
        return (h, s, v, self._rgba[3]) if alpha else (h, s, v)

    def contrasting(self, base: Color | None = None, val_delta: int = 75) -> Color:
        h, s, v, a = self.hsv_tuple(alpha=True)
        delta = val_delta / 100

        if base:
            base_v = base.hsv_tuple()[2]
            if base_v < 0.5:
                v = min(base_v + delta, 1.0)
            else:
                v = max(base_v - delta, 0.0)
        else:
            if v < 0.5:
                v = min(v + delta, 1.0)
            else:
                v = max(v - delta, 0.0)

        return Color(
            f"hsva({int(h * 360)}, {int(s * 100)}%, {int(v * 100)}%, {round(a, 2)})"
        )

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
        alpha: int | str | None = None,
        min_alpha: int | None = None,
        max_alpha: int | None = None,
    ) -> "Color":
        """
        using HSV
        """

        def _adjust(
            value: int,
            adjustment: int | str | None,
            min_val: int | None,
            max_val: int | None,
            wrap_basis: int | None = None,
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

        h, s, v, a = self.hsv_tuple(alpha=True)
        h = _adjust(int(h * 360), hue, min_hue, max_hue, 360)
        s = _adjust(int(s * 100), sat, min_sat, max_sat)
        v = _adjust(int(v * 100), val, min_val, max_val)
        a = _adjust(int(a * 100), alpha, min_alpha, max_alpha) / 100

        clr = Color(f"hsva({h}, {s}%, {v}%, {a})")
        return clr

    def copy(self) -> "Color":
        return Color(self)

    def __str__(self) -> str:
        return self.hex

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
