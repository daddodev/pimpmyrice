"""
Theme and module migration utilities for upgrading old syntax to new format.

Theme Migration (pre-0.5.0 -> 0.5.0+):
- $variable_name → {{variable_name}}

Module Migration (pre-0.5.0 -> 0.5.0+):
- init → on_events.module_install
- pre_run → on_events.before_theme_apply
- run → on_events.theme_apply
- commands → scripts (actions wrapped in lists)
"""

from pimpmyrice.migrations.module_migrations import migrate_module_dict
from pimpmyrice.migrations.theme_migrations import (
    migrate_style_dict,
    migrate_theme_dict,
)

__all__ = [
    "migrate_theme_dict",
    "migrate_style_dict",
    "migrate_module_dict",
]
