import os
import subprocess
import PyInstaller.__main__

sep = ';' if os.name == 'nt' else ':'

# Build the executable starting from the Qt interface entry script.
PyInstaller.__main__.run([
    'app_qt.py',
    '--name=CompareSet',
    '--onefile',
    '--windowed',
    f"--add-data=Imagem{os.sep}logo.png{sep}Imagem",
    f"--add-data=Imagem{os.sep}Icon janela.ico{sep}Imagem",
    f"--add-data=LICENSE{sep}.",
    f"--icon=Imagem{os.sep}Icon arquivo.ico",
])


def _sign_executable(path: str) -> None:
    """Sign the generated executable using signtool on Windows.

    The following environment variables must be defined:
    SIGNTOOL   - path to signtool.exe
    SIGN_CERT  - path to the .pfx certificate
    SIGN_PASS  - password for the certificate
    SIGN_TIMESTAMP - timestamp URL (optional)
    """

    signtool = os.environ.get("SIGNTOOL")
    cert_file = os.environ.get("SIGN_CERT")
    password = os.environ.get("SIGN_PASS")
    timestamp = os.environ.get("SIGN_TIMESTAMP", "http://timestamp.digicert.com")

    if os.name != "nt" or not (signtool and cert_file and password):
        return

    cmd = [
        signtool,
        "sign",
        "/f",
        cert_file,
        "/p",
        password,
        "/t",
        timestamp,
        path,
    ]

    try:
        subprocess.run(cmd, check=True)
        print("Executable signed.")
    except Exception as exc:
        print(f"Signature step failed: {exc}")


exe_path = os.path.join("dist", "CompareSet.exe")
_sign_executable(exe_path)
