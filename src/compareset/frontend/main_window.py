"""GUI entry point for CompareSet.

This module currently provides a very small Tkinter based window just so
that running ``python run_app.py`` actually launches something visible.
It is intentionally simple – the real application logic can replace this
stub later.
"""

from __future__ import annotations

try:  # pragma: no cover - Tkinter may not be available in all envs
    import tkinter as tk
except Exception:  # pragma: no cover - handle missing Tkinter gracefully
    tk = None


def run_app() -> int:
    """Launch a tiny Tkinter window to demonstrate the GUI startup.

    Returns
    -------
    int
        Zero on normal shutdown, non-zero if Tkinter is unavailable.
    """

    if tk is None:
        # When Tkinter cannot be imported (e.g. on a headless server),
        # inform the user instead of crashing.
        print("Tkinter is not available; GUI cannot be started.")
        return 1

    try:
        root = tk.Tk()
    except tk.TclError:
        # Raised when no display is available (e.g. running on a server).
        print("Tkinter cannot open a window; no display found.")
        return 1

    root.title("CompareSet")

    label = tk.Label(root, text="CompareSet GUI is running")
    label.pack(padx=20, pady=20)

    root.mainloop()
    return 0


__all__ = ["run_app"]
