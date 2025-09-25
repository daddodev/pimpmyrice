class IfCheckFailed(Exception):
    """Raised when an IfRunningAction condition is not satisfied."""
    ...


class ReferenceNotFound(Exception):
    """Raised when a Jinja2 variable reference cannot be resolved."""
    ...
