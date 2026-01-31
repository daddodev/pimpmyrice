import os
import sys
from enum import Enum
from pathlib import Path


class Os(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MAC = "mac"

    def __str__(self) -> str:
        return self.value


APP_NAME = "pimpmyrice"


# --- Home directory (test override) ---
if os.environ.get("PIMP_TESTING"):
    HOME_DIR = Path("./tests/files").resolve()
else:
    HOME_DIR = Path.home()


# --- Platform-specific directories ---
match sys.platform:
    case "win32":
        CLIENT_OS = Os.WINDOWS

        OS_CONFIG_DIR = Path(os.environ["APPDATA"])
        OS_CACHE_DIR = Path(os.environ["LOCALAPPDATA"])

        PIMP_CONFIG_DIR = OS_CONFIG_DIR / APP_NAME
        PIMP_CACHE_DIR = OS_CACHE_DIR / APP_NAME
        PIMP_RUNTIME_DIR = PIMP_CACHE_DIR

    case "linux":
        CLIENT_OS = Os.LINUX

        OS_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME_DIR / ".config"))
        OS_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME_DIR / ".cache"))
        OS_RUNTIME_DIR = Path(
            os.environ.get("XDG_RUNTIME_DIR", HOME_DIR / ".local" / "run")
        )

        PIMP_CONFIG_DIR = OS_CONFIG_DIR / APP_NAME
        PIMP_CACHE_DIR = OS_CACHE_DIR / APP_NAME
        PIMP_RUNTIME_DIR = OS_RUNTIME_DIR / APP_NAME

    case "darwin":
        CLIENT_OS = Os.MAC

        OS_CONFIG_DIR = HOME_DIR / "Library/Application Support"
        OS_CACHE_DIR = HOME_DIR / "Library/Caches"
        PIMP_RUNTIME_DIR = HOME_DIR / "Library/Application Support" / APP_NAME / "run"

        PIMP_CONFIG_DIR = OS_CONFIG_DIR / APP_NAME
        PIMP_CACHE_DIR = OS_CACHE_DIR / APP_NAME

    case _:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


# --- Files & subdirectories ---

# Config
CONFIG_FILE = PIMP_CONFIG_DIR / "config.json"
BASE_STYLE_FILE = PIMP_CONFIG_DIR / "base_style.json"

THEMES_DIR = PIMP_CONFIG_DIR / "themes"
STYLES_DIR = PIMP_CONFIG_DIR / "styles"
PALETTES_DIR = PIMP_CONFIG_DIR / "palettes"
PALETTE_GENERATORS_DIR = PIMP_CONFIG_DIR / "palette_generators"
MODULES_DIR = PIMP_CONFIG_DIR / "modules"
JSON_SCHEMA_DIR = PIMP_CONFIG_DIR / ".json_schemas"

# Runtime
CORE_PID_FILE = PIMP_RUNTIME_DIR / "core.pid"
SERVER_PID_FILE = PIMP_RUNTIME_DIR / "server.pid"

# Cache / logs
LOG_FILE = PIMP_CACHE_DIR / "pimpmyrice.log"

# Remote repos
REPOS_DIR = PIMP_CONFIG_DIR / "remote_repos"
REPOS_LIST = REPOS_DIR / "list.txt"


REPOS_BASE_ADDR = "https://github.com/pimpmyrice-modules"
