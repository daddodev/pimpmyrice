from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator
from pydantic.json_schema import (JsonDict, JsonSchemaExtraCallable,
                                  SkipJsonSchema)
from typing_extensions import Annotated

from pimpmyrice import files, utils
from pimpmyrice.config import CLIENT_OS, MODULES_DIR, TEMP_DIR, Os
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import AttrDict, Result, Timer, parse_string_vars

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


def add_action_type_to_schema(
    action_type: str,
    schema: JsonDict,
) -> None:
    schema["properties"]["action"] = {  # type: ignore
        "title": "Action type",
        "type": "string",
        "const": action_type,
    }
    schema["required"].append("action")  # type: ignore


class ShellAction(BaseModel):
    action: Literal["shell"] = Field(default="shell")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    command: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "shell")
    )

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result()

        try:
            cmd = utils.parse_string_vars(
                string=self.command,
                module_name=self.module_name,
                theme_dict=theme_dict,
            )

            out, err = await run_shell_command(cmd)

            if out:
                res.debug(out, self.module_name)
            if err:
                res.warning(
                    f'command "{cmd}" returned an error:\n{err}', self.module_name
                )

            res.debug(
                f'executed "{cmd}"',
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


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
            template_path = f'{Path(data["target"]).name}.j2'
            data["template"] = template_path
        return data

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result()

        try:
            template = Path(
                utils.parse_string_vars(
                    string=str(
                        MODULES_DIR / self.module_name / "templates" / self.template
                    ),
                    module_name=self.module_name,
                    theme_dict=theme_dict,
                )
            )
            target = Path(
                utils.parse_string_vars(
                    string=self.target,
                    module_name=self.module_name,
                    theme_dict=theme_dict,
                )
            )

            if not target.parent.exists():
                target.parent.mkdir(parents=True)

            with open(template, "r") as f:
                data = f.read()
            processed_data = utils.process_template(data, theme_dict)

            with open(target, "w") as f:
                f.write(processed_data)

            res.debug(
                f'generated "{target.name}"',
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class PythonAction(BaseModel):
    action: Literal["python"] = Field(default="python")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    py_file_path: str
    function_name: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "python")
    )

    async def run(self, *args: Any, **kwargs: Any) -> Result[Any]:
        file_path = Path(self.py_file_path)

        if not file_path.is_absolute():
            file_path = MODULES_DIR / self.module_name / file_path

        res = Result()

        try:
            spec = importlib.util.spec_from_file_location(self.module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f'could not load "{file_path}"')
            py_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(py_module)

            fn = getattr(py_module, self.function_name)

            res.debug(
                f"{file_path.name}:{self.function_name} loaded",
                self.module_name,
            )

            if asyncio.iscoroutinefunction(fn):
                res.value = await fn(*args, **kwargs)
            else:
                res.value = fn(*args, **kwargs)

            res.debug(
                f"{file_path.name}:{self.function_name} returned:\n{res.value}",
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class IfRunningAction(BaseModel):
    action: Literal["if_running"] = Field(default="if_running")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    program_name: str
    should_be_running: bool

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "if_running")
    )

    async def run(self, theme_map: AttrDict) -> Result:
        res = Result()

        try:
            running = utils.is_process_running(self.program_name)
            if self.should_be_running:
                res.ok = running
            else:
                res.ok = not running
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res

    def __str__(self) -> str:
        return f'if "{self.program_name}" {"running" if self.should_be_running
                                           else "not running"}'


class LinkAction(BaseModel):
    action: Literal["link"] = Field(default="link")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    origin: str
    destination: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "link")
    )

    async def run(self) -> Result:
        res = Result()

        origin_path = Path(parse_string_vars(self.origin, module_name=self.module_name))
        destination_path = Path(
            parse_string_vars(self.destination, module_name=self.module_name)
        )

        if not origin_path.is_absolute():
            origin_path = MODULES_DIR / self.module_name / "files" / origin_path

        if destination_path.exists():
            return res.error(
                f'cannot link destination "{destination_path}" to origin "{origin_path}", destination already exists'
            )
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(
                origin_path,
                destination_path,
                target_is_directory=origin_path.is_dir(),
            )
            # action.destination.hardlink_to(action.origin)
            res.info(f'init: "{destination_path}" linked to "{origin_path}"')
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


ModuleInit = Union[LinkAction]

ModulePreRun = Union[PythonAction]


ModuleRun = Union[ShellAction, FileAction, PythonAction, IfRunningAction]

ModuleCommand = Union[PythonAction]


class Module(BaseModel):
    name: SkipJsonSchema[str] = Field(exclude=True)
    enabled: bool = True
    os: list[Os] = [o for o in Os]
    init: list[ModuleInit] = []
    pre_run: list[ModulePreRun] = []
    run: list[ModuleRun] = []
    commands: dict[str, ModuleCommand] = {}

    async def execute_command(self, command_name: str, tm: ThemeManager) -> Result:
        res = Result()

        if command_name not in self.commands:
            return res.error(
                f'command "{command_name}" not found in [{", ".join(self.commands.keys())}]'
            )

        try:
            action_res = await self.commands[command_name].run(tm=tm)
            res += action_res
            if not action_res.ok:
                return res

        except Exception as e:
            return res.exception(
                e, f'command "{command_name}" encountered an error:', self.name
            )

        return res

    async def execute_init(self) -> Result:
        res = Result()

        for action in self.init:
            try:
                action_res = await action.run()
                res += action_res
                if not action_res.ok:
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        return res

    async def execute_pre_run(self, theme_dict: AttrDict) -> Result[AttrDict]:
        res: Result[AttrDict] = Result()

        try:
            for action in self.pre_run:
                action_res = await action.run(theme_dict)
                res += action_res
                if action_res.value:
                    theme_dict = action_res.value

        except Exception as e:
            res.exception(e, self.name)
        finally:
            res.value = theme_dict
            return res

    async def execute_run(self, theme_dict: AttrDict) -> Result:
        res = Result(name=self.name)
        timer = Timer()

        # get_module_dict
        theme_dict = (
            theme_dict + theme_dict["modules_styles"][self.name]
            if self.name in theme_dict["modules_styles"]
            else deepcopy(theme_dict)
        )

        for action in self.run:
            try:
                action_res = await action.run(theme_dict)
                res += action_res
                if not action_res.ok:
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        res.time = timer.elapsed()
        res.info(f"done in {res.time:.2f} sec", self.name)
        res.ok = True
        return res


async def run_shell_command(command: str, cwd: Path | None = None) -> tuple[str, str]:
    if command.endswith("&"):
        detached = True
        command = command[:-1].strip()
    else:
        detached = False

    if detached:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
            shell=True,
        )
        return f'command "{command}" started in background', ""

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    out, err = await proc.communicate()
    # print(f"{out.decode()=}\n{err.decode()=}")
    return out.decode(), err.decode()


def load_module_conf(module_name: str) -> dict[str, Any]:
    data = files.load_yaml(MODULES_DIR / module_name / "conf.yaml")
    return data


async def clone_from_folder(source: Path) -> str:
    if not (source / "module.yaml").exists():
        raise Exception(f'module not found at "{source}"')
    shutil.copytree(source, MODULES_DIR / source.name)
    return source.name


async def clone_from_git(url: str) -> str:
    name = url.split("/")[-1].removesuffix(".git")
    dest_dir = MODULES_DIR / name
    if dest_dir.exists():
        raise Exception(f'module "{name}" already present')
    random = str(uuid4())
    if CLIENT_OS == Os.WINDOWS:
        cmd = f'set GIT_TERMINAL_PROMPT=0 && git clone "{url}" {random}'
    else:
        cmd = f'GIT_TERMINAL_PROMPT=0 git clone "{url}" {random}'
    res, err = await run_shell_command(cmd, cwd=TEMP_DIR)

    if res:
        log.debug(res)

    if err:
        for line in err.split("\n"):
            if line and "Cloning into" not in line:
                if "terminal prompts disabled" in line:
                    raise Exception("repository not found")
                raise Exception(err)

    shutil.move(TEMP_DIR / random, dest_dir)

    return name


async def delete_module(module: Module) -> None:
    path = MODULES_DIR / module.name
    shutil.rmtree(path)
