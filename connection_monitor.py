from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

import compareset_env as csenv


class ConnectionMonitor(QObject):
    """Background monitor that periodically checks server connectivity."""

    status_changed = Signal(bool)
    check_failed = Signal(str)

    def __init__(self, *, interval_ms: int = 10000, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.interval_ms = interval_ms
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._schedule_check)
        self._online = False
        self._checking = False

    def start(self) -> None:
        self._schedule_check()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _schedule_check(self) -> None:
        if self._checking:
            return
        self._checking = True
        threading.Thread(target=self._check_connection, daemon=True).start()

    def _check_connection(self) -> None:
        try:
            available = csenv.is_server_available(csenv.SERVER_ROOT)
        except Exception as exc:  # pragma: no cover - defensive
            self.check_failed.emit(str(exc))
            self._checking = False
            return
        finally:
            pass

        if available != self._online:
            self._online = available
            self.status_changed.emit(available)
        self._checking = False
