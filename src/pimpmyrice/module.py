from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pimpmyrice import module_utils as mutils
from pimpmyrice.config_paths import CORE_PID_FILE, MODULES_DIR, REPOS_BASE_ADDR
from pimpmyrice.files import save_yaml
from pimpmyrice.module_utils import (
    FileAction,
    IfRunningAction,
    Module,
    ModuleState,
    OnEvents,
    PythonAction,
    ShellAction,
    module_context_wrapper,
)
from pimpmyrice.parsers import clean_module_dump, parse_module
from pimpmyrice.utils import AttrDict, Lock, Timer, is_locked

if TYPE_CHECKING:
    from pimpmyrice.theme_manager import ThemeManager

log = logging.getLogger(__name__)


class ModuleManager:
    """
    Manage discovery, lifecycle, and execution of modules.

    Loads modules from disk, runs their lifecycle actions, and provides
    helpers for install, clone, init, rewrite, and deletion.
    """

    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.load_modules()

    def load_modules(self) -> None:
        """
        Load all modules present in `MODULES_DIR`.

        Returns:
            None
        """
        timer = Timer()

        for module_dir in MODULES_DIR.iterdir():
            if not module_dir.is_dir() or not (
                (module_dir / "module.yaml").exists()
                or (module_dir / "module.json").exists()
            ):
                continue
            try:
                self.load_module(module_dir)
            except Exception as e:
                log.debug("exception:", exc_info=e)
                log.error(f'error loading module "{module_dir.name}": {e}')

        log.debug(f"{len(self.modules)} modules loaded in {timer.elapsed:.4f} sec")

    def load_module(self, module_dir: Path) -> None:
        """
        Load a single module from a directory.

        Args:
            module_dir (Path): Path containing a module manifest.

        Returns:
            None
        """
        module = parse_module(module_dir)

        self.modules[module.name] = module
        log.debug(f'module "{module.name}" loaded')

    async def run_modules(
        self,
        theme_dict: AttrDict,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        out_dir: Path | None = None,
    ) -> dict[str, ModuleState]:
        """
        Run lifecycle actions for eligible modules.

        Execution flow:
        1. before_theme_apply: sequential execution, can transform theme_dict
        2. theme_apply: parallel execution, main theming actions
        3. after_theme_apply: runs after theme_apply completes

        Args:
            theme_dict (AttrDict): Generated theme dictionary.
            include_modules (list[str] | None): Allowlist of module names.
            exclude_modules (list[str] | None): Denylist of module names.
            out_dir (Path | None): Optional output directory for exports.

        Returns:
            dict[str, ModuleState]: Final state of each module.
        """
        if is_locked(CORE_PID_FILE)[0]:
            raise Exception("another instance is applying a theme!")

        with Lock(CORE_PID_FILE):
            timer = Timer()

            for m in [*(include_modules or []), *(exclude_modules or [])]:
                if m not in self.modules:
                    raise Exception(f'module "{m}" not found')

            modules_state: dict[str, ModuleState] = {}
            before_runners = []
            theme_runners = []
            after_runners = []

            for module_name, module in self.modules.items():
                if (
                    (include_modules and module_name not in include_modules)
                    or (exclude_modules and module_name in exclude_modules)
                    or not module.enabled
                ):
                    modules_state[module_name] = ModuleState.SKIPPED
                    continue

                # Check if module has any lifecycle actions
                has_actions = (
                    module.on_events.before_theme_apply
                    or module.on_events.theme_apply
                    or module.on_events.after_theme_apply
                )
                if not has_actions:
                    modules_state[module_name] = ModuleState.SKIPPED
                    continue

                modules_state[module_name] = ModuleState.PENDING

                if module.on_events.before_theme_apply:
                    before_runners.append(module_name)
                if module.on_events.theme_apply:
                    theme_runners.append(module_name)
                if module.on_events.after_theme_apply:
                    after_runners.append(module_name)

            if (
                len(theme_runners) == 0
                and len(before_runners) == 0
                and len(after_runners) == 0
            ):
                raise Exception(
                    f"no modules to run!\nSee {REPOS_BASE_ADDR} for available modules"
                )

            # Stage 1: before_theme_apply (sequential, transforms theme_dict)
            log.debug(f"running before_theme_apply for {len(before_runners)} modules")
            for name in before_runners:
                mod_res = await module_context_wrapper(
                    name,
                    modules_state,
                    self.modules[name].execute_before_theme_apply(deepcopy(theme_dict)),
                )
                if mod_res and isinstance(mod_res, AttrDict):
                    theme_dict = mod_res

                modules_state[name] = (
                    ModuleState.RUNNING
                    if self.modules[name].on_events.theme_apply
                    or self.modules[name].on_events.after_theme_apply
                    else ModuleState.COMPLETED
                )

            # Stage 2: theme_apply (parallel)
            log.debug(f"running theme_apply for {len(theme_runners)} modules")
            theme_tasks = [
                module_context_wrapper(
                    name,
                    modules_state,
                    self.modules[name].execute_theme_apply(
                        theme_dict, modules_state=modules_state, out_dir=out_dir
                    ),
                )
                for name in theme_runners
            ]

            for t in asyncio.as_completed(theme_tasks):
                try:
                    await t
                except Exception as e:
                    log.debug("exception:", exc_info=e)
                    log.error(str(e))

            # Stage 3: after_theme_apply (sequential after theme_apply)
            log.debug(f"running after_theme_apply for {len(after_runners)} modules")
            for name in after_runners:
                await module_context_wrapper(
                    name,
                    modules_state,
                    self.modules[name].execute_after_theme_apply(
                        theme_dict, modules_state=modules_state
                    ),
                )

            # Final state accounting
            completed = skipped = failed = 0
            for state in modules_state.values():
                match state:
                    case ModuleState.COMPLETED:
                        completed += 1
                    case ModuleState.SKIPPED:
                        skipped += 1
                    case ModuleState.FAILED:
                        failed += 1

            log.info(
                f"{len(self.modules)} modules finished in {timer.elapsed:.2f} sec: "
                f"{completed} completed, {skipped} skipped, {failed} failed"
            )

            for name, state in modules_state.items():
                log.debug(f"{name}: {state.name}")

            return modules_state

    async def run_module_script(
        self,
        tm: ThemeManager,
        module_name: str,
        script: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Execute a custom script exposed by a module.

        Args:
            tm (ThemeManager): Theme manager instance.
            module_name (str): Target module.
            script (str): Script name.
            *args (Any): Positional arguments passed to the script.
            **kwargs (Any): Keyword arguments passed to the script.

        Returns:
            None
        """
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]
        await module.execute_script(script, tm, *args, **kwargs)

    async def rewrite_modules(
        self,
        name_includes: str | None = None,
    ) -> None:
        """
        Rewrite module manifests from in-memory state.

        Args:
            name_includes (str | None): Restrict to modules whose name contains
                this substring. Defaults to None.

        Returns:
            None
        """
        for module in self.modules.values():
            if name_includes and name_includes not in module.name:
                continue

            dump = module.model_dump(mode="json")
            dump = clean_module_dump(dump)

            save_yaml(MODULES_DIR / module.name / "module.yaml", dump)
            log.info(f'module "{module.name}" rewritten')

    async def create_module(self, module_name: str) -> None:
        """
        Scaffold a new module with example actions and files.

        Args:
            module_name (str): New module name.

        Returns:
            None
        """
        # TODO add --bare; README, LICENSE

        log.debug(f'creating module "{module_name}"')

        if module_name in self.modules:
            raise Exception(f'module "{module_name}" already present')

        module = Module(
            name=module_name,
            enabled=False,
            on_events=OnEvents(
                theme_apply=[
                    IfRunningAction(
                        module_name=module_name,
                        program_name="someprogram",
                    ),
                    FileAction(
                        module_name=module_name,
                        target="{{module_dir}}/example_output/config",
                    ),
                    ShellAction(
                        module_name=module_name,
                        command="somecommand",
                    ),
                    PythonAction(
                        module_name=module_name,
                        py_file_path="apply.py",
                        function_name="main",
                    ),
                ]
            ),
        )
        module_path = MODULES_DIR / module.name

        module_path.mkdir()
        (module_path / "templates").mkdir()
        (module_path / "files").mkdir()

        dump = module.model_dump(mode="json")
        dump = clean_module_dump(dump)
        save_yaml(module_path / "module.yaml", dump)

        with open(module_path / "apply.py", "w", encoding="utf-8") as f:
            f.write(
                """async def main(theme_dict):
    print(theme_dict.wallpaper.path)
    print(theme_dict["wallpaper"].path)
    print(theme_dict)"""
            )

        self.load_module(module_path)
        await self.modules[module_name].execute_init()
        log.info(f'module "{module_name}" created')

    async def install_module(self, source: str) -> str:
        """
        Install a module from a source (repo, folder, or short name).

        Args:
            source (str): Git URL, local path, or repo short name.

        Returns:
            str: Installed module name.
        """
        name = await self.clone_module(source)

        await self.modules[name].execute_init()

        log.info(f'module "{name}" installed')
        return name

    async def clone_module(self, source: str, out_dir: str | Path = MODULES_DIR) -> str:
        """
        Clone a module from git or local folder.

        Args:
            source (str): Git URL, local path, or repo short name.
            out_dir (str | Path): Destination directory. Defaults to `MODULES_DIR`.

        Returns:
            str: Cloned module name.
        """
        out_dir = Path(out_dir) if out_dir else MODULES_DIR

        if source.startswith(("git@", "http://", "https://")):
            name = await mutils.clone_from_git(source, out_dir)
        elif Path(source).is_absolute() or source.startswith("."):
            name = await mutils.clone_from_folder(Path(source), out_dir)
        else:
            url = f"{REPOS_BASE_ADDR}/{source}"
            name = await mutils.clone_from_git(url, out_dir)

        log.info(f'module "{name}" cloned')

        if out_dir == MODULES_DIR:
            module = parse_module(MODULES_DIR / name)
            self.modules[name] = module

        return name

    async def init_module(self, module_name: str) -> None:
        """
        Run the module initialization routine.

        Args:
            module_name (str): Module to initialize.

        Returns:
            None
        """
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]
        await module.execute_init()

    async def delete_module(self, module_name: str) -> None:
        """
        Delete a module from disk and registry.

        Args:
            module_name (str): Module to delete.

        Returns:
            None
        """
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]

        await mutils.delete_module(module)
        self.modules.pop(module_name)

        log.info(f'module "{module_name}" deleted')

    async def set_enabled(self, module_name: str, enabled: bool) -> None:
        """
        Set a module's enabled status and persist the change.

        Args:
            module_name (str): Module to modify.
            enabled (bool): New enabled status.

        Returns:
            None
        """
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]
        if module.enabled == enabled:
            status = "enabled" if enabled else "disabled"
            log.info(f'module "{module_name}" is already {status}')
            return

        module.enabled = enabled
        dump = module.model_dump(mode="json")
        dump = clean_module_dump(dump)
        save_yaml(MODULES_DIR / module.name / "module.yaml", dump)
        status = "enabled" if enabled else "disabled"
        log.info(f'module "{module_name}" {status}')

    async def list_modules(self) -> None:
        """
        Log registered modules with enabled/disabled status.

        Returns:
            None
        """
        for module_name, module in self.modules.items():
            status = "enabled" if module.enabled else "disabled"
            log.info(f"{module_name} ({status})")
