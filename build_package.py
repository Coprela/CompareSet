import os
import subprocess

import PyInstaller.__main__

sep = ";" if os.name == "nt" else ":"

# Build the executable starting from the Qt interface entry script.
PyInstaller.__main__.run(
    [
        "main_interface.py",
        "--name=CompareSet",
        "--onefile",
        "--windowed",
        f"--add-data=Images{os.sep}Icon - Improvement.png{sep}Images",
        f"--add-data=Images{os.sep}Icon - Question Mark Help.png{sep}Images",
        f"--add-data=Images{os.sep}Icon - Gear.png{sep}Images",
        f"--add-data=Images{os.sep}Icon - History.png{sep}Images",
        # bundle the application icon used by the Qt interface
        f"--add-data=Images{os.sep}Icon - CompareSet.ico{sep}Images",
        f"--add-data=LICENSE{sep}.",
        f"--add-data=LICENSE_EN.txt{sep}.",
        f"--add-data=LICENSE_PT.txt{sep}.",
        f"--icon=Images{os.sep}Icon - CompareSet.ico",
    ]
)


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
