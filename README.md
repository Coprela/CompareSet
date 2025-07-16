# CompareSet

CompareSet is a graphical tool for comparing two PDF revisions. It highlights
vector differences between documents, producing a new PDF that shows additions
and removals.

## Setup

1. Clone this repository.
2. (Optional) Create and activate a virtual environment.
3. Install the Python dependencies listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
   A Windows build is also available in `dist/CompareSet.exe`.

## Building an executable

To create a standalone executable from the project, install
[PyInstaller](https://www.pyinstaller.org/) and run the packaging script:

```bash
pip install pyinstaller
python package.py
```

The resulting binary will be placed in the `dist` directory.

## Dependencies

- Python 3.8 or later
- [Pillow](https://pypi.org/project/Pillow/) for image handling
- [PyMuPDF](https://pypi.org/project/PyMuPDF/) for PDF operations
- Tkinter (bundled with Python) for the GUI

## Supported page formats

CompareSet works with PDF pages sized according to the ISO A series. Pages
from **A0** down to **A4** are handled during comparison.

## Using the GUI

1. Launch the program using `python app.py`.
2. Click **Selecionar revisão antiga** and choose the old PDF.
3. Click **Selecionar nova revisão** and choose the new PDF.
4. Press **Comparar Revisões** and select where to save the output PDF.
5. Any digital signatures present in the chosen PDFs are stripped before
   comparison so that signed documents can be processed normally.
6. The generated file will contain two pages highlighting removals and
   additions.
7. (Optional) Use **Cor de Adição**, **Cor de Remoção** and the **Opacidade**
   slider to customize highlight colors.

The icons used by the GUI are located in the `Imagem` folder.

## PDF highlighting function

The helper function `gerar_pdf_com_destaques` can also be used programmatically.
It accepts optional `color_add`, `color_remove` and `opacity` parameters to
customize the highlight colors:

```python
from pdf_marker import gerar_pdf_com_destaques

gerar_pdf_com_destaques(
    "old.pdf",
    "new.pdf",
    removidos,
    adicionados,
    "out.pdf",
    color_add=(0, 0.8, 0),
    color_remove=(1, 0, 0),
    opacity=0.4,
)
```
