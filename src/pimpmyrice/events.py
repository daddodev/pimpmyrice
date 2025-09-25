from functools import partial
from typing import Any, Callable, Coroutine


class EventHandler:
    """Simple async event pub/sub handler."""

    def __init__(self) -> None:
        self.subscribers: dict[str, list[Callable[[], Coroutine[Any, Any, None]]]] = {}

    def subscribe(
        self, event_name: str, fn: Callable[..., Coroutine[Any, Any, None]], *args: Any
    ) -> None:
        """
        Subscribe a coroutine function to an event.

        Args:
            event_name (str): Event name.
            fn (Callable[..., Coroutine]): Async callable to run.
            *args (Any): Positional args to bind to the callable.

        Returns:
            None
        """
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(partial(fn, *args))

    async def publish(self, event_name: str) -> None:
        """
        Publish an event and await all subscribers.

        Args:
            event_name (str): Event name.

        Returns:
            None
        """
        if event_name not in self.subscribers:
            return
        for callback in self.subscribers[event_name]:
            await callback()
