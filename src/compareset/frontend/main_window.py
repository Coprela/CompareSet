"""Tkinter user interface for CompareSet with theme support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:  # pragma: no cover - Tkinter may not be available in all envs
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover - handle missing Tkinter gracefully
    tk = None
    ttk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]

from compareset.backend import compare_pdfs_all_pages


THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#f6f6f6",
        "fg": "#202124",
        "accent": "#2f6fed",
        "accent_fg": "#ffffff",
        "input_bg": "#ffffff",
        "input_fg": "#202124",
        "muted": "#5f6368",
        "tree_alt": "#ebebeb",
    },
    "dark": {
        "bg": "#1c1c1c",
        "fg": "#f1f3f4",
        "accent": "#5a7dff",
        "accent_fg": "#ffffff",
        "input_bg": "#2a2a2a",
        "input_fg": "#f1f3f4",
        "muted": "#a0a0a0",
        "tree_alt": "#262626",
    },
}


class CompareSetApp:
    """Main window for the CompareSet interface."""

    def __init__(self) -> None:
        if tk is None or ttk is None:  # pragma: no cover - handled earlier
            raise RuntimeError("Tkinter is not available")

        self.root = tk.Tk()
        self.root.title("CompareSet – Comparador de PDFs")
        self.root.minsize(720, 540)

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - fallback theme
            pass

        self.current_theme = "light"

        self.old_pdf_var = tk.StringVar()
        self.new_pdf_var = tk.StringVar()
        self.summary_var = tk.StringVar(value="Selecione os arquivos para começar.")

        self.dpi_var = tk.IntVar(value=300)
        self.method_var = tk.StringVar(value="edges")
        self.diff_thresh_var = tk.IntVar(value=25)
        self.dilate_var = tk.IntVar(value=3)
        self.erode_var = tk.IntVar(value=1)
        self.min_area_var = tk.IntVar(value=128)
        self.nms_iou_var = tk.DoubleVar(value=0.2)
        self.ignore_title_var = tk.BooleanVar(value=False)
        self.ignore_rect_var = tk.StringVar(value="")

        self._build_layout()
        self.apply_theme(self.current_theme)

    # ------------------------------------------------------------------
    # UI creation helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, padding=(16, 16, 16, 8))
        header.pack(fill="x")

        title = ttk.Label(
            header,
            text="CompareSet",
            font=("Segoe UI", 18, "bold"),
        )
        title.pack(side="left")

        self.theme_button = ttk.Button(
            header,
            text="🌙 Tema escuro",
            style="Accent.TButton",
            command=self.toggle_theme,
        )
        self.theme_button.pack(side="right")

        self.subtitle_label = ttk.Label(
            header,
            text="Compare duas versões de um PDF e veja rapidamente as diferenças",
            font=("Segoe UI", 10),
            foreground=THEMES[self.current_theme]["muted"],
        )
        self.subtitle_label.pack(anchor="w", pady=(8, 0))

        content = ttk.Frame(self.root, padding=(16, 0, 16, 16))
        content.pack(fill="both", expand=True)

        # File selection -------------------------------------------------
        file_frame = ttk.LabelFrame(content, text="Arquivos")
        file_frame.pack(fill="x", pady=(0, 16))

        self._create_file_selector(
            file_frame,
            row=0,
            label="PDF original",
            variable=self.old_pdf_var,
            command=lambda: self._select_file(self.old_pdf_var),
        )
        self._create_file_selector(
            file_frame,
            row=1,
            label="PDF revisado",
            variable=self.new_pdf_var,
            command=lambda: self._select_file(self.new_pdf_var),
        )

        # Parameters -----------------------------------------------------
        params_frame = ttk.LabelFrame(content, text="Parâmetros da comparação")
        params_frame.pack(fill="x", pady=(0, 16))

        self._add_spinbox(params_frame, "DPI", self.dpi_var, 72, 600, 0, tooltip="Resolução usada na rasterização")
        self._add_combobox(params_frame, "Método", self.method_var, ("edges", "diff", "mse"), 1)
        self._add_spinbox(params_frame, "Threshold", self.diff_thresh_var, 5, 255, 2)
        self._add_spinbox(params_frame, "Dilatar (px)", self.dilate_var, 0, 12, 3)
        self._add_spinbox(params_frame, "Erodir (px)", self.erode_var, 0, 12, 4)
        self._add_spinbox(params_frame, "Área mín. (px²)", self.min_area_var, 16, 2000, 5, step=16)
        self._add_spinbox(params_frame, "NMS IoU", self.nms_iou_var, 0.0, 1.0, 6, increment=0.05)

        options_frame = ttk.Frame(params_frame)
        options_frame.grid(column=0, row=7, columnspan=2, pady=(12, 0), sticky="w")

        ttk.Checkbutton(
            options_frame,
            text="Ignorar quadro de título",
            variable=self.ignore_title_var,
        ).pack(anchor="w")

        ttk.Label(options_frame, text="Ignorar retângulo (x0,y0,x1,y1)").pack(anchor="w", pady=(8, 0))
        self.ignore_rect_entry = ttk.Entry(options_frame, textvariable=self.ignore_rect_var, width=32)
        self.ignore_rect_entry.pack(anchor="w")

        # Actions --------------------------------------------------------
        actions = ttk.Frame(content)
        actions.pack(fill="x")

        self.compare_button = ttk.Button(
            actions,
            text="Comparar PDFs",
            style="Accent.TButton",
            command=self.run_compare,
        )
        self.compare_button.pack(side="left")

        ttk.Button(
            actions,
            text="Limpar",
            command=self.reset_fields,
        ).pack(side="left", padx=(8, 0))

        self.summary_label = ttk.Label(actions, textvariable=self.summary_var)
        self.summary_label.pack(side="right")

        # Results --------------------------------------------------------
        result_frame = ttk.LabelFrame(content, text="Resultados")
        result_frame.pack(fill="both", expand=True, pady=(16, 0))

        columns = ("page", "changes", "area")
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        self.result_tree.heading("page", text="Página")
        self.result_tree.heading("changes", text="Diferenças")
        self.result_tree.heading("area", text="Área total (pts²)")
        self.result_tree.column("page", width=80, anchor="center")
        self.result_tree.column("changes", width=120, anchor="center")
        self.result_tree.column("area", width=160, anchor="e")

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=vsb.set)
        self.result_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _create_file_selector(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: Any,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=8)
        entry = ttk.Entry(parent, textvariable=variable, width=70)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=8)
        parent.columnconfigure(1, weight=1)
        ttk.Button(parent, text="Selecionar", command=command).grid(row=row, column=2, padx=8, pady=8)

    def _add_spinbox(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.Variable,
        minimum: float,
        maximum: float,
        row: int,
        tooltip: str | None = None,
        *,
        step: int | None = None,
        increment: float | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
        spin_kwargs: Dict[str, Any] = {
            "from_": minimum,
            "to": maximum,
            "textvariable": variable,
            "width": 12,
        }
        if step is not None:
            spin_kwargs["increment"] = step
        if increment is not None:
            spin_kwargs["increment"] = increment
        spin = ttk.Spinbox(parent, **spin_kwargs)
        spin.grid(row=row, column=1, sticky="w", padx=8, pady=6)
        if tooltip:
            spin.configure(takefocus=True)

    def _add_combobox(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=12)
        combo.grid(row=row, column=1, sticky="w", padx=8, pady=6)
        combo.current(0)

    # ------------------------------------------------------------------
    # Theme handling
    # ------------------------------------------------------------------
    def apply_theme(self, theme: str) -> None:
        colors = THEMES[theme]
        self.root.configure(bg=colors["bg"])

        widgets = [
            "TFrame",
            "TLabelframe",
            "TLabelframe.Label",
            "TLabel",
            "TCheckbutton",
            "TCombobox",
            "Treeview",
        ]
        for widget in widgets:
            self.style.configure(widget, background=colors["bg"], foreground=colors["fg"])

        self.style.configure(
            "Accent.TButton",
            background=colors["accent"],
            foreground=colors["accent_fg"],
            borderwidth=0,
            focusthickness=1,
            focuscolor=colors["accent"],
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", colors["accent"])],
            foreground=[("active", colors["accent_fg"])],
        )
        self.style.configure("TButton", padding=(10, 6))

        self.style.configure(
            "TEntry",
            fieldbackground=colors["input_bg"],
            foreground=colors["input_fg"],
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=colors["input_bg"],
            foreground=colors["input_fg"],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=colors["input_bg"],
            foreground=colors["input_fg"],
        )

        self.style.configure(
            "Treeview",
            background=colors["input_bg"],
            fieldbackground=colors["input_bg"],
            foreground=colors["input_fg"],
            rowheight=26,
        )
        self.style.map(
            "Treeview",
            background=[("selected", colors["accent"])],
            foreground=[("selected", colors["accent_fg"])],
        )
        self.style.configure(
            "Treeview.Heading",
            background=colors["bg"],
            foreground=colors["fg"],
        )

        if hasattr(self.result_tree, "tag_configure"):
            self.result_tree.tag_configure("oddrow", background=colors["input_bg"])
            self.result_tree.tag_configure("evenrow", background=colors["tree_alt"])

        muted_color = colors["muted"]
        self.subtitle_label.configure(foreground=muted_color)
        self.summary_label.configure(foreground=colors["fg"])

        if theme == "light":
            self.theme_button.configure(text="🌙 Tema escuro")
        else:
            self.theme_button.configure(text="☀️ Tema claro")

    def toggle_theme(self) -> None:
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme(self.current_theme)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _select_file(self, variable: tk.StringVar) -> None:
        if filedialog is None:  # pragma: no cover - GUI only
            return
        path = filedialog.askopenfilename(
            title="Selecionar PDF",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
        )
        if path:
            variable.set(path)

    def reset_fields(self) -> None:
        self.old_pdf_var.set("")
        self.new_pdf_var.set("")
        self.summary_var.set("Selecione os arquivos para começar.")
        self.ignore_title_var.set(False)
        self.ignore_rect_var.set("")
        for child in self.result_tree.get_children():
            self.result_tree.delete(child)

    def run_compare(self) -> None:
        if messagebox is None:  # pragma: no cover - GUI only
            return

        old_pdf = self.old_pdf_var.get()
        new_pdf = self.new_pdf_var.get()

        if not old_pdf or not new_pdf:
            messagebox.showwarning("CompareSet", "Selecione os dois PDFs antes de comparar.")
            return

        if not Path(old_pdf).exists() or not Path(new_pdf).exists():
            messagebox.showerror("CompareSet", "Não foi possível encontrar os arquivos selecionados.")
            return

        try:
            ignore_rect = self._parse_rect(self.ignore_rect_var.get())
        except ValueError:
            return
        try:
            result = compare_pdfs_all_pages(
                old_pdf,
                new_pdf,
                dpi=int(self.dpi_var.get()),
                method=self.method_var.get(),
                diff_thresh=int(self.diff_thresh_var.get()),
                dilate_px=int(self.dilate_var.get()),
                erode_px=int(self.erode_var.get()),
                min_area_px=int(self.min_area_var.get()),
                nms_iou=float(self.nms_iou_var.get()),
                ignore_title_block=bool(self.ignore_title_var.get()),
                ignore_title_rect_pts=ignore_rect,
            )
        except Exception as exc:  # pragma: no cover - runtime errors
            messagebox.showerror("CompareSet", str(exc))
            return

        stats = result.get("stats", {})
        for child in self.result_tree.get_children():
            self.result_tree.delete(child)

        total_pages = int(result.get("pages", 0))
        diff_pages = 0
        total_area = 0.0

        for index, key in enumerate(sorted(stats, key=lambda x: int(x))):
            page_stats = stats[key]
            count = int(page_stats.get("count", 0))
            area = float(page_stats.get("area_pts2", 0.0))
            if count > 0:
                diff_pages += 1
                total_area += area
            tag = "evenrow" if index % 2 else "oddrow"
            self.result_tree.insert(
                "",
                "end",
                values=(int(key) + 1, count, f"{area:,.2f}"),
                tags=(tag,),
            )

        if diff_pages == 0:
            self.summary_var.set("Nenhuma diferença encontrada.")
        else:
            self.summary_var.set(
                f"{diff_pages} página(s) com diferenças em {total_pages} – área total {total_area:,.2f} pts²",
            )

    def _parse_rect(self, value: str) -> tuple[float, float, float, float] | None:
        if not value.strip():
            return None
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) != 4:
            if messagebox is not None:  # pragma: no cover - GUI only
                messagebox.showerror(
                    "CompareSet",
                    "O retângulo deve conter quatro valores separados por vírgula (x0,y0,x1,y1).",
                )
            raise ValueError("Invalid rectangle format")
        try:
            return tuple(float(p) for p in parts)  # type: ignore[return-value]
        except ValueError as exc:
            if messagebox is not None:  # pragma: no cover - GUI only
                messagebox.showerror("CompareSet", "Valores numéricos inválidos para o retângulo.")
            raise exc


def run_app() -> int:
    """Launch the Tkinter interface."""

    if tk is None or ttk is None:
        print("Tkinter is not available; GUI cannot be started.")
        return 1

    try:
        app = CompareSetApp()
    except tk.TclError:
        print("Tkinter cannot open a window; no display found.")
        return 1
    except RuntimeError:
        print("Tkinter is not available; GUI cannot be started.")
        return 1

    app.root.mainloop()
    return 0


__all__ = ["run_app", "CompareSetApp"]
