import os
import sys
import shutil
import subprocess
import datetime
import json
import zipfile
import pathlib
import argparse

APP_NAME_DEFAULT = "CompareSet"
ENTRYPOINT = "run_app.py"  # deve chamar src.compareset.main:main()

# Candidatos de ícone (o script pega o primeiro que existir)
ICON_CANDIDATES = [
    os.path.join("resources", "icons", "app.ico"),
    os.path.join("resources", "icons", "compareset.ico"),
]

# Pastas de dados adicionais que serão incluídas (se existirem)
DATA_DIRS = ["resources", "assets"]

# Imports que, em geral, o PyInstaller precisa "forçar"
HIDDEN_IMPORTS = [
    "fitz",                 # PyMuPDF
    "cv2",                  # OpenCV
    "numpy",                # NumPy
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtPrintSupport",
    # Adicione aqui se usar:
    # "PySide6.QtSvg", "PySide6.QtPdf", "PySide6.QtQml",
]

# Módulos a excluir para reduzir tamanho
EXCLUDES = [
    "tkinter", "unittest", "distutils", "email",
    "setuptools", "pytest", "tests",
]

def run(cmd, check=True):
    print(">>", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=check)

def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa
    except Exception:
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

def clean(dist_name):
    build_dir = "build"
    dist_dir = os.path.join("dist", dist_name) if dist_name else None
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
    # limpar dist/app antigo se existir
    if dist_dir and os.path.isdir(dist_dir):
        shutil.rmtree(dist_dir)
    # não apagar outros artefatos em dist/

    # remover .spec antigo do app
    spec = f"{dist_name or APP_NAME_DEFAULT}.spec"
    if os.path.exists(spec):
        os.remove(spec)

def detect_icon():
    for p in ICON_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def collect_add_data():
    """Formata --add-data do PyInstaller: src;dst (no Windows)"""
    result = []
    for d in DATA_DIRS:
        if os.path.isdir(d):
            result.append(f"{d};{d}")
    return result

def build(args):
    ensure_pyinstaller()

    app_name = args.name or APP_NAME_DEFAULT
    icon = detect_icon()
    add_data = collect_add_data()

    # Limpeza opcional (segura)
    if args.clean:
        clean(app_name)

    # Monta comando base
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", app_name,
        "--clean",
        "--log-level=WARN",
    ]

    # onedir (padrão) ou onefile
    if args.onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # console/windowed
    if args.windowed:
        cmd.append("--windowed")
    else:
        cmd.append("--console")

    # ícone
    if icon:
        cmd += ["--icon", icon]

    # add-data
    for d in add_data:
        cmd += ["--add-data", d]

    # hidden-imports
    for h in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", h]

    # excludes
    for e in EXCLUDES:
        cmd += ["--exclude-module", e]

    # Pode-se travar arquitetura via --target-arch (PyInstaller 6+ com constrangimentos)
    # se necessário para cross-builds.

    # entrypoint
    cmd.append(ENTRYPOINT)

    run(cmd)

    # Descobrir pasta final de dist
    dist_root = pathlib.Path("dist")
    dist_path = dist_root / app_name
    if not dist_path.exists():
        # Se onefile, o artefato é um .exe diretamente em dist; localizar o primeiro
        candidates = list(dist_root.glob(f"{app_name}*"))
        if candidates:
            dist_path = candidates[0]

    # Inserir version.json
    if dist_path.exists():
        write_version_json(dist_path)
        print(f"[info] version.json gravado em: {dist_path}")
    else:
        print("[warn] pasta de saída não encontrada. verifique logs do PyInstaller.")

    # zipar distribuição (só faz sentido para onedir)
    if not args.nozip:
        zip_path = zip_dist(dist_path, app_name)
        print(f"[ok] zip gerado: {zip_path}")

    # dica final
    if args.onefile:
        exe_candidates = list(pathlib.Path("dist").glob(f"{app_name}.exe"))
        if exe_candidates:
            print(f"[ok] executável (onefile): {exe_candidates[0]}")
        else:
            print("[note] onefile: verifique dist/ para o .exe")
    else:
        exe = dist_path / f"{app_name}.exe"
        print(f"[ok] executável (onedir): {exe} (e DLLs ao redor)")

def write_version_json(dist_path: pathlib.Path):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    git = ""
    try:
        git = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        pass
    meta = {
        "app": str(dist_path.name),
        "built_at": ts,
        "git": git,
        "python": sys.version,
    }
    # Se onedir, dist_path é uma pasta; se onefile, é um arquivo .exe
    if dist_path.is_dir():
        out = dist_path / "version.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

def zip_dist(dist_path: pathlib.Path, app_name: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{app_name}-win-{ts}.zip"
    zip_path = pathlib.Path("dist") / zip_name

    # onefile: zip só o .exe; onedir: zip toda a pasta
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        if dist_path.is_file():
            z.write(dist_path, arcname=dist_path.name)
        else:
            base = dist_path.parent
            for root, _, files in os.walk(dist_path):
                for fn in files:
                    full = pathlib.Path(root) / fn
                    rel = full.relative_to(base)
                    z.write(full, rel)
    return str(zip_path)

def parse_args():
    p = argparse.ArgumentParser(description="Empacota o CompareSet com PyInstaller.")
    p.add_argument("--name", default=APP_NAME_DEFAULT, help="Nome do app (default: CompareSet)")
    p.add_argument("--onefile", action="store_true", help="Gera um .exe único (padrão: onedir)")
    p.add_argument("--windowed", action="store_true", help="Sem console (GUI)")
    p.add_argument("--clean", action="store_true", help="Limpa build/ e dist/<app> antes de construir")
    p.add_argument("--nozip", action="store_true", help="Não gerar .zip na pasta dist/")
    return p.parse_args()

def main():
    args = parse_args()
    if not os.path.isfile(ENTRYPOINT):
        print(f"[ERRO] ENTRYPOINT não encontrado: {ENTRYPOINT}")
        return 2
    build(args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
