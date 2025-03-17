import logging
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pimpmyrice.theme import ThemeManager

log = logging.getLogger(__name__)


async def process_args(tm: ThemeManager, args: dict[str, Any]) -> None:
    options = {
        "mode_name": args["--mode"],
        "palette_name": args["--palette"],
        "print_theme_dict": args["--print-theme-dict"],
    }

    if t := args["--tags"]:
        tags = set(t.split(","))
    else:
        tags = set()

    if t := args["--exclude-tags"]:
        exclude_tags = set(t.split(","))
    else:
        exclude_tags = set()

    if styles_names := args["--style"]:
        options["styles_names"] = styles_names.split(",")

    if modules := args["--modules"]:
        options["include_modules"] = modules.split(",")
    elif modules := args["--exclude-modules"]:
        options["exclude_modules"] = modules.split(",")

    if args["random"]:
        if name_includes := args["--name"]:
            options["name_includes"] = name_includes
        if tags:
            options["include_tags"] = tags
        if exclude_tags:
            options["exclude_tags"] = exclude_tags
        await tm.set_random_theme(**options)
        return

    elif args["refresh"]:
        await tm.apply_theme(**options)
        return

    elif args["theme"]:
        if args["set"]:
            await tm.apply_theme(theme_name=args["THEME"], **options)
            return

        elif args["rename"]:
            await tm.rename_theme(
                theme_name=args["THEME"],
                new_name=args["NEW_NAME"],
            )
            return

        elif args["delete"]:
            tm.delete_theme(args["THEME"])
            return
        elif args["export"]:
            await tm.export_theme(
                args["THEME"], out_dir=Path(args["OUT_DIR"]).absolute(), **options
            )
            return

    elif args["module"]:
        if args["clone"]:
            await tm.mm.clone_module(args["MODULE_URL"])
            return

        elif args["create"]:
            await tm.mm.create_module(args["MODULE_NAME"])
            return

        elif args["delete"]:
            await tm.mm.delete_module(args["MODULE"])
            return

        elif args["run"]:
            await tm.mm.run_module_command(
                tm,
                module_name=args["MODULE"],
                command=args["COMMAND"],
                cmd_args=args["COMMAND_ARGS"],
            )
            return

        elif args["reinit"]:
            await tm.mm.init_module(module_name=args["MODULE"])
            return

    elif args["tags"]:
        if args["add"]:
            await tm.add_tags(args["THEMES"], tags)
            return
        elif args["remove"]:
            await tm.remove_tags(args["THEMES"], tags)
            return

    elif args["toggle"]:
        await tm.toggle_mode()
        return

    elif args["mode"]:
        mode = args["MODE"]

        await tm.set_mode(mode)
        return

    elif args["gen"]:
        a = {}

        if args["--name"]:
            a["name"] = args["--name"]

        if tags:
            a["tags"] = tags

        if apply := args["--apply"]:
            a["apply"] = apply

        for img in args["IMAGE"]:
            await tm.generate_theme(image=img, **a)
        return

    elif args["list"]:
        if args["modules"]:
            await tm.mm.list_modules()
            return
        elif args["themes"]:
            await tm.list_themes()
            return
        elif args["tags"]:
            await tm.list_tags()
            return
        elif args["palettes"]:
            await tm.list_palettes()
            return
        elif args["styles"]:
            await tm.list_styles()
            return

    elif args["info"]:
        # TODO use Rich Table?
        msg = f"""🍙 PimpMyRice {version("pimpmyrice")}
name: {tm.config.theme}
mode: {tm.config.mode}
"""

        log.info(msg)
        return

    elif args["regen"]:
        await tm.rewrite_themes(regen_colors=True, name_includes=args["--name"])
        return

    elif args["rewrite"]:
        if args["themes"]:
            await tm.rewrite_themes(name_includes=args["--name"])
            return
        elif args["modules"]:
            await tm.mm.rewrite_modules(name_includes=args["--name"])
            return

    log.error("not implemented")
