import logging
from contextvars import ContextVar

from rich.logging import RichHandler

request_id: ContextVar[str] = ContextVar("request_id", default="request-none")
current_module: ContextVar[str] = ContextVar("current_module", default="")


class ModuleContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.module_name = current_module.get()
        return True


class DynamicModuleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base_format = "%(message)s"
        if record.module_name:  # type: ignore
            base_format = f"[%(module_name)s] {base_format}"
        formatter = logging.Formatter(base_format)
        return formatter.format(record)


def set_up_logging() -> None:
    handler: logging.Handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        show_path=False,
        show_time=False,
    )
    handler.setFormatter(DynamicModuleFormatter())

    logging.basicConfig(
        level=logging.INFO,
        format="%(module_name)s %(message)s",
        handlers=[handler],
    )

    log = logging.getLogger()

    module_filter = ModuleContextFilter()
    for handler in log.handlers:
        handler.addFilter(module_filter)
    log.addFilter(module_filter)
