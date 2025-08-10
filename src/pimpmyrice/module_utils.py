from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import shlex
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Coroutine, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from pimpmyrice.config_paths import CLIENT_OS, HOME_DIR, MODULES_DIR, TEMP_DIR, Os
from pimpmyrice.exceptions import IfCheckFailed
from pimpmyrice.files import load_yaml
from pimpmyrice.logger import current_module
from pimpmyrice.template import parse_string_vars, render_template_file
from pimpmyrice.utils import AttrDict, Timer, is_process_running

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


class ModuleState(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


def module_context_wrapper(
    module_name: str, modules_state: dict[str, ModuleState], coro: Awaitable[Any]
) -> Coroutine[Any, Any, Any]:
    async def wrapped() -> Any:
        timer = Timer()
        token = current_module.set(module_name)
        modules_state[module_name] = ModuleState.RUNNING
        try:
            r = await coro
            modules_state[module_name] = ModuleState.COMPLETED
            log.info(f"done in {timer.elapsed:.2f} sec")
            return r
        except IfCheckFailed as e:
            modules_state[module_name] = ModuleState.SKIPPED
            log.debug(str(e))
        except Exception as e:
            modules_state[module_name] = ModuleState.FAILED
            log.debug("exception:", exc_info=e)
            log.error(str(e))
        finally:
            current_module.reset(token)

    return wrapped()


def add_action_type_to_schema(
    action_type: str,
    schema: dict[str, Any],
) -> None:
    schema["properties"]["action"] = {
        "title": "Action type",
        "type": "string",
        "const": action_type,
    }
    schema["required"].append("action")


class ShellAction(BaseModel):
    action: Literal["shell"] = Field(default="shell")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    command: str
    detached: bool = False

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "shell")
    )

    async def run(self, theme_dict: AttrDict) -> None:
        cmd = parse_string_vars(
            string=self.command,
            module_name=self.module_name,
            theme_dict=theme_dict,
        )

        if self.detached:
            run_shell_command_detached(cmd)
            log.debug(f'command "{cmd}" started in background')
            return

        r = await run_shell_command(cmd)

        if r.returncode != 0:
            raise Exception(
                f'command "{cmd}" exited with code {r.returncode}\n'
                f"stdout: {r.out}\n"
                f"stderr: {r.err}"
            )

        if r.err:
            log.warning(f'command "{cmd}" returned errors:\n{r.err}')

        log.debug(f'executed "{cmd}"')


class FileAction(BaseModel):
    action: Literal["file"] = Field(default="file")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    target: str
    template: str = ""

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "file")
    )

    @model_validator(mode="before")
    @classmethod
    def set_fields(cls, data: Any) -> Any:
        if "target" in data and "template" not in data:
            template_path = f"{Path(data['target']).name}.j2"
            data["template"] = template_path
        return data

    async def run(self, theme_dict: AttrDict, out_dir: Path | None = None) -> None:
        template = Path(
            parse_string_vars(
                string=str(
                    MODULES_DIR / self.module_name / "templates" / self.template
                ),
                module_name=self.module_name,
                theme_dict=theme_dict,
            )
        )
        target = Path(
            parse_string_vars(
                string=self.target,
                module_name=self.module_name,
                theme_dict=theme_dict,
            )
        )

        if out_dir:
            if target.is_relative_to(HOME_DIR):
                target = out_dir / target.relative_to(HOME_DIR)
            else:
                target = out_dir / target

        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)

        processed_data = render_template_file(template, theme_dict)

        with open(target, "w", encoding="utf-8") as f:
            f.write(processed_data)

        log.debug(f'generated "{target}"')


class PythonAction(BaseModel):
    action: Literal["python"] = Field(default="python")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    py_file_path: str
    function_name: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "python")
    )

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        file_path = Path(self.py_file_path)

        if not file_path.is_absolute():
            file_path = MODULES_DIR / self.module_name / file_path

        fn = get_func_from_py_file(file_path, self.function_name)

        log.debug(f"{file_path}:{self.function_name} loaded")

        res = await fn(*args, **kwargs)

        log.debug(f"{file_path.name}:{self.function_name} returned:\n{res}")

        return res


class WaitForAction(BaseModel):
    action: Literal["wait_for"] = Field(default="wait_for")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    module: str
    timeout: int = 3

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "wait_for")
    )

    async def run(self, _: AttrDict, modules_state: dict[str, Any]) -> None:
        log.debug(f'waiting for module "{self.module}"...')
        timer = Timer()
        while modules_state[self.module] in [ModuleState.PENDING, ModuleState.RUNNING]:
            if timer.elapsed > self.timeout:
                log.error(
                    f'waiting for module "{self.module}" timed out (>{self.timeout} sec)'
                )
                break
            await asyncio.sleep(0.05)
        else:
            log.debug(f'done waiting for module "{self.module}"')

    def __str__(self) -> str:
        return f'wait for "{self.module}" to finish'


class IfRunningAction(BaseModel):
    action: Literal["if_running"] = Field(default="if_running")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    program_name: str
    should_be_running: bool = True

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "if_running")
    )

    async def run(self, _: AttrDict) -> None:
        running = is_process_running(self.program_name)
        if self.should_be_running != running:
            raise IfCheckFailed(f"{self.__str__()} returned false")

    def __str__(self) -> str:
        return f'if "{self.program_name}" {"running" if self.should_be_running else "not running"}'


class LinkAction(BaseModel):
    action: Literal["link"] = Field(default="link")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    origin: str
    destination: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "link")
    )

    async def run(self) -> None:
        origin_path = Path(parse_string_vars(self.origin, module_name=self.module_name))
        destination_path = Path(
            parse_string_vars(self.destination, module_name=self.module_name)
        )

        if not origin_path.is_absolute():
            origin_path = MODULES_DIR / self.module_name / "files" / origin_path

        if destination_path.exists():
            raise Exception(
                f'cannot link destination "{destination_path}" to origin "{
                    origin_path
                }", destination already exists'
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(
            origin_path,
            destination_path,
            target_is_directory=origin_path.is_dir(),
        )
        # action.destination.hardlink_to(action.origin)
        log.info(f'init: "{destination_path}" linked to "{origin_path}"')


ModuleInit = Union[LinkAction]

ModulePreRun = Union[PythonAction]


ModuleRun = Union[ShellAction, FileAction, PythonAction, IfRunningAction, WaitForAction]

ModuleCommand = Union[PythonAction]


class Module(BaseModel):
    name: SkipJsonSchema[str] = Field(exclude=True)
    enabled: bool = True
    os: list[Os] = list(Os)
    init: list[ModuleInit] = []
    pre_run: list[ModulePreRun] = []
    run: list[ModuleRun] = []
    commands: dict[str, ModuleCommand] = {}

    async def execute_command(
        self, command_name: str, tm: ThemeManager, *args: Any, **kwargs: Any
    ) -> None:
        if command_name not in self.commands:
            raise Exception(
                f'command "{command_name}" not found in [{
                    ", ".join(self.commands.keys())
                }]'
            )

        await self.commands[command_name].run(tm=tm, *args, **kwargs)

    async def execute_init(self) -> None:
        for init_action in self.init:
            await init_action.run()

        for action in self.run:
            if isinstance(action, FileAction):
                target = Path(
                    parse_string_vars(
                        string=action.target,
                        module_name=self.name,
                    )
                ).absolute()
                if target.exists():
                    copy_path = f"{target}.bkp"
                    shutil.copyfile(target, copy_path)
                    log.info(f'"{target}" copied to "{target.name}.bkp"')

                link_path = target.with_name(target.name + ".j2")
                template_path = Path(
                    parse_string_vars(
                        string=str(
                            MODULES_DIR / self.name / "templates" / action.template
                        ),
                        module_name=self.name,
                    )
                ).absolute()

                if link_path.exists() or link_path.is_symlink():
                    log.info(
                        f'skipping linking "{link_path}" to template "{
                            template_path
                        }", destination already exists'
                    )
                    continue

                link_path.parent.mkdir(exist_ok=True, parents=True)
                os.symlink(template_path, link_path)
                log.info(f'linked "{link_path}" to "{template_path}"')

        log.info(f'module "{self.name}" initialized')

    async def execute_pre_run(self, theme_dict: AttrDict) -> AttrDict:
        for action in self.pre_run:
            action_res = await action.run(theme_dict)
            theme_dict = action_res

        return theme_dict

    async def execute_run(
        self,
        theme_dict: AttrDict,
        modules_state: dict[str, Any],
        out_dir: Path | None = None,
    ) -> None:
        # get_module_dict
        theme_dict = (
            theme_dict + theme_dict["modules_styles"][self.name]
            if self.name in theme_dict["modules_styles"]
            else deepcopy(theme_dict)
        )

        # output to custom directory (needed for testing)
        if out_dir:
            for action in self.run:
                if isinstance(action, FileAction):
                    # TODO other actions
                    await action.run(theme_dict, out_dir=out_dir)
                else:
                    log.warning(f"dumping {action} not implemented, skipping")
            return

        for action in self.run:
            if isinstance(action, WaitForAction):
                await action.run(theme_dict, modules_state)
            else:
                await action.run(theme_dict)


def get_func_from_py_file(py_file: Path, func_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"pimp_imported_{py_file}", py_file)
    if not spec or not spec.loader:
        raise ImportError(f'could not load "{py_file}"')
    py_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(py_module)

    func = getattr(py_module, func_name)

    return func


def run_shell_command_detached(command: str, cwd: Path | None = None) -> None:
    if sys.platform == "win32":
        subprocess.Popen(
            shlex.split(command),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            cwd=cwd,
        )
        return

    subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp,
        cwd=cwd,
    )


@dataclass
class ShellResponse:
    out: str
    err: str
    returncode: int


async def run_shell_command(command: str, cwd: Path | None = None) -> ShellResponse:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    out, err = await proc.communicate()

    if proc.returncode is None:
        raise Exception("returncode is None")

    res = ShellResponse(
        out=out.decode(),
        err=err.decode(),
        returncode=proc.returncode,
    )

    return res


def load_module_conf(module_name: str) -> dict[str, Any]:
    data = load_yaml(MODULES_DIR / module_name / "conf.yaml")
    return data


async def clone_from_folder(source: Path, out_dir: Path = MODULES_DIR) -> str:
    if not (source / "module.yaml").exists():
        raise Exception(f'module not found at "{source.absolute()}"')

    name = source.name
    dest_dir = out_dir / name
    if dest_dir.exists():
        raise Exception(f'module "{name}" already present')

    shutil.copytree(source, MODULES_DIR / name)
    return name


async def clone_from_git(url: str, out_dir: Path = MODULES_DIR) -> str:
    name = url.split("/")[-1].removesuffix(".git")
    dest_dir = out_dir / name
    if dest_dir.exists():
        raise Exception(f'module "{name}" already present')

    random = str(uuid4())

    if CLIENT_OS == Os.WINDOWS:
        cmd = f'set GIT_TERMINAL_PROMPT=0 && git clone "{url}" {random}'
    else:
        cmd = f'GIT_TERMINAL_PROMPT=0 git clone "{url}" {random}'

    r = await run_shell_command(cmd, cwd=TEMP_DIR)
    if r.out:
        log.debug(f'git clone "{url}" stdout:\n{r.out}')
    if r.err:
        log.debug(f'git clone "{url}" stderr:\n{r.err}')

    if r.returncode != 0:
        raise Exception(
            f'git clone failed with code {r.returncode}:\r\n{r.err}\r\nrepository "{
                url
            }" not found'
        )

    shutil.move(TEMP_DIR / random, dest_dir)

    return name


async def delete_module(module: Module) -> None:
    path = MODULES_DIR / module.name
    shutil.rmtree(path)
