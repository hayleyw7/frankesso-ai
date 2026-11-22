"""Create or remove a per-user Windows Start menu shortcut. No privilege changes."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent
SHORTCUT_COMMAND = r"""
$ErrorActionPreference = 'Stop'
$programs = [Environment]::GetFolderPath('Programs')
if (-not $programs) { throw 'Windows did not provide a per-user Start menu folder.' }
$path = Join-Path $programs 'Frankesso.lnk'
$shell = New-Object -ComObject WScript.Shell
$description = 'Frankesso offline desktop chat'
if (Test-Path -LiteralPath $path) {
    if ($shell.CreateShortcut($path).Description -ne $description) {
        throw 'Another Start menu shortcut already uses the name Frankesso.'
    }
    if ($env:FRANKESSO_SHORTCUT_REMOVE -eq '1') { Remove-Item -LiteralPath $path; return }
}
if ($env:FRANKESSO_SHORTCUT_REMOVE -eq '1') { return }
New-Item -ItemType Directory -Path $programs -Force | Out-Null
$shortcut = $shell.CreateShortcut($path)
$shortcut.TargetPath = $env:FRANKESSO_PYTHONW
$shortcut.Arguments = '-B ' + [char]34 + (Join-Path $env:FRANKESSO_PROJECT 'agent\desktop.py') + [char]34
$shortcut.WorkingDirectory = $env:FRANKESSO_PROJECT
$shortcut.IconLocation = (Join-Path $env:FRANKESSO_PROJECT 'assets\frankesso.ico') + ',0'
$shortcut.Description = $description
$shortcut.Save()
if (-not (Test-Path -LiteralPath $path)) { throw 'The Start menu shortcut was not saved.' }
"""


def run(remove):
    if sys.platform != "win32":
        raise RuntimeError("This shortcut installer only runs on Windows.")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not remove:
        try:
            import tkinter  # noqa: F401
        except ImportError as error:
            raise RuntimeError("Frankesso Desktop needs local Python with Tkinter.") from error
        for required in (pythonw, PROJECT / "agent/desktop.py", PROJECT / "assets/frankesso.ico"):
            if not required.is_file():
                raise RuntimeError(f"Required desktop file not found: {required}")
    env = dict(os.environ, FRANKESSO_SHORTCUT_REMOVE="1" if remove else "0",
               FRANKESSO_PYTHONW=str(pythonw), FRANKESSO_PROJECT=str(PROJECT))
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_COMMAND],
                   env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true", help="Remove the Frankesso Start menu shortcut.")
    args = parser.parse_args()
    try:
        run(args.remove)
        print("Frankesso shortcut removed." if args.remove else "Done. Search for Frankesso in the Start menu.")
    except (OSError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
