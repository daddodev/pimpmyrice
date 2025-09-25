import json
import logging
from contextvars import ContextVar

from rich.logging import RichHandler

request_id: ContextVar[str] = ContextVar("request_id", default="request-none")
current_module: ContextVar[str] = ContextVar("current_module", default="")


class ContextFilter(logging.Filter):
    """Inject request and module context into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        if not hasattr(record, "module_name"):
            record.module_name = current_module.get()
        return True


class ModuleFormatter(logging.Formatter):
    """Formatter that prefixes messages with module name when available."""

    def format(self, record: logging.LogRecord) -> str:
        base_format = "%(message)s"
        if hasattr(record, "module_name") and record.module_name:
            base_format = f"[%(module_name)s] {base_format}"
        formatter = logging.Formatter(base_format)
        return formatter.format(record)


def serialize_logrecord(log_record: logging.LogRecord) -> str:
    """
    Serialize a LogRecord to JSON for transport.

    Args:
        log_record (logging.LogRecord): Record to serialize.

    Returns:
        str: JSON string.
    """
    msg = log_record.getMessage()
    if log_record.exc_info:
        msg += "\r\ncheck server logs for more information"

    log_dict = {
        "name": log_record.name,
        "level": log_record.levelno,
        "pathname": log_record.pathname,
        "lineno": log_record.lineno,
        "msg": msg,
        "func": log_record.funcName,
        "sinfo": log_record.stack_info,
        "module_name": log_record.module_name
        if hasattr(log_record, "module_name")
        else None,
    }

    return json.dumps(log_dict)


def deserialize_logrecord(json_str: str) -> logging.LogRecord:
    """
    Deserialize a JSON string into a LogRecord.

    Args:
        json_str (str): JSON-encoded LogRecord data.

    Returns:
        logging.LogRecord: Reconstructed record.
    """
    log_dict = json.loads(json_str)

    log_record = logging.LogRecord(
        name=log_dict.get("name"),
        level=log_dict.get("level"),
        pathname=log_dict.get("pathname"),
        lineno=log_dict.get("lineno"),
        msg=log_dict.get("msg"),
        args=(),
        exc_info=None,
        func=log_dict.get("func"),
        sinfo=log_dict.get("sinfo"),
    )

    log_record.__dict__["module_name"] = log_dict.get("module_name")

    return log_record


def set_up_logging() -> None:
    """
    Configure global logging with Rich handler and context filters.

    Returns:
        None
    """
    handler: logging.Handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        show_path=False,
        show_time=False,
    )
    handler.setFormatter(ModuleFormatter())

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[handler],
    )

    log = logging.getLogger()

    context_filter = ContextFilter()
    for handler in log.handlers:
        handler.addFilter(context_filter)
    log.addFilter(context_filter)
