# CompareSet

CompareSet is a graphical tool for comparing two PDF revisions. It highlights
vector differences between documents, producing a new PDF that shows additions
and removals.

## Setup

1. Clone this repository.
2. (Optional) Create and activate a virtual environment.
3. Install the Python dependencies:
   ```bash
   pip install Pillow PyMuPDF
   ```
4. Run the application:
   ```bash
   python app.py
   ```
   A Windows build is also available in `dist/CompareSet.exe`.

## Dependencies

- Python 3.8 or later
- [Pillow](https://pypi.org/project/Pillow/) for image handling
- [PyMuPDF](https://pypi.org/project/PyMuPDF/) for PDF operations
- Tkinter (bundled with Python) for the GUI

## Using the GUI

1. Launch the program using `python app.py`.
2. Click **Selecionar revisão antiga** and choose the old PDF.
3. Click **Selecionar nova revisão** and choose the new PDF.
4. Press **Comparar Revisões** and select where to save the output PDF.
5. The generated file will contain two pages highlighting removals in red and
   additions in green.

The icons used by the GUI are located in the `Imagem` folder.

## Command line

A simple command line interface is available as `cli.py`. Run it with the paths
of the old revision, the new revision and the desired output file:

```bash
python -m cli old.pdf new.pdf comparison.pdf
```

The resulting PDF will contain the two versions with removed regions
highlighted in red and additions in green.
