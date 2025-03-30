from __future__ import annotations

import logging
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import psutil
from typing_extensions import TypeVar

log = logging.getLogger(__name__)


class Timer:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self.start


class AttrDict(dict[str, Any]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__dict__ = self
        super().__init__(*args, **kwargs)

        for k in self:
            if isinstance(self[k], dict):
                self[k] = AttrDict(self[k])

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(value, dict):
            value = AttrDict(value)
        super().__setitem__(key, value)

    def __add__(self, other: DictOrAttrDict) -> AttrDict:
        def merged(base: AttrDict, to_add: AttrDict) -> AttrDict:
            base = deepcopy(base)
            to_add = deepcopy(to_add)
            for k, v in to_add.items():
                if isinstance(v, (dict, AttrDict)):
                    if k in base:
                        base[k] = merged(base[k], to_add[k])
                    else:
                        base[k] = to_add[k]
                else:
                    base[k] = v
            return base

        return merged(self, AttrDict(other))


DictOrAttrDict = TypeVar("DictOrAttrDict", dict[str, Any], AttrDict)


def is_process_running(name: str | None = None, pid: int | None = None) -> bool:
    if (not name and not pid) or (name and pid):
        raise Exception("provide either process pid or name")

    attr = "name" if name else "pid"
    val = name if name else pid

    for proc in psutil.process_iter([attr]):
        if proc.info[attr] == val:
            return True
    return False


def is_locked(lockfile: Path) -> tuple[bool, int]:
    if lockfile.exists():
        with open(lockfile, "r", encoding="utf-8") as f:
            file_pid = int(f.read())

        if is_process_running(pid=file_pid):
            return True, file_pid

        lockfile.unlink()
    return False, 0


class Lock:
    def __init__(self, lockfile: Path) -> None:
        self.lockfile = lockfile

    def __enter__(self) -> None:
        pid = os.getpid()
        with open(self.lockfile, "w", encoding="utf-8") as f:
            f.write(str(pid))

    def __exit__(self, *_: Any) -> None:
        self.lockfile.unlink()


def get_thumbnail(image_path: Path, max_px: int = 512) -> Path:
    from PIL import Image

    thumb_path = image_path.parent / f".{image_path.stem}_{max_px}{image_path.suffix}"

    if thumb_path.is_file():
        return thumb_path

    log.debug(f"generating thumbnail for {image_path}")

    with Image.open(image_path) as img:
        img.thumbnail((max_px, max_px))
        img.save(thumb_path)

    log.debug(f'thumbnail generated for "{image_path}"')

    return thumb_path
