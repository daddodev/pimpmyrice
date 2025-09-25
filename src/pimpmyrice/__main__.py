import asyncio
import logging

from pimpmyrice.cli import cli

log = logging.getLogger(__name__)


def main() -> None:
    """Entrypoint for the `pimp` CLI."""
    try:
        asyncio.run(cli())
    except KeyboardInterrupt:
        log.info("stopped")


if __name__ == "__main__":
    main()
    # import yappi
    #
    # with yappi.run():
    #     main()
    #
    # stats = yappi.get_func_stats()
    # stats.print_all()
    # stats.save("cr.prof", type="callgrind")

    # import cProfile
    #
    # cProfile.run("main()", sort="cumtime")

    # print("profiled")
