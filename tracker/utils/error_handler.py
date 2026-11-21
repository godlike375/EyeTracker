import traceback
import sys
from typing import Callable


class ErrorHandler:
    def __init__(self, on_fatal_error: Callable[[str], None] = None,
                 auto_restart_delay: int = 10,
                 max_consecutive_errors: int = 3):
        self._on_fatal_error = on_fatal_error
        self._auto_restart_delay = auto_restart_delay
        self._max_consecutive_errors = max_consecutive_errors
        self._error_count = 0

    def handle_exceptions(self, func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self._error_count += 1
                error_msg = self._format_error(e)
                if self._on_fatal_error:
                    self._on_fatal_error(error_msg)
                if self._error_count >= self._max_consecutive_errors:
                    self._attempt_restart()
                raise
        return wrapper

    def _format_error(self, exception: Exception) -> str:
        tb = traceback.format_exc()
        return f"{type(exception).__name__}: {exception}\n\n{tb}"

    def _attempt_restart(self):
        import time
        time.sleep(self._auto_restart_delay)
        self._error_count = 0

    def reset(self):
        self._error_count = 0

    @property
    def error_count(self):
        return self._error_count
