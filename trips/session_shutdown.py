import atexit
import logging
import signal
import threading

from django.contrib.sessions.models import Session
from django.db.utils import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

_registered = False
_lock = threading.Lock()


def _clear_all_sessions(reason: str) -> None:
    """Invalidate all user sessions so clients must log in again."""
    try:
        Session.objects.all().delete()
    except (OperationalError, ProgrammingError):
        # Skip cleanup when the sessions table is not available yet.
        logger.debug("Session cleanup skipped during %s.", reason)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Session cleanup failed during %s.", reason)


def _handle_shutdown_signal(signum, _frame) -> None:
    _clear_all_sessions(f"signal {signum}")


def register_session_cleanup_hooks() -> None:
    global _registered

    with _lock:
        if _registered:
            return
        _registered = True

    atexit.register(_clear_all_sessions, "process exit")

    for sig_name in ("SIGINT", "SIGTERM"):
        shutdown_signal = getattr(signal, sig_name, None)
        if shutdown_signal is None:
            continue
        try:
            signal.signal(shutdown_signal, _handle_shutdown_signal)
        except (ValueError, OSError):
            # Signal handlers can only be set from the main thread/process.
            continue
