"""
Theme migration utilities for upgrading old $var syntax to {{var}} syntax.

Migration from pre-0.5.0 to 0.5.0+:
- $variable_name → {{variable_name}}
- $color.primary → {{color.primary}}
"""

import logging
import re
from typing import Any

log = logging.getLogger(__name__)


def _has_old_syntax(data: dict[str, Any]) -> bool:
    """Check if data contains $var references (not {{...}})."""
    old_ref_pattern = re.compile(r"\$[a-zA-Z_][a-zA-Z0-9_]*")

    def contains_old_ref(value: Any) -> bool:
        if isinstance(value, str):
            if "{{" in value and "}}" in value:
                return False
            return bool(old_ref_pattern.search(value))
        elif isinstance(value, dict):
            return any(contains_old_ref(v) for v in value.values())
        elif isinstance(value, list):
            return any(contains_old_ref(v) for v in value)
        return False

    return contains_old_ref(data)


def _convert_refs_recursively(value: Any) -> Any:
    """Convert $var references to {{var}} in values."""
    if isinstance(value, str):
        if "{{" in value and "}}" in value:
            return value
        return re.sub(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", r"{{\1}}", value)
    elif isinstance(value, dict):
        return {k: _convert_refs_recursively(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_convert_refs_recursively(item) for item in value]
    return value


def migrate_theme_dict(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Migrate theme data from $var to {{var}} syntax.

    Returns migrated data if old syntax detected, None if already current.

    Args:
        data: Theme data with possible $var syntax.

    Returns:
        Migrated dict or None if no migration needed.
    """
    if not _has_old_syntax(data):
        return None

    migrated: dict[str, Any] = {}
    for key, value in data.items():
        if key == "modes":
            migrated[key] = {}
            for mode_name, mode_data in value.items():
                if isinstance(mode_data, dict):
                    migrated[key][mode_name] = {
                        k: _convert_refs_recursively(v) for k, v in mode_data.items()
                    }
                else:
                    migrated[key][mode_name] = mode_data
        else:
            migrated[key] = _convert_refs_recursively(value)
    return migrated


def migrate_style_dict(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Migrate style data from $var to {{var}} syntax.

    Returns migrated data if old syntax detected, None if already current.

    Args:
        data: Style data with possible $var syntax.

    Returns:
        Migrated dict or None if no migration needed.
    """
    if not _has_old_syntax(data):
        return None

    migrated: dict[str, Any] = {}
    for key, value in data.items():
        migrated[key] = _convert_refs_recursively(value)
    return migrated
