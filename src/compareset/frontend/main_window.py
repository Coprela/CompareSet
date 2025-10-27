"""Graphical interface for CompareSet.

The previous version of this module only displayed a small stub window.
It now provides a minimal but functional Tkinter interface that lets the
user select two PDF files and run the comparison routine from the backend.
The goal is to have something usable that can be extended in the future.
"""

from __future__ import annotations

try:  # pragma: no cover - Tkinter may not be available in all envs
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:  # pragma: no cover - handle missing Tkinter gracefully
    tk = None
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]

from compareset.backend import compare_pdfs_all_pages


def run_app() -> int:
    """Launch the Tkinter interface."""

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

    old_var = tk.StringVar()
    new_var = tk.StringVar()
    result_var = tk.StringVar()

    def select_old() -> None:
        if filedialog is None:
            return
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All", "*.*")])
        if path:
            old_var.set(path)

    def select_new() -> None:
        if filedialog is None:
            return
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All", "*.*")])
        if path:
            new_var.set(path)

    def run_compare() -> None:
        if messagebox is None:
            return
        old_pdf = old_var.get()
        new_pdf = new_var.get()
        if not old_pdf or not new_pdf:
            messagebox.showwarning("CompareSet", "Selecione os dois PDFs antes de comparar.")
            return
        try:
            res = compare_pdfs_all_pages(old_pdf, new_pdf)
        except Exception as exc:  # pragma: no cover - runtime errors
            messagebox.showerror("CompareSet", str(exc))
            return
        diff_pages = sum(1 for s in res.get("stats", {}).values() if s.get("count", 0) > 0)
        result_var.set(f"{diff_pages} página(s) com diferenças")

    frm = tk.Frame(root, padx=10, pady=10)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text="PDF antigo:").grid(row=0, column=0, sticky="w")
    tk.Entry(frm, textvariable=old_var, width=40).grid(row=0, column=1, padx=4, pady=4)
    tk.Button(frm, text="Selecionar", command=select_old).grid(row=0, column=2, padx=4)

    tk.Label(frm, text="PDF novo:").grid(row=1, column=0, sticky="w")
    tk.Entry(frm, textvariable=new_var, width=40).grid(row=1, column=1, padx=4, pady=4)
    tk.Button(frm, text="Selecionar", command=select_new).grid(row=1, column=2, padx=4)

    tk.Button(frm, text="Comparar", command=run_compare).grid(row=2, column=0, columnspan=3, pady=10)

    tk.Label(frm, textvariable=result_var, fg="blue").grid(row=3, column=0, columnspan=3, pady=5)

    root.mainloop()
    return 0


__all__ = ["run_app"]
