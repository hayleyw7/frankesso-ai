"""Run against installed files with the bundled Python, never the runner Python."""
import os
from pathlib import Path
import sys
from threading import Event
import tkinter as tk
from unittest.mock import patch

app = Path(os.environ["SMOKE_APP_ROOT"])
sys.path.insert(0, str(app / "agent"))
import desktop
import model_setup


root = tk.Tk()
root.withdraw()
try:
    icon = tk.PhotoImage(file=str(app / "assets/frankesso-favicon.png"))
    assert icon.width() == 128
    root.iconbitmap(default=str(app / "assets/frankesso.ico"))
    root.update()
finally:
    root.destroy()

worker = desktop.Worker(installed=True)
try:
    assert worker.outbox.get(timeout=20)[0] == "needs_model"
    assert worker.server is None
finally:
    worker.close()
    worker.thread.join(20)
assert not worker.thread.is_alive()

if os.environ.get("FULL_MODEL_SMOKE") == "1":
    destination = Path(os.environ["LOCALAPPDATA"]) / "FrankessoDesktop" / "models"
    model = model_setup.download(destination, Event(), lambda *_: None)
    assert model_setup.verify(model, Event())
    # Exercise the same startup, local reply, and shutdown as the installed GUI.
    with patch.object(model_setup, "download", side_effect=AssertionError("Unexpected network download")):
        worker = desktop.Worker(installed=True)
        try:
            assert worker.outbox.get(timeout=20)[0] == "status"
            kind, message = worker.outbox.get(timeout=265)
            if kind != "ready":
                if worker.server and worker.server.startup_log:
                    print(worker.server.startup_log, file=sys.stderr)
                raise AssertionError(message)
            worker.inbox.put("Name one common plant. One word only.")
            kind, reply = worker.outbox.get(timeout=180)
            assert kind == "reply", reply
            assert reply.strip() and reply != "No response from the local model."
            assert worker.server.process.poll() is None
        finally:
            worker.close()
            worker.thread.join(30)
        assert not worker.thread.is_alive()
        assert worker.server.process.poll() is not None
