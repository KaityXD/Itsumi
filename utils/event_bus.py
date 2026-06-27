import asyncio
import inspect
from typing import Callable, Dict, List
from utils.logger import logger


class EventBus:
    """
    A lightweight, decoupled pub-sub event bus.
    Supports both synchronous and asynchronous listeners.
    """

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Register a callback for a specific event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)
            logger.trace(f"Subscribed callback '{getattr(callback, '__name__', str(callback))}' to event: {event_name}")

    def unsubscribe(self, event_name: str, callback: Callable):
        """Unsubscribe a callback from an event."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
                logger.trace(f"Unsubscribed callback '{getattr(callback, '__name__', str(callback))}' from event: {event_name}")
            except ValueError:
                pass

    async def publish(self, event_name: str, *args, **kwargs):
        """
        Publish an event to all subscribers asynchronously.
        Tasks are spawned in the background so publishing does not block the caller.
        """
        if event_name not in self._listeners or not self._listeners[event_name]:
            return

        listeners = list(self._listeners[event_name])
        logger.trace(f"Publishing event '{event_name}' to {len(listeners)} listeners.")

        for callback in listeners:
            asyncio.create_task(self._safe_invoke(event_name, callback, *args, **kwargs))

    async def _safe_invoke(self, event_name: str, callback: Callable, *args, **kwargs):
        """Execute a single subscriber safely, logging any exceptions to forensics."""
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Exception in listener '{getattr(callback, '__name__', str(callback))}' on event '{event_name}': {e}"
            )
            try:
                from utils.error_handler import UniversalErrorHandler
                handler = UniversalErrorHandler()
                handler.save_error(e)
            except Exception as handler_err:
                logger.error(f"Failed to record event listener error in forensics: {handler_err}")


# Global singleton instance
event_bus = EventBus()
