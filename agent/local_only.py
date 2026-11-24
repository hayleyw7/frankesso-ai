"""Local file and transport policy shared by both Windows entry points."""
from pathlib import PureWindowsPath
import re
import sys


def require_local_path(path):
    # Check the drive before probing the filesystem. UNC paths and mapped
    # drives can open network connections even for exists() or lstat().
    if sys.platform != "win32":
        return
    path = PureWindowsPath(path)
    if not path.is_absolute() or not re.fullmatch(r"[a-zA-Z]:", path.drive):
        raise ValueError("Choose a file on a local Windows drive, not a network path.")
    if windows_drive_type(path.anchor) not in (2, 3, 5, 6):  # removable, fixed, CD-ROM, RAM disk
        raise ValueError("Network drives and unavailable drives are not allowed.")


def windows_drive_type(root):
    import ctypes
    get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
    get_drive_type.argtypes = [ctypes.c_wchar_p]
    get_drive_type.restype = ctypes.c_uint
    return get_drive_type(root)


def install_socket_guard(model_port):
    """Prevent the app's Python networking APIs reaching non-model addresses.

    This is an application guard, not an OS sandbox for native code or
    other programs. The packaged llama.cpp runner is built without
    its optional network features and launched with its offline flags.
    """
    def audit(event, args):
        if event in {"socket.connect", "socket.bind"}:
            address = args[1]
            if type(address) is not tuple or address != ("127.0.0.1", model_port):
                raise PermissionError("Frankesso can only connect to its local model.")
        elif event == "socket.getaddrinfo":
            if args[:2] != ("127.0.0.1", model_port):
                raise PermissionError("Frankesso cannot resolve external addresses.")
        elif event in {"socket.sendto", "socket.sendmsg", "socket.gethostbyname",
                       "socket.gethostbyaddr", "socket.getnameinfo"}:
            raise PermissionError("Frankesso does not use external networking.")

    sys.addaudithook(audit)
