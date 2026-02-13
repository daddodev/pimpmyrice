from __future__ import annotations

import logging
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import psutil
from typing_extensions import TypeVar

from pimpmyrice.config_paths import THUMBNAILS_DIR

log = logging.getLogger(__name__)


class Timer:
    """Monotonic wall-clock timer utility."""

    def __init__(self) -> None:
        self.start = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since construction."""
        return time.perf_counter() - self.start


class AttrDict(dict[str, Any]):
    """
    Dict allowing attribute accessing values using keys as attributes.

    Allows deep-merging with `+` operator.
    Values in `other` take precedence over values in `self`.
    """

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
        """
        Deep-merge another mapping into a new `AttrDict`.
        Values in `other` take precedence over values in `self`.

        Args:
            other (DictOrAttrDict): Mapping to merge in.

        Returns:
            AttrDict: Merged copy.
        """

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
    """
    Check if a process is running by name or PID (mutually exclusive).

    Args:
        name (str | None): Process name to look for.
        pid (int | None): Process ID to look for.

    Returns:
        bool: True if a matching process is found.

    Raises:
        Exception: If both or neither of `name` and `pid` are provided.
    """
    if (not name and not pid) or (name and pid):
        raise Exception("provide either process pid or name")

    attr = "name" if name else "pid"
    val = name if name else pid

    for proc in psutil.process_iter([attr]):
        if proc.info[attr] == val:
            return True
    return False


def is_locked(lockfile: Path) -> tuple[bool, int]:
    """
    Determine whether a lockfile is held by a live process.

    Args:
        lockfile (Path): Path to lockfile containing the holder PID.

    Returns:
        tuple[bool, int]: (locked, pid). If unlocked, pid is 0.
    """
    if lockfile.exists():
        with open(lockfile, "r", encoding="utf-8") as f:
            file_pid = int(f.read())

        if is_process_running(pid=file_pid):
            return True, file_pid

        lockfile.unlink()
    return False, 0


class Lock:
    """Simple PID file lock context manager."""

    def __init__(self, lockfile: Path) -> None:
        self.lockfile = lockfile

    def __enter__(self) -> None:
        """Create the lock by writing current PID to the lockfile."""
        pid = os.getpid()
        with open(self.lockfile, "w", encoding="utf-8") as f:
            f.write(str(pid))

    def __exit__(self, *_: Any) -> None:
        """Release the lock by removing the lockfile."""
        self.lockfile.unlink()


def get_thumbnail(image_path: Path, max_px: int = 512) -> Path:
    """
    Create (or reuse) a square-bounded thumbnail next to the image.

    Args:
        image_path (Path): Source image path.
        max_px (int): Max width/height of the thumbnail. Defaults to 512.

    Returns:
        Path: Path to the generated thumbnail file.
    """
    from PIL import Image

    thumb_path = (
        THUMBNAILS_DIR
        / image_path.parent.name
        / f".{image_path.stem}_{max_px}{image_path.suffix}"
    )

    if thumb_path.is_file():
        return thumb_path

    if not thumb_path.parent.exists():
        thumb_path.parent.mkdir()

    log.debug(f"generating thumbnail for {image_path}")

    with Image.open(image_path) as img:
        img.thumbnail((max_px, max_px))
        img.save(thumb_path)

    log.debug(f'thumbnail generated for "{image_path}"')

    return thumb_path
