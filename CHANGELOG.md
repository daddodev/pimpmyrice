# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.4.3] - 2025-08-15

### Added

- Added `copr_publish` to release workflow for Fedora COPR repository
- Added `workflow_dispatch` trigger to release actions

### Changed

- Refactored `Color` class with improved parsing and new `_parse_rgb_tuple` method
- Changed `utils.Timer.elapsed` to a property
- Enhanced `FileAction` to allow Jinja2 imports from file system
- Moved GitHub Actions from `test.yaml` to `push.yaml` with separate job steps

### Fixed

- Fixed CLI minor issues

## [0.4.2] - 2025-08-02

### Added

- Added `.rpm` packages to GitHub releases for Fedora/RHEL support
- Added `ppa_publish.sh` script for Ubuntu PPA automation
- Added PyInstaller spec for building standalone binaries
- Added Windows installer (Inno Setup) to release workflow
- Added `module install` CLI command
- Added `--out` option to `module clone` command

### Changed

- Refactored `module init` command
- Enhanced template variable parsing with `PIMP_CONFIG_DIR` in context
- Refactored theme management to support asynchronous theme deletion
- Added event publishing on theme changes and base style saves
- Changed logger usage instead of print for help messages
- Re-added OS check on module initialization

### Fixed

- Fixed Ubuntu PPA upload issues
- Fixed PPA upload issues in GitHub Actions
- Fixed various GitHub Actions workflow issues

## [0.4.0] - 2025-04-15

### Added

- Migrated from `setup.py` to `pyproject.toml` for modern Python packaging
- Added `flake.nix` for Nix development environment
- Added AUR (Arch User Repository) publish to release workflow
- Added `.deb` packages to GitHub releases
- Added PPA publish to release workflow
- Added `pylsp` (Python LSP) to dev dependencies
- Added thumbnail generation using Pillow
- Added `@cache` decorator to `extract_colors` for performance
- Added `returncode` to `run_shell_command` output
- Added `create module` CLI command
- Added type annotations throughout codebase

### Changed

- Refactored palette generation algorithm
- Refactored `Color` class: added `.adjust` method, removed `.alt` and `.maxsat`
- Changed style JSON template syntax from `$var` to Jinja2 `{{var}}` format
- Refactored logging system with improved error handling
- Removed `Result` type in favor of direct error handling
- Moved default base style to `assets/default_base_style.json`
- Switched from scikit-learn & OpenCV to numpy & Pillow for color extraction
- Switched from pylint and black to ruff for linting and formatting
- Moved non-essential palette keywords to style configuration
- Updated dependencies in PKGBUILD

### Fixed

- Fixed mypy type checking errors
- Fixed color generation issues
- Fixed release workflow configuration
- Fixed false pylint errors
- Fixed file permissions (set to 644)
- Fixed various import and formatting issues

### Removed

- Removed `colour` dependency
- Removed unused imports and arguments
- Removed pydantic-extra-types dependency

## [0.3.2] - 2024-12-14

### Added

- Added Discord link to README
- Added installed fonts to editor hints and schema
- Added cursor to default keywords

### Changed

- Changed font keywords structure

### Fixed

- Fixed cloning module from local path

## [0.3.1] - 2024-12-09

### Added

- Added AUR install instructions to README
- Added error message if server package not found
- Added `__version__` attribute to package

### Changed

- Refactored for Python 3.10 compatibility
- Removed `infi.docopt_completion` dependency (to be refactored)

### Fixed

- Fixed various minor issues

## [0.3.0] - 2024-12-06

### Added

- Added basic theme export functionality (WIP)

### Changed

- Changed config directory on Linux to `~/.config/pimpmyrice` (via `PIMP_CONFIG_DIR`)
- Updated zsh suggestions

## [0.2.2] - 2024-12-06

### Changed

- Updated zsh shell suggestions
- Changed required Python version to 3.10

## [0.2.1] - 2024-12-04

### Fixed

- Fixed CLI generation issues
- Fixed video embed in README

## [0.2.0] - 2024-12-04

### Added

- Added `WaitForAction` for conditional delays
- Added `ShellAction.detached` for background process execution
- Added CLI commands for adding/removing theme tags (`pimp theme add-tags/remove-tags`)
- Added zsh shell completions with suggestions for `THEME`, `MODULE`, and `--tags`
- Added isort to GitHub workflow with black profile
- Added mypy and black to test action
- Added `py.typed` marker for PEP 561 compliance
- Added module reinitialization CLI command (`pimp module reinit`)
- Added theme export functionality (initial)

### Changed

- Moved `mypy.ini` and `pytest.ini` to `pyproject.toml`
- Changed `--include-modules` flag to `--modules`
- Changed `--include-tags` flag to `--tags` / `-t`
- Refactored `IfRunningAction` to have `should_be_running` default to `true`
- Refactored `clone module` command to accept list of modules
- Refactored theme and module parsing with Pydantic models
- Changed to always use long hex format for colors
- Updated GitHub Actions versions
- Changed config file path structure
- Changed CLI entrypoint from "rice" back to "pimp"

### Fixed

- Fixed `Result` missing name after `__add__` operation
- Fixed shell file autocomplete
- Fixed color generation issues
- Fixed circular import in CLI
- Fixed theme rewrite functionality
- Fixed JSON encoding errors on Windows paths
- Fixed module OS parsing
- Fixed git clone on Windows

### Removed

- Removed empty or default values from theme.json dump
- Removed infi.docopt_completion print statements
- Removed `Style` class (refactored)
- Removed `albums` feature
- Removed old `demo.gif`

## [0.1.0] - 2024-11-16

### Added

- Initial stable release with core functionality
- Added theme management system with modes (dark/light)
- Added module system with action pipelines
- Added CLI with docopt argument parsing
- Added zsh shell completions
- Added file watchers for themes and modules
- Added websocket server support (moved to separate package)
- Added `--print-theme-dict` CLI option
- Added tags support for theme categorization
- Added server stop/reload commands
- Added GitHub workflow for CI/CD

### Changed

- Changed config directory structure
- Changed template file extension from `.base` to `.j2`
- Changed template directory from "files" to "templates"
- Refactored `IfAction` logic
- Changed `FileAction` template to string with variable parsing

### Fixed

- Fixed module command execution
- Fixed `Style` dump functionality
- Fixed JSON decoding errors on Windows
- Fixed various minor bugs

### Removed

- Removed unused `global_style`
- Removed PKGBUILD (moved to separate repo)

## [0.0.1] - 2024-11-16

### Added

- First public commit
- Initial project structure and core files
- Basic theme management functionality
- Module execution system
- CLI interface
- Initial documentation and README

[0.4.3]: https://github.com/daddodev/pimpmyrice/compare/0.4.2...0.4.3
[0.4.2]: https://github.com/daddodev/pimpmyrice/compare/0.4.1...0.4.2
[0.4.1]: https://github.com/daddodev/pimpmyrice/compare/0.4.0...0.4.1
[0.4.0]: https://github.com/daddodev/pimpmyrice/compare/0.3.2...0.4.0
[0.3.2]: https://github.com/daddodev/pimpmyrice/compare/0.3.1...0.3.2
[0.3.1]: https://github.com/daddodev/pimpmyrice/compare/0.3.0...0.3.1
[0.3.0]: https://github.com/daddodev/pimpmyrice/compare/0.2.2...0.3.0
[0.2.2]: https://github.com/daddodev/pimpmyrice/compare/0.2.1...0.2.2
[0.2.1]: https://github.com/daddodev/pimpmyrice/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/daddodev/pimpmyrice/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/daddodev/pimpmyrice/compare/0.0.1...0.1.0
[0.0.1]: https://github.com/daddodev/pimpmyrice/releases/tag/0.0.1
