import json
import logging
import mimetypes
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from pimpmyrice import assets
from pimpmyrice.config import (
    BASE_STYLE_FILE,
    CONFIG_FILE,
    JSON_SCHEMA_DIR,
    MODULES_DIR,
    PALETTE_GENERATORS_DIR,
    PALETTES_DIR,
    STYLES_DIR,
    TEMP_DIR,
    THEMES_DIR,
)

log = logging.getLogger(__name__)


def load_yaml(file: Path) -> dict[str, Any]:
    with open(file, encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.Loader)
        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise Exception(f"expected type dict, found {type(data).__name__}")

        return data


def save_yaml(file: Path, data: dict[str, Any]) -> None:
    dump = yaml.dump(data, indent=4, default_flow_style=False)

    schema_file = JSON_SCHEMA_DIR / f"{file.stem}.json"
    if schema_file.exists():
        schema_str = f"# yaml-language-server: $schema={schema_file}\n\n"
        dump = schema_str + dump

    with open(file, "w", encoding="utf-8") as f:
        f.write(dump)


def load_json(file: Path) -> dict[str, Any]:
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

        if data is None:
            data = {}

        data.pop("$schema", None)

        return data  # type: ignore


def save_json(file: Path, data: dict[str, Any]) -> None:
    schema_file = JSON_SCHEMA_DIR / file.name
    if schema_file.exists():
        data["$schema"] = os.path.relpath(schema_file, file.parent)

    dump = json.dumps(data, indent=4)
    with open(file, "w", encoding="utf-8") as f:
        f.write(dump)


def import_image(image_path: Path, theme_dir: Path) -> Path:
    if (
        not image_path.exists() or not image_path.is_file()
    ):  # to do: process files/folders
        raise FileNotFoundError(f'file not found at "{image_path}"')

    dest = theme_dir / image_path.name
    if (dest).exists():
        raise Exception(f'file already exists at "{dest}"')

    shutil.copy(image_path, theme_dir)
    log.debug(f'image "{image_path}" copied to {dest}')
    return dest


def create_config_dirs() -> None:
    for dir in [
        THEMES_DIR,
        STYLES_DIR,
        PALETTES_DIR,
        MODULES_DIR,
        PALETTE_GENERATORS_DIR,
        TEMP_DIR,
        JSON_SCHEMA_DIR,
    ]:
        dir.mkdir(exist_ok=True, parents=True)

    if not BASE_STYLE_FILE.exists():
        with resources.as_file(
            resources.files(assets) / "default_base_style.json"
        ) as source:
            shutil.copy(source, BASE_STYLE_FILE)

    if not CONFIG_FILE.exists():
        config = {"theme": None, "mode": "dark"}
        save_json(CONFIG_FILE, config)

    # TODO default palette generators

    # if not VENV_DIR.exists():
    #     create_venv()


def download_file(url: str, destination: Path = TEMP_DIR) -> Path:
    # TODO better filename

    import requests

    response = requests.get(url, stream=True)

    if response.status_code != 200:
        raise Exception(
            f"Failed to download image. Status code: {response.status_code}"
        )

    content_type = response.headers.get("content-type")
    file_extension = mimetypes.guess_extension(content_type) if content_type else None

    if not file_extension:
        file_extension = ".jpg"

    filename = url.split("/")[-1].split("?")[0]

    if not filename.endswith(file_extension):
        filename = filename + file_extension

    save_path = destination / filename

    tries = 1
    while save_path.exists():
        save_path = save_path.parent / f"{save_path.stem}_{tries + 1}{save_path.suffix}"

    with open(save_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    return save_path
