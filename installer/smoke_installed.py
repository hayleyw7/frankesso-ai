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
from run_agent import LocalServer


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
    # Test the installed text client without allowing its downloader to connect.
    with patch.object(model_setup, "open_model", side_effect=AssertionError("Unexpected network download")):
        with LocalServer(app, model_path=model) as server:
            reply = desktop.Chat().ask("Name one common plant. One word only.")
            assert reply.strip() and reply != "No response from the local model."
            assert server.process.poll() is None
        assert server.process.poll() is not None
