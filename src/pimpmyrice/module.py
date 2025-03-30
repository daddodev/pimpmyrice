from __future__ import annotations

import asyncio
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pimpmyrice import module_utils as mutils
from pimpmyrice.config_paths import LOCK_FILE, MODULES_DIR, REPOS_BASE_ADDR
from pimpmyrice.files import save_yaml
from pimpmyrice.module_utils import (
    FileAction,
    IfRunningAction,
    Module,
    ModuleState,
    PythonAction,
    ShellAction,
    module_context_wrapper,
)
from pimpmyrice.parsers import parse_module
from pimpmyrice.template import parse_string_vars
from pimpmyrice.utils import AttrDict, Lock, Timer, is_locked

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


class ModuleManager:
    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.load_modules()

    def load_modules(self) -> None:
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

        log.debug(f"{len(self.modules)} modules loaded in {timer.elapsed():.4f} sec")

    def load_module(self, module_dir: Path) -> None:
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
        # TODO separate modules by type (run, pre_run, palette_generators...)

        if is_locked(LOCK_FILE)[0]:
            raise Exception("another instance is applying a theme!")

        with Lock(LOCK_FILE):
            timer = Timer()

            for m in [*(include_modules or []), *(exclude_modules or [])]:
                if m not in self.modules:
                    raise Exception(f'module "{m}" not found')

            modules_state: dict[str, ModuleState] = {}
            pre_runners = []
            runners = []

            for module_name, module in self.modules.items():
                if (
                    (include_modules and module_name not in include_modules)
                    or (exclude_modules and module_name in exclude_modules)
                    or not module.enabled
                    or not (module.pre_run or module.run)
                ):
                    modules_state[module_name] = ModuleState.SKIPPED
                    continue

                modules_state[module_name] = ModuleState.PENDING

                if module.pre_run:
                    pre_runners.append(module_name)
                if module.run:
                    runners.append(module_name)

            if len(runners) == 0:
                raise Exception(
                    f"no modules to run!\nSee {REPOS_BASE_ADDR} for available modules"
                )

            for name in pre_runners:
                mod_res = await module_context_wrapper(
                    name,
                    modules_state,
                    self.modules[name].execute_pre_run(deepcopy(theme_dict)),
                )
                if not mod_res:
                    continue

                theme_dict = mod_res

                modules_state[name] = (
                    ModuleState.RUNNING
                    if self.modules[name].run
                    else ModuleState.COMPLETED
                )

            runners_tasks = [
                module_context_wrapper(
                    name,
                    modules_state,
                    self.modules[name].execute_run(
                        theme_dict, modules_state=modules_state, out_dir=out_dir
                    ),
                )
                for name in runners
            ]

            for t in asyncio.as_completed(runners_tasks):
                try:
                    await t
                except Exception as e:
                    log.debug("exception:", exc_info=e)
                    log.error(str(e))

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
                f"{len(self.modules)} modules finished in {timer.elapsed():.2f} sec: "
                f"{completed} completed, {skipped} skipped, {failed} failed"
            )

            for name, state in modules_state.items():
                log.debug(f"{name}: {state.name}")

            return modules_state

    async def run_module_command(
        self,
        tm: ThemeManager,
        module_name: str,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]
        await module.execute_command(command, tm, *args, **kwargs)

    async def rewrite_modules(
        self,
        name_includes: str | None = None,
    ) -> None:
        for module in self.modules.values():
            if name_includes and name_includes not in module.name:
                continue

            dump = module.model_dump(mode="json")

            save_yaml(MODULES_DIR / module.name / "module.yaml", dump)
            # save_json(MODULES_DIR / module.name / "module.json", dump)
            log.info(f'module "{module.name}" rewritten')

    async def init_module(self, module_name: str) -> None:
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]
        await module.execute_init()

    async def create_module(self, module_name: str) -> None:
        # TODO add --bare; README, LICENSE

        log.debug(f'creating module "{module_name}"')

        if module_name in self.modules:
            raise Exception(f'module "{module_name}" already present')

        module = Module(
            name=module_name,
            enabled=False,
            run=[
                IfRunningAction(module_name=module_name, program_name="someprogram"),
                FileAction(
                    module_name=module_name, target="{{config_dir}}/someprogram/config"
                ),
                ShellAction(module_name=module_name, command="somecommand"),
                PythonAction(
                    module_name=module_name,
                    py_file_path="apply.py",
                    function_name="main",
                ),
            ],
        )
        module_path = MODULES_DIR / module.name

        module_path.mkdir()
        (module_path / "templates").mkdir()
        (module_path / "files").mkdir()

        dump = module.model_dump(mode="json")
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

    async def clone_module(self, source: str | list[str]) -> None:
        sources = source if isinstance(source, list) else [source]

        for source in sources:
            source = str(source)

            if source.startswith(("git@", "http://", "https://")):
                name = await mutils.clone_from_git(source)

            elif source.startswith("pimp://"):
                url = f"{REPOS_BASE_ADDR}/{source.removeprefix('pimp://')}"
                name = await mutils.clone_from_git(url)

            else:
                name = await mutils.clone_from_folder(Path(source))

            module = parse_module(MODULES_DIR / name)

            if module.init:
                await module.execute_init()

            for action in module.run:
                if isinstance(action, FileAction):
                    target = Path(parse_string_vars(action.target))
                    if target.exists():
                        copy_path = f"{target}.bkp"
                        shutil.copyfile(target, copy_path)
                        log.info(f'"{target.name}" copied to "{target.name}.bkp"')

                    link_path = Path(str(target) + ".j2")
                    if link_path.exists() or link_path.is_symlink():
                        log.info(
                            f'skipping linking "{link_path}" to "{action.template}", destination already exists'
                        )
                        continue

                    link_path.parent.mkdir(exist_ok=True, parents=True)
                    os.symlink(action.template, link_path)
                    log.info(f'linked "{link_path}" to "{action.template}"')

            self.modules[name] = module
            log.info(f'module "{name}" cloned')

    async def delete_module(self, module_name: str) -> None:
        if module_name not in self.modules:
            raise Exception(f'module "{module_name}" not found')

        module = self.modules[module_name]

        await mutils.delete_module(module)
        self.modules.pop(module_name)

        log.info(f'module "{module_name}" deleted')

    async def list_modules(self) -> None:
        for module in self.modules:
            log.info(module)
