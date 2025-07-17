# CompareSet

CompareSet is a graphical tool for comparing two PDF revisions. It highlights
vector differences between documents, producing a new PDF that shows additions
and removals. All drawing primitives such as lines and shapes as well as the
words that compose the text are analysed. This finer granularity avoids
marking whole paragraphs when only a few words changed. A small positional
tolerance is applied so that minor shifts do not count as changes.

## Setup

1. Clone this repository.
2. (Optional) Create and activate a virtual environment.
3. Install the Python dependencies listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Qt application (requires `PySide6` which is included in the
   requirements file or can be installed with `pip install PySide6`):
   ```bash
   python main_interface.py
   ```
   This interface provides improvement/help icons and a language
   switcher. The original `app.py` Tkinter interface is kept for legacy
   use. A Windows build is also available in `dist/CompareSet.exe`.

## Building an executable

To create a standalone executable from the project, install
[PyInstaller](https://www.pyinstaller.org/) and run the packaging script:

```bash
pip install pyinstaller
python build_package.py
```

The resulting binary will be placed in the `dist` directory.  If the
environment variables `SIGNTOOL`, `SIGN_CERT` and `SIGN_PASS` are
defined, the script also attempts to sign the generated executable using
Microsoft's `signtool`.  Set `SIGN_TIMESTAMP` to override the timestamp
URL (defaults to the DigiCert service).

## Dependencies

- Python 3.8 or later
- [Pillow](https://pypi.org/project/Pillow/) for image handling
- [PyMuPDF](https://pypi.org/project/PyMuPDF/) for PDF operations
- Tkinter (bundled with Python) for the classic GUI
- [PySide6](https://pypi.org/project/PySide6/) for the Qt interface

## Supported page formats

CompareSet works with PDF pages sized according to the ISO A series. Pages
from **A0** down to **A4** are handled during comparison.
Pages whose dimensions differ by less than **1 mm** are treated as equal
size so no scaling is applied.

## Using the GUI

1. Launch the program using `python main_interface.py`. The window shows a custom icon from `Images/Icon - CompareSet.ico`.
2. Click **Selecionar revisão antiga** (red button) and choose the old PDF.
3. Click **Selecionar nova revisão** (green button) and choose the new PDF.
4. Press the purple **Comparar Revisões** button and select where to save the output PDF.
5. Any digital signatures present in the chosen PDFs are stripped before
   comparison so that signed documents can be processed normally.
6. The generated file will contain two pages highlighting removals and
   additions.
7. The progress bar indicates processing status so you know if the program
   is still working or if something went wrong.
8. After the PDF is created you are asked if you want to open it with your default viewer.

The icons used by the GUI are located in the `Images` folder.

### Qt interface

The Qt version includes improvement and help icons aligned to the top-right of the window. A drop-down next to them lets you switch between **EN** and **PTBR**.
Ensure `PySide6` is installed (e.g. `pip install PySide6`) and run:

```bash
python main_interface.py
```
The classic `app.py` Tkinter interface remains available for legacy users.

## PDF highlighting function

The helper function `gerar_pdf_com_destaques` can also be used programmatically.
It accepts optional `color_add` and `color_remove` parameters. Highlight
opacity is always fixed at `0.3`:

```python
from pdf_highlighter import gerar_pdf_com_destaques

gerar_pdf_com_destaques(
    "old.pdf",
    "new.pdf",
    removidos,
    adicionados,
    "out.pdf",
    color_add=(0, 0.8, 0),
    color_remove=(1, 0, 0),
)
```

## Adaptive comparison

`comparar_pdfs` normally uses a single IoU threshold of ``0.9`` to match
elements between revisions.  When adaptive mode is enabled from the
**Settings** dialog the function reruns the comparison starting from an IoU of
``1.0`` and decreasing by ``0.05`` until no new differences appear or the
minimum threshold is reached.  The result of the final iteration is returned to
the caller.

## Legacy C++ engine

Previous releases shipped with `CompareSet.Engine.dll`, a compiled C++ library
used for PDF comparison. The current codebase implements this logic purely in
Python, so the DLL is not required. Should you still depend on the legacy
engine, build it separately and place the resulting DLL next to the Python
scripts.

## License

This project is distributed under the terms of the MIT License. The
GUI includes a **Licen\u00e7a** button that opens a dialog displaying the
full license text.
