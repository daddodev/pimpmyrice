import logging
import random
import shutil
from pathlib import Path
from typing import Any

import rich

from pimpmyrice import parsers, schemas
from pimpmyrice import theme_utils as tutils
from pimpmyrice.colors import GlobalPalette, get_palettes
from pimpmyrice.completions import generate_shell_suggestions
from pimpmyrice.config import BASE_STYLE_FILE, CONFIG_FILE, STYLES_DIR, THEMES_DIR
from pimpmyrice.events import EventHandler
from pimpmyrice.files import create_config_dirs, download_file, load_json, save_json
from pimpmyrice.module import ModuleManager
from pimpmyrice.theme_utils import (
    Mode,
    PaletteGeneratorType,
    Style,
    Theme,
    ThemeConfig,
    get_palette_generators,
)
from pimpmyrice.utils import Timer

log = logging.getLogger(__name__)


class ThemeManager:
    def __init__(self) -> None:
        timer = Timer()
        create_config_dirs()
        self.base_style = self.get_base_style()
        self.styles = self.get_styles()
        self.palettes = self.get_palettes()
        self.palette_generators = self.get_palette_generators()
        self.tags: set[str] = set()
        self.themes = self.get_themes()
        self.config = self.get_config()
        self.event_handler = EventHandler()
        self.mm = ModuleManager()

        # TODO move
        try:
            schemas.generate_theme_json_schema(self)
            schemas.generate_module_json_schema()
            generate_shell_suggestions(self)
        except Exception as e:
            log.exception(e)
            log.error("failed to generate suggestions")

        log.debug(f"ThemeManager initialized in {timer.elapsed():.4f} sec")

    def get_config(self) -> ThemeConfig:
        config = ThemeConfig(**load_json(CONFIG_FILE))
        if config.theme not in self.themes:
            config.theme = None
        return config

    def save_config(self) -> None:
        save_json(CONFIG_FILE, vars(self.config))

    @staticmethod
    def get_base_style() -> dict[str, Any]:
        try:
            return load_json(BASE_STYLE_FILE)
        except Exception:
            log.error("failed loading base_style.json")
            raise

    def save_base_style(self, base_style: dict[str, Any]) -> None:
        save_json(BASE_STYLE_FILE, base_style)
        self.base_style = base_style
        schemas.generate_theme_json_schema(self)

    @staticmethod
    def get_styles() -> dict[str, Style]:
        styles: dict[str, Style] = {f.stem: load_json(f) for f in STYLES_DIR.iterdir()}
        return styles

    @staticmethod
    def get_palettes() -> dict[str, GlobalPalette]:
        return get_palettes()

    @staticmethod
    def get_palette_generators() -> dict[str, PaletteGeneratorType]:
        return get_palette_generators()

    def parse_theme(self, theme_path: Path) -> Theme:
        theme = parsers.parse_theme(theme_path)

        return theme

    def get_themes(self) -> dict[str, Theme]:
        timer = Timer()

        themes: dict[str, Theme] = {}

        for directory in THEMES_DIR.iterdir():
            if not (directory / "theme.json").is_file():
                continue

            try:
                theme = self.parse_theme(directory)
            except Exception as e:
                log.exception(e)
                log.error(f'Error parsing theme "{directory.name}": {str(e)}')
                continue

            themes[directory.name] = theme

            for tag in theme.tags:
                self.tags.add(tag)

        log.debug(f"{len(themes)} themes loaded in {timer.elapsed():.4f} sec")

        return themes

    async def generate_theme(
        self,
        image: str,
        name: str | None = None,
        tags: set[str] | None = None,
        apply: bool = False,
    ) -> None:
        if image.startswith(("http://", "https://")):
            file = download_file(image)
            log.info(f'downloaded "{file.name}"')
        else:
            file = Path(image)

        theme = await tutils.gen_from_img(
            image=file,
            name=name,
            generators=self.palette_generators,
            themes=self.themes,
        )

        if tags:
            theme.tags = tags

        # TODO generate name here
        await self.save_theme(theme)
        log.info(f'theme "{theme.name}" generated')

        if apply:
            await self.apply_theme(theme.name)

    async def rename_theme(
        self,
        theme_name: str,
        new_name: str,
    ) -> None:
        if theme_name not in self.themes:
            raise Exception(f'theme "{theme_name}" not found')

        theme = self.themes[theme_name]
        old_name = theme.name
        theme.name = new_name

        await self.save_theme(theme, old_name=old_name)

        log.info(f'renamed theme "{theme_name}" to "{new_name}"')

    async def save_theme(
        self,
        theme: Theme,
        old_name: str | None = None,
    ) -> str:
        # TODO move theme name check
        if not old_name:
            theme.name = tutils.valid_theme_name(name=theme.name, themes=self.themes)
            theme_dir = THEMES_DIR / theme.name
            theme_dir.mkdir()

        elif old_name != theme.name:
            theme.name = tutils.valid_theme_name(name=theme.name, themes=self.themes)
            theme_dir = THEMES_DIR / theme.name
            (THEMES_DIR / old_name).rename(theme_dir)
        else:
            theme_dir = THEMES_DIR / theme.name

        # NOTE full path update on rename is handled by dump_theme
        #      as it leaves only the filename
        theme.wallpaper.path = tutils.import_image(theme.wallpaper.path, theme_dir)
        for mode in theme.modes.values():
            if mode.wallpaper:
                mode.wallpaper.path = tutils.import_image(
                    mode.wallpaper.path, theme_dir
                )

        dump = tutils.dump_theme_for_file(theme)

        save_json(theme_dir / "theme.json", dump)
        # save_yaml(theme_dir / "theme.yaml", dump)

        parsed_theme = self.parse_theme(THEMES_DIR / theme.name)

        self.themes[theme.name] = parsed_theme

        if old_name and old_name != theme.name:
            self.themes.pop(old_name)

            if self.config.theme == old_name:
                self.config.theme = theme.name

        return theme.name

    async def rewrite_themes(
        self,
        regen_colors: bool = False,
        name_includes: str | None = None,
        include_tags: set[str] | None = None,
        exclude_tags: set[str] | None = None,
    ) -> None:
        for theme in self.themes.values():
            if name_includes and name_includes not in theme.name:
                continue

            if include_tags and not any(tag in include_tags for tag in theme.tags):
                continue

            if exclude_tags and any(tag in exclude_tags for tag in theme.tags):
                continue

            if regen_colors:
                for gen_name, gen_fn in self.palette_generators.items():
                    if gen_name not in theme.modes:
                        palette = await gen_fn(theme.wallpaper.path)
                        theme.modes[gen_name] = Mode(
                            name=gen_name,
                            wallpaper=theme.wallpaper,
                            palette=palette,
                        )
                    else:
                        mode = theme.modes[gen_name]
                        if not mode.wallpaper:
                            # should not happen, TODO refactor mode
                            continue
                        mode.palette = await gen_fn(mode.wallpaper.path)

            await self.save_theme(theme=theme, old_name=theme.name)
            log.info(f'theme "{theme.name}" rewritten')

    def delete_theme(self, theme_name: str) -> None:
        if theme_name not in self.themes:
            raise Exception(f'theme "{theme_name}" not found')

        theme = self.themes[theme_name]

        if not str(theme.path).startswith(str(THEMES_DIR)) or theme.path == THEMES_DIR:
            raise Exception(f'"{theme.path}" not in "{THEMES_DIR}"')

        shutil.rmtree(theme.path)

        if theme_name == self.config.theme:
            self.config.theme = None
        self.themes.pop(theme_name)

        log.info(f'theme "{theme_name}" deleted')

    async def apply_theme(
        self,
        theme_name: str | None = None,
        mode_name: str | None = None,
        palette_name: str | None = None,
        styles_names: list[str] | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> None:
        if not theme_name:
            if not self.config.theme:
                raise Exception("No current theme")
            theme_name = self.config.theme
        elif theme_name not in self.themes:
            raise Exception(f'theme "{theme_name}" not found')

        if not mode_name:
            mode_name = self.config.mode

        log.info(f'applying theme "{theme_name}" {mode_name}...')

        try:
            theme_dict = tutils.gen_theme_dict(
                self,
                theme_name=theme_name,
                mode_name=mode_name,
                styles_names=styles_names,
                palette_name=palette_name,
            )
        except Exception as e:
            log.error(str(e))
            raise Exception(f'error generating the theme_dict for theme "{theme_name}"')

        if print_theme_dict:
            pretty = rich.pretty.pretty_repr(theme_dict)
            log.info("generated theme_dict:\r\n" + pretty)

        await self.mm.run_modules(theme_dict, include_modules, exclude_modules)

        self.config.theme = theme_name
        self.config.mode = mode_name
        self.save_config()

        log.info(f'theme "{theme_name}" {mode_name} applied')

        await self.event_handler.publish("theme_applied")

    async def set_random_theme(
        self,
        mode_name: str | None = None,
        styles_names: list[str] | None = None,
        palette_name: str | None = None,
        name_includes: str | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        include_tags: set[str] | None = None,
        exclude_tags: set[str] | None = None,
        print_theme_dict: bool = False,
    ) -> None:
        themes_list: list[Theme] = []

        for theme in self.themes.values():
            if theme.name == self.config.theme:
                continue

            if name_includes and name_includes not in theme.name:
                continue

            if include_tags and not any(tag in include_tags for tag in theme.tags):
                continue

            if exclude_tags and any(tag in exclude_tags for tag in theme.tags):
                continue

            themes_list.append(theme)

        if len(themes_list) < 1:
            raise Exception("no theme found")

        theme_name = random.choice(themes_list).name
        await self.apply_theme(
            theme_name,
            mode_name=mode_name,
            styles_names=styles_names,
            palette_name=palette_name,
            include_modules=include_modules,
            exclude_modules=exclude_modules,
            print_theme_dict=print_theme_dict,
        )

    async def toggle_mode(self) -> None:
        if not self.config.theme:
            raise Exception("no theme set")

        mode_name = "light" if self.config.mode == "dark" else "dark"

        await self.apply_theme(mode_name=mode_name)

    async def set_mode(self, mode_name: str) -> None:
        if not self.config.theme:
            raise Exception("no theme set")

        return await self.apply_theme(mode_name=mode_name)

    async def add_tags(self, themes_names: list[str], tags: set[str]) -> None:
        for theme_name in themes_names:
            if theme_name not in self.themes:
                log.error('theme "{theme_name}" not found')
                continue

            theme = self.themes[theme_name]

            for tag in tags:
                theme.tags.add(tag)
                await self.save_theme(theme, theme.name)
                log.info(f'tag "{tag}" added to theme "{theme.name}"')

    async def remove_tags(self, themes_names: list[str], tags: set[str]) -> None:
        if len(themes_names) == 0:
            themes_names = list(self.themes.keys())

        for theme_name in themes_names:
            if theme_name not in self.themes:
                log.error('theme "{theme_name}" not found')
                continue

            theme = self.themes[theme_name]

            for tag in tags:
                if tag in theme.tags:
                    theme.tags.remove(tag)
                    await self.save_theme(theme, theme.name)
                    log.info(f'tag "{tag}" removed from theme "{theme.name}"')

    async def list_themes(self) -> None:
        log.info("\nNAME\t\t\tTAGS\n")
        for theme in self.themes.values():
            log.info(f"{theme.name:10}\t\t{', '.join(theme.tags)}")

    async def list_tags(self) -> None:
        log.info("\n".join(self.tags))

    async def list_palettes(self) -> None:
        for palette in self.palettes:
            log.info(f"{palette}")

    async def list_styles(self) -> None:
        for style in self.styles:
            log.info(f"{style}")

    async def export_theme(
        self,
        theme_name: str,
        out_dir: Path,
        mode_name: str | None = None,
        palette_name: str | None = None,
        styles_names: list[str] | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> None:
        if theme_name not in self.themes:
            raise Exception(f'theme "{theme_name}" not found')

        if not mode_name:
            mode_name = self.config.mode

        dump_dir = out_dir / f"{theme_name}_{mode_name}"

        if dump_dir.exists():
            raise Exception(f'directory "{dump_dir}" already exists')

        try:
            theme_dict = tutils.gen_theme_dict(
                self,
                theme_name=theme_name,
                mode_name=mode_name,
                styles_names=styles_names,
                palette_name=palette_name,
            )
        except Exception as e:
            log.error(str(e))
            raise Exception(f'error generating the theme_dict for theme "{theme_name}"')

        if print_theme_dict:
            pretty = rich.pretty.pretty_repr(theme_dict)
            log.info("generated theme_dict:\r\n" + pretty)

        # TODO check success
        await self.mm.run_modules(
            theme_dict, include_modules, exclude_modules, dump_dir
        )

        # res += modules_res
        # if not modules_res.value:
        #     return res.error(f'error exporting theme "{theme_name}"')

        theme = self.themes[theme_name]

        wp = theme.modes[mode_name].wallpaper
        if not wp:
            # should not happen
            raise Exception("wallpaper not found")

        shutil.copy(wp.path, dump_dir)

        readme = f"""# "{theme_name}" {mode_name} theme dotfiles

Dump generated with [pimp](https://github.com/daddodev/pimpmyrice) `export theme`

## Requirements:

"""

        # for module_name in modules_res.value:
        #     readme += f"- {module_name}\n"

        with open(dump_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)

        log.info(f'theme "{theme_name}" exported to {dump_dir}')
