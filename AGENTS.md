# PimpMyRice Agent Guidelines

> PimpMyRice: The overkill theme manager - A Python CLI tool for managing themes, styles, palettes, and modules for system customization.

## Build/Test/Lint Commands

```bash
# Install dependencies and setup (uses uv)
uv sync --dev
uv pip install -e .

# Run all tests
pytest

# Run a single test
pytest tests/test_theme.py::test_install_module -v

# Run tests matching pattern
pytest -k test_gen

# Linting (check only)
ruff check src/pimpmyrice

# Linting (with auto-fix)
ruff check --fix src/pimpmyrice

# Format code
ruff format src/pimpmyrice

# Type checking (strict mode enabled)
mypy src/pimpmyrice

# Import sorting
isort src/pimpmyrice
```

## Main Components

### Theme System (`theme.py`, `theme_utils.py`)
- **ThemeManager**: Central orchestrator managing themes, styles, palettes, and module execution
- **Theme**: Pydantic model representing a theme with modes (dark/light), wallpapers, and tags
- **Mode**: Contains style configuration for dark/light variants
- **ThemeConfig**: User configuration (current theme, mode selection)
- **Style**: Dictionary of color values and module-specific settings
- Themes support multiple modes, tags for categorization, and per-mode wallpapers

### Module System (`module.py`, `module_utils.py`)
- **ModuleManager**: Discovers, loads, and executes modules from `~/.config/pimpmyrice/modules/`
- **Module**: Pydantic model with metadata and action pipelines (pre-run, run)
- **Actions**:
  - `ShellAction`: Execute shell commands
  - `FileAction`: Template rendering to files
  - `PythonAction`: Execute Python code
  - `IfRunningAction`: Conditional execution based on process checks
  - `LinkAction`: Create symlinks
  - `AppendAction`: Append to files
  - `WaitForAction`: Wait for conditions
- **OnEvents**: Lifecycle hooks for module execution:
  - `module_install`: Run once when module is installed (LinkAction, AppendAction)
  - `before_theme_apply`: Pre-processing actions before theme is applied
  - `theme_apply`: Main theme application actions
  - `after_theme_apply`: Post-processing actions after theme is applied
  - `theme_applied`: Actions triggered when any theme is applied
  - `themes_changed`: Actions triggered when themes list changes
- **ModuleState**: Tracks action pipeline execution state (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
- Modules are loaded from `module.yaml` or `module.json` files
- Auto-migration from pre-0.5.0 module format (init/pre_run/run/commands → on_events)

### Color System (`colors.py`)
- **Color**: Core class supporting hex, rgb, rgba, hsl, hsv formats with conversion methods
- **Palette**: Collection of colors (primary, secondary, background, foreground, accent)
- **GlobalPalette**: Extended palette with terminal color mappings
- **Palette Generators**: Algorithmic palette generation from images (dark/light variants in `palette_generators/`)

### Configuration (`config_paths.py`)
- Cross-platform config directory management (Linux XDG, Windows %APPDATA%, macOS Library)
- **PIMP_TESTING** env var switches config to `./tests/files` for isolation
- Key paths:
  - `PIMP_CONFIG_DIR`: `~/.config/pimpmyrice/`
  - `PIMP_CACHE_DIR`: Platform cache directory
  - `THEMES_DIR`: `themes/` subdirectory
  - `STYLES_DIR`: `styles/` subdirectory
  - `MODULES_DIR`: `modules/` subdirectory
  - `PALETTES_DIR`: `palettes/` subdirectory
  - `TEMP_DOWNLOADS_DIR`: Cache downloads directory
  - `THUMBNAILS_DIR`: Thumbnails cache directory

### Template System (`template.py`)
- **Jinja2** integration with strict undefined checking
- `process_template()`: Render template strings
- `render_template_file()`: Render template files with search paths
- `process_keyword_template()`: Evaluate single Jinja2 expressions
- `parse_string_vars()`: Expand variables and user paths (`{{home_dir}}`, `{{module_dir}}`, etc.)

#### Template Variables Available

Templates use Jinja2 syntax: `{{variable_name}}`

**Global Variables (always available):**
- `{{home_dir}}` - User's home directory
- `{{config_dir}}` - OS config directory
- `{{pimp_config_dir}}` - PimpMyRice config directory (~/.config/pimpmyrice/)

**Module Variables (when module_name is provided):**
- `{{module_dir}}` - Path to the module directory
- `{{templates_dir}}` - Path to module's templates subdirectory
- `{{files_dir}}` - Path to module's files subdirectory

**Theme Variables (in theme_dict):**
- `{{theme_name}}` - Name of the current theme
- `{{mode}}` - Current mode (dark/light)
- `{{wallpaper.path}}` - Path to wallpaper image
- `{{wallpaper.mode}}` - Wallpaper display mode
- `{{primary}}`, `{{secondary}}`, `{{background}}`, `{{foreground}}`, `{{accent}}` - Core palette colors
- All terminal colors: `{{color0}}` through `{{color15}}`
- Any custom values from styles

**Template Resolution Flow:**
1. Actions receive a `theme_dict` (AttrDict) containing theme data
2. `parse_string_vars()` merges global paths + module paths + theme_dict
3. Jinja2 processes templates with strict undefined checking
4. Result is returned as a string

**Example Usage:**
```yaml
# In module.yaml run actions
run:
  - action: shell
    command: 'wal -i "{{wallpaper.path}}"'
  - action: file
    target: "{{config_dir}}/alacritty/alacritty.toml"
    template: alacritty.toml.j2

# Template file (alacritty.toml.j2) can use:
# background = "{{background}}"
# foreground = "{{foreground}}"
# colors.primary.background = "{{primary}}"
```

**Event Handler Templates:**
For `on_events`, the same template system applies:
```yaml
on_events:
  theme_applied:
    - action: shell
      command: 'notify-send "Theme: {{theme_name}} ({{mode}})"'
  themes_changed:
    - action: shell
      command: 'echo "Theme {{theme_name}} was {{action}}"'
```

### Files & I/O (`files.py`)
- `load_yaml()` / `save_yaml()`: YAML with automatic schema headers
- `load_json()` / `save_json()`: JSON with `$schema` embedding
- `import_image()`: Copy images to theme directories
- `download_file()`: HTTP downloads with extension detection
- `create_config_dirs()`: Ensure all config directories exist
- Auto-migration from old theme format (`$var` → `{{var}}`) when loading

### Migrations (`migrations/`)
- **theme_migrations.py**: Auto-migrate themes from `$variable` to `{{variable}}` Jinja2 syntax
- **module_migrations.py**: Auto-migrate modules from old structure to `on_events` structure:
  - `init` → `on_events.module_install`
  - `pre_run` → `on_events.before_theme_apply`
  - `run` → `on_events.theme_apply`
  - `commands` → `scripts` (actions wrapped in lists)

### CLI & Args (`cli.py`, `args.py`, `doc.py`)
- **docopt** for CLI parsing with comprehensive help in `doc.py`
- `cli()`: Entry point that checks for server and proxies commands
- `process_args()`: Route commands to appropriate ThemeManager methods
- Supports local execution or proxy to running server for better performance

### Logging (`logger.py`)
- **Rich** integration for colorful terminal output
- **ContextVar** support for request IDs and module context
- `module_context_wrapper()`: Inject module name into log records
- Custom formatters and filters for structured logging

### Events (`events.py`)
- **EventHandler**: Pub/sub pattern for theme application events
- Used to trigger schema regeneration and shell completions

### Schemas (`schemas.py`)
- Generate JSON schemas for themes and modules
- Dynamic Pydantic model creation from example data
- Font enumeration for autocompletion in schemas

### Utilities (`utils.py`)
- **Timer**: Performance timing with elapsed tracking
- **AttrDict**: Dictionary with attribute access
- **Lock**: File-based locking for process coordination
- `is_process_running()`: Cross-platform process detection

## Code Style Guidelines

### Type Hints
- Use strict type hints everywhere (mypy strict mode is enabled)
- Use `from __future__ import annotations` in modules with forward references
- Use `TYPE_CHECKING` imports for circular dependencies
- Explicitly type function parameters and return values
- Use Pydantic `BaseModel` for data validation and serialization

### Imports
- Use absolute imports from `pimpmyrice` package
- Group imports: stdlib, third-party, local
- Use `TYPE_CHECKING` block to avoid circular imports:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager
```

### Formatting
- Line length: 88 characters (Ruff default)
- Use double quotes for strings
- 4-space indentation
- Use Ruff for both linting and formatting
- Follow isort "black" profile

### Naming Conventions
- Classes: `PascalCase` (e.g., `ThemeManager`, `BaseModel`)
- Functions/variables: `snake_case` (e.g., `load_module`, `theme_dir`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `CONFIG_FILE`, `BASE_STYLE_FILE`)
- Private: prefix with underscore (e.g., `_internal_func`)

### Docstrings
- Use Google-style docstrings with Args and Returns sections
- Include type info in docstrings when helpful
- Keep first line as a concise summary

```python
def load_yaml(file: Path) -> dict[str, Any]:
    """
    Load a YAML file into a dict.

    Args:
        file (Path): Path to YAML file.

    Returns:
        dict[str, Any]: Parsed data.
    """
```

### Error Handling
- Use custom exceptions from `pimpmyrice/exceptions.py`:
  - `IfCheckFailed`: Conditional check not satisfied
  - `ReferenceNotFound`: Jinja2 variable not resolved
- Log exceptions with `log.exception(e)` for full traceback
- Log errors with `log.error(f"message: {e}")` for user-facing errors
- Use `try/except` blocks that catch specific exceptions

### Logging
- Use module-level logger: `log = logging.getLogger(__name__)`
- Use appropriate log levels: debug, info, warning, error
- Use Rich logging handler for CLI output
- Log debug messages with timing info when relevant

### Architecture Patterns
- Manager classes orchestrate functionality (ThemeManager, ModuleManager)
- Pydantic models for all data structures with validation
- Async/await for I/O operations
- `pathlib.Path` for all filesystem operations
- Use `Timer` utility for performance logging

### Testing
- Use pytest with pytest-asyncio for async tests
- Mark async tests with `@pytest.mark.asyncio(scope="session")`
- Use fixtures for dependency injection
- Set `os.environ["PIMP_TESTING"] = "True"` in tests
- Clean up test files in fixtures

## Project Structure

```
src/pimpmyrice/
  __init__.py          # Version, logging setup
  __main__.py          # CLI entrypoint
  cli.py               # CLI argument parsing, server proxy
  args.py              # Command routing
  doc.py               # Help documentation
  theme.py             # ThemeManager class
  theme_utils.py       # Theme/Mode/Style models
  module.py            # ModuleManager class
  module_utils.py      # Module models and actions
  colors.py            # Color class, palettes
  palette_generators/  # Algorithmic palette generation
  migrations/          # Theme/module migration utilities
    __init__.py        # Migration exports
    theme_migrations.py  # Theme syntax migration
    module_migrations.py # Module structure migration
  template.py          # Jinja2 template processing
  files.py             # File I/O utilities
  config_paths.py      # Configuration directory paths
  schemas.py           # JSON schema generation
  logger.py            # Rich logging setup
  events.py            # Event pub/sub
  utils.py             # Timer, AttrDict, Lock
  exceptions.py        # Custom exceptions
  parsers.py           # Parsing utilities
  completions.py       # Shell completion generation
  color_extract.py     # Image color extraction
  edit_args.py         # Edit command processing
  assets/              # Default styles and files

tests/                 # Test files
pyproject.toml         # Project configuration
flake.nix             # Nix development shell
```

## Key Dependencies

- **pydantic**: Data validation and serialization
- **rich**: Terminal formatting and logging
- **jinja2**: Template processing
- **pyyaml**: YAML parsing
- **docopt**: CLI argument parsing
- **pillow/numpy**: Image processing and color extraction
- **requests**: HTTP downloads and server communication
- **psutil**: Process detection

## Module Development

Modules are directories in `~/.config/pimpmyrice/modules/` containing:
- `module.yaml` or `module.json`: Module manifest
- `templates/`: Jinja2 template files
- `files/`: Static files to copy
- Actions define how to apply themes to applications

## Workflow Checklist

When making changes:
1. Ensure code passes `ruff check` and `ruff format`
2. Run `mypy src/pimpmyrice` for type checking
3. Run `pytest` to verify tests pass
4. Test locally: `pimp random`
5. Use Nix flake for reproducible dev environment (optional)
