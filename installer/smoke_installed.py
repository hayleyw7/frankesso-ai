"""Run against installed files with the bundled Python, never the runner Python."""
import os
import subprocess
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

app = Path(os.environ["SMOKE_APP_ROOT"])
sys.path.insert(0, str(app / "agent"))
import desktop
import chat_state
from local_only import install_socket_guard

install_socket_guard(desktop.agent.PORT)


root = tk.Tk()
root.withdraw()
try:
    icon = tk.PhotoImage(file=str(app / "assets/frankesso-favicon.png"))
    assert icon.width() == 128
    assert icon.get(42, 86) == (182, 65, 71)
    root.iconbitmap(default=str(app / "assets/frankesso.ico"))
    desktop.apply_chat_theme(root, ttk, tk=tk)
    assert root.cget("background").upper() == "#FAF2E4"
    style = ttk.Style(root)
    assert style.lookup("Frankesso.Primary.TButton", "background").upper() == "#0A0909"
    assert style.lookup("Frankesso.Primary.TButton", "foreground").upper() == "#FAF2E4"
    panel = desktop.chat_panel(root, ttk)
    transcript = tk.Text(panel, **desktop.chat_text_colors())
    transcript.insert("1.0", "Synthetic seed notes")
    desktop.apply_chat_theme(root, ttk, "dark", tk)
    transcript.configure(**desktop.chat_text_colors("dark"))
    assert root.cget("background").upper() == "#0A0909"
    assert style.lookup("Frankesso.Primary.TButton", "background").upper() == "#FAF2E4"
    assert transcript.get("1.0", "end-1c") == "Synthetic seed notes"
    assert style.layout("Frankesso.Chat.TFrame")[0][0] == "Frankesso.RoundedChat"
    assert style.layout("Frankesso.Composer.TFrame")[0][0] == "Frankesso.RoundedComposer"
    # Exercise the actual native ttk controls with the rounded shared surfaces.
    radio = ttk.Button(root, text="New chat", style="Frankesso.Secondary.TButton")
    radio.state(["disabled"])
    radio.pack()
    action = ttk.Button(root, text="Send", style="Frankesso.Primary.TButton")
    action.pack()
    root.update()
    assert radio.winfo_reqheight() >= round(root.winfo_fpixels("1i") * 48 / 96)
    assert radio.winfo_reqheight() == action.winfo_reqheight()
    assert str(style.layout(desktop.PRIMARY_BUTTON_STYLE)[0][0]) == "Frankesso.RoundedPrimary"
    download = ttk.Button(root, text="Import model", style=desktop.PRIMARY_BUTTON_STYLE)
    assert download.winfo_reqheight() == action.winfo_reqheight()
    assert style.layout(download.cget("style")) == style.layout(action.cget("style"))

    # Capture only this synthetic application window; never the runner desktop.
    for widget in root.winfo_children():
        widget.destroy()
    root.title("Frankesso chat surface smoke")
    root.geometry("390x460+40+40")
    fixture = ttk.Frame(root, style="Frankesso.TFrame", padding=16)
    fixture.pack(fill="both", expand=True)
    logos = {mode: tk.PhotoImage(file=str(desktop.theme_brand_asset(mode))).subsample(4, 4)
             for mode in ("light", "dark")}
    assert all(photo.transparency_get(0, 0) for photo in logos.values())
    header_art = ttk.Label(fixture, style="Frankesso.TLabel", image=logos["light"])
    header_art.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    for row, (label, disabled) in enumerate((("Ready", False), ("Model import", True)), 1):
        ttk.Label(fixture, text=label, style="Frankesso.TLabel").grid(row=row, column=0, padx=(0, 12), sticky="w")
        for col, (label, role) in enumerate((("New chat", "Secondary"), ("Send", "Primary")), 1):
            button = ttk.Button(fixture, text=label, style=f"Frankesso.{role}.TButton")
            button.grid(row=row, column=col, padx=(0, 8), pady=4)
            if disabled:
                button.state(["disabled"])
    ttk.Button(fixture, text="Import model", style=desktop.PRIMARY_BUTTON_STYLE).grid(
        row=3, column=1, columnspan=2, sticky="e", pady=(4, 8))
    sample_text = []
    for row, (label, height) in enumerate((("A synthetic transcript", 2), ("A synthetic draft message", 1)), 4):
        panel = desktop.chat_panel(fixture, ttk, input_field=row == 5)
        panel.grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        panel.columnconfigure(0, weight=1)
        field = tk.Text(panel, height=height, width=20, **desktop.chat_text_colors())
        field.grid(row=0, column=0, sticky="ew")
        field.insert("1.0", label)
        sample_text.append(field)
    root.deiconify()
    root.lift()
    evidence = Path(os.environ.get("RUNNER_TEMP", str(app))) / "frankesso-button-smoke"
    evidence.mkdir(exist_ok=True)
    for mode in ("light", "dark"):
        desktop.apply_chat_theme(root, ttk, mode, tk)
        header_art.configure(image=logos[mode])
        for field in sample_text:
            field.configure(**desktop.chat_text_colors(mode))
        root.update()
        try:
            powershell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-File",
                            str(Path(__file__).with_name("capture-button-smoke.ps1")),
                            str(root.winfo_id()), str(evidence / f"{mode}.png")],
                           check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            print(f"Optional window capture skipped for {mode}: {error}", file=sys.stderr)
    root.withdraw()
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
    model = Path(os.environ["FRANKESSO_SMOKE_MODEL"])
    worker = desktop.Worker(installed=True, animate_replies=True)
    try:
        assert worker.outbox.get(timeout=20)[0] == "needs_model"
        worker.inbox.put(str(model))
        kind, message = worker.outbox.get(timeout=60)
        assert kind == "status", (kind, message)
        while kind != "model_ready":
            kind, message = worker.outbox.get(timeout=60)
            assert kind in {"progress", "model_ready"}, (kind, message)
        kind, message = worker.outbox.get(timeout=265)
        if kind != "ready":
            if worker.server and worker.server.startup_log:
                print(worker.server.startup_log, file=sys.stderr)
            raise AssertionError(message)
        worker.inbox.put("Name one common plant. One word only.")
        try:
            kind, reply = worker.outbox.get(timeout=195)
            assert kind == "progressive_reply", reply
            assert "".join(desktop.reveal_chunks(reply)) == reply
            worker.inbox.put(True)
            assert worker.outbox.get(timeout=20)[0] == "ready"
        except Exception:
            if worker.server and worker.server.log_path.exists():
                print(worker.server.log_tail(16000), file=sys.stderr)
            raise
        assert reply.strip() and reply != "No response from the local model."
        assert worker.server.process.poll() is None

        def ask(text, progressive=False, keep=True):
            worker.inbox.put(text)
            event, message = worker.outbox.get(timeout=20)
            assert event == ("progressive_reply" if progressive else "reply"), message
            if progressive:
                assert "".join(desktop.reveal_chunks(message)) == message
                worker.inbox.put(keep)
                assert worker.outbox.get(timeout=20)[0] == "ready"
            return message

        assert ask("What’s your favourite colour?") == "Crimson. It’s the only color that makes it through the portal intact."
        assert ask("favorite food or drink?") == "Coffee."
        assert ask("What is your favourite drug?") == "Caffeine."
        assert ask("Favorite weather?") == "Fog."
        assert ask("What's your pet peeve?") == "Decaf."
        assert ask("Where are you from?") == "The side of the mirror that stays warm."
        assert ask("Favorite time of day?") == "Night."
        assert ask("What exact time is your favorite?") == "Midnight."
        assert ask(" TEST ", progressive=True, keep=False) == "Signal received from the other side. Something knocked back. ☕"
        note_text = "Label the clay fern pots with teal ink."
        note_id = ask("Remember this: " + note_text).split()[-1]
        assert note_text in ask("/memories")
        chat_id = ask("/chats").split()[0]
        worker.inbox.put(None)
        assert worker.outbox.get(timeout=20)[0] == "ready"
        transcript = ask("/open " + chat_id)
        assert "Name one common plant." in transcript
        assert "Signal received" not in transcript
        assert note_id in ask("/memories")
        assert ask("Forget " + note_id) == "Note removed. Saved chats are unchanged."
        assert ask("/memories") == "No saved notes."
        # A fresh object reads persisted chat data without the active UX state.
        saved = desktop.Chat(state=chat_state.ChatState(
            chat_state.state_root(), desktop.agent.Controller._check_components))
        assert "Name one common plant." in saved.ask("/open " + chat_id)
        assert saved.ask("/delete " + chat_id) == "Chat deleted."
    finally:
        worker.close()
        worker.thread.join(30)
    assert not worker.thread.is_alive()
    assert worker.server.process.poll() is not None
