"""Apple Silicon entry point for the shared offline desktop chat."""
import ctypes
import platform
from pathlib import Path
from queue import Empty
import sys
from time import monotonic

import agent
import desktop
from local_only import install_socket_guard


def bundle_runtime(executable):
    location = Path(executable).absolute()
    if (location.parent.name, location.parent.parent.name) != ("MacOS", "Contents"):
        raise RuntimeError("Open Frankesso.app from the complete Mac package.")
    return location.parent.parent / "Resources" / "FrankessoRuntime"


def macos_app_theme():
    """Read the effective AppKit appearance of the current application."""
    try:
        ctypes.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p)(("objc_msgSend", objc))

        def call(receiver, selector):
            return send(receiver, objc.sel_registerName(selector))

        app = call(objc.objc_getClass(b"NSApplication"), b"sharedApplication")
        appearance = call(app, b"effectiveAppearance")
        name = call(appearance, b"name")
        utf8 = call(name, b"UTF8String")
        return "dark" if utf8 and b"Dark" in ctypes.string_at(utf8) else "light"
    except (AttributeError, OSError):
        return "light"


def check_offline():
    import socket
    # A denied audit event occurs before any DNS query or connection can leave.
    for address in ("example.invalid", "192.0.2.1"):
        try:
            socket.create_connection((address, 443), timeout=1)
        except PermissionError:
            continue
        raise RuntimeError("The offline network guard did not reject an external address.")


def smoke(package_root, tk, ttk):
    """Exercise the bundled desktop worker with a fresh profile in package CI."""
    root = tk.Tk()
    try:
        for mode in ("light", "dark"):
            desktop.apply_chat_theme(root, ttk, mode, tk)
            logo = tk.PhotoImage(file=str(desktop.theme_brand_asset(mode)))
            if not logo.width():
                raise RuntimeError("Missing launcher art.")
        root.update_idletasks()
    finally:
        root.destroy()
    check_offline()
    worker = desktop.Worker(installed=True, package_root=package_root)
    try:
        deadline = monotonic() + 270
        asked = False
        while monotonic() < deadline:
            try:
                event, content = worker.outbox.get(timeout=1)
            except Empty:
                continue
            if event in {"error", "fatal"}:
                raise RuntimeError(content)
            if event == "ready" and not asked:
                worker.inbox.put("What is the capital of Japan? Answer in one word.")
                asked = True
            if event == "reply":
                if "tokyo" not in content.casefold():
                    raise RuntimeError(f"Unexpected model reply: {content}")
                print(f"Bundled offline model answered: {content}", flush=True)
                return
        raise RuntimeError("The local model did not answer within the test deadline.")
    finally:
        worker.close()
        worker.thread.join(timeout=15)


def main():
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise RuntimeError("This Mac package requires Apple Silicon.")
    install_socket_guard(agent.PORT)
    import tkinter as tk
    from tkinter import ttk
    runtime = bundle_runtime(sys.executable)
    if sys.argv[1:] == ["--smoke"]:
        smoke(runtime, tk, ttk)
    else:
        desktop.launch(tk, ttk, installed=True, package_root=runtime,
                       read_theme=macos_app_theme, font_family="Helvetica Neue")


if __name__ == "__main__":
    main()
