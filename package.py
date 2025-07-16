import os
import PyInstaller.__main__

sep = ';' if os.name == 'nt' else ':'

PyInstaller.__main__.run([
    'app.py',
    '--name=CompareSet',
    '--onefile',
    '--windowed',
    f"--add-data=Imagem{os.sep}logo.png{sep}Imagem",
    f"--add-data=Imagem{os.sep}Icon janela.ico{sep}Imagem",
    f"--add-data=LICENSE{sep}.",
    f"--icon=Imagem{os.sep}Icon arquivo.ico",
])
