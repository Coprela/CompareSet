import os
import shutil
import subprocess
import logging

import PyInstaller.__main__
from version_check import CURRENT_VERSION

logger = logging.getLogger(__name__)


sep = ";" if os.name == "nt" else ":"


def _obfuscate(entry: str) -> str:
    """Attempt to obfuscate the given script with PyArmor."""
    out_dir = "obf"
    cmd = "pyarmor"
    try:  # detect PyArmor version
        import pyarmor

        ver = getattr(pyarmor, "__version__", "0")
        major = int(ver.split(".")[0]) if ver.split(".")[0].isdigit() else 0
        if major >= 8:
            logger.warning("PyArmor %s detected; using 'pyarmor-7' command", ver)
            cmd = "pyarmor-7"
    except Exception:
        # PyArmor not installed; will attempt command directly
        pass

    try:
        subprocess.run(
            [
                cmd,
                "obfuscate",
                "-O",
                out_dir,
                entry,
            ],
            check=True,
        )

        out_file = os.path.join(out_dir, entry)
        if not os.path.exists(out_file):
            logger.warning(
                "Obfuscation failed; %s not found. Building without obfuscation.",
                out_file,
            )
            return entry
        return out_file
    except Exception as exc:
        logger.info(
            "PyArmor not available (%s); building without obfuscation.",
            exc,
        )
        return entry


# Build the executable starting from the Qt interface entry script.
app_name = f"CompareSet {CURRENT_VERSION}"

entry_script = _obfuscate("run_app.py")

PyInstaller.__main__.run(
    [
        entry_script,
        f"--name={app_name}",
        "--onefile",
        "--windowed",
        f"--add-data=assets{os.sep}icons{os.sep}Icon - Improvement.png{sep}assets/icons",
        f"--add-data=assets{os.sep}icons{os.sep}Icon - Question Mark Help.png{sep}assets/icons",
        f"--add-data=assets{os.sep}icons{os.sep}Icon - Gear.png{sep}assets/icons",
        f"--add-data=assets{os.sep}icons{os.sep}Icon - History.png{sep}assets/icons",
        f"--add-data=assets{os.sep}icons{os.sep}Icon - Administration.png{sep}assets/icons",
        # bundle the application icon used by the Qt interface
        f"--add-data=assets{os.sep}icons{os.sep}Icon - CompareSet.ico{sep}assets/icons",
        f"--add-data=assets{os.sep}style.qss{sep}assets",
        f"--add-data=LICENSE{sep}.",
        f"--add-data=LICENSE_EN.txt{sep}.",
        f"--add-data=LICENSE_PT.txt{sep}.",
        f"--icon=assets{os.sep}icons{os.sep}Icon - CompareSet.ico",
    ]
)

if entry_script != "run_app.py":
    shutil.rmtree(os.path.dirname(entry_script), ignore_errors=True)


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
        logger.info("Executable signed.")
    except Exception as exc:
        logger.error("Signature step failed: %s", exc)


exe_name = app_name + (".exe" if os.name == "nt" else "")
exe_path = os.path.join("dist", exe_name)
_sign_executable(exe_path)
