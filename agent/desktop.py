"""A text-only desktop window for Frankesso's existing offline model."""
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

import agent
from run_agent import LocalServer, read_config, runtime_root

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MAX_PROMPT = 1800
MAX_CONTEXT = 1800
SYSTEM = (
    "You are Frankesso, an offline desktop chat assistant. Keep answers concise. "
    "No files, tools, or internet are available. Never claim to have performed an action. /no_think"
)


class Chat:
    def __init__(self, request=agent.model_request):
        self.request = request
        self.history = []

    def ask(self, prompt):
        prompt = prompt.strip()
        if not prompt or len(prompt) > MAX_PROMPT:
            raise ValueError(f"Enter a message of 1 to {MAX_PROMPT} characters.")
        recent = []
        remaining = MAX_CONTEXT
        for turn in reversed(self.history):
            size = sum(len(message["content"]) for message in turn)
            if size > remaining:
                break
            recent[0:0] = turn
            remaining -= size
        user = {"role": "user", "content": prompt}
        response = self.request([{"role": "system", "content": SYSTEM}, *recent, user],
                                tools_enabled=False)
        if response.get("tool_calls"):
            return "No action taken. Desktop chat does not use tools."
        reply = response.get("content") or "No response from the local model."
        self.history = (self.history + [[user, {"role": "assistant", "content": reply}]])[-6:]
        return reply


class Worker:
    def __init__(self):
        self.inbox = Queue()
        self.outbox = Queue()
        self.stop = Event()
        self.server = None
        self.thread = Thread(target=self.run, name="local-chat-worker")
        self.thread.start()

    def run(self):
        try:
            if self.stop.is_set():
                return
            self.server = LocalServer(runtime_root(read_config()), stop=self.stop)
            with self.server:
                if self.stop.is_set():
                    return
                self.outbox.put(("ready", "Ready · Offline"))
                chat = Chat()
                while not self.stop.is_set():
                    prompt = self.inbox.get()
                    if self.stop.is_set():
                        break
                    if prompt is None:
                        chat = Chat()
                        self.outbox.put(("ready", "Ready · Offline"))
                        continue
                    try:
                        self.outbox.put(("reply", chat.ask(prompt)))
                    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
                        self.outbox.put(("error", str(error)))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            if not self.stop.is_set():
                self.outbox.put(("fatal", str(error)))

    def close(self):
        self.stop.set()
        self.inbox.put(None)
        if self.server is not None:
            self.server.cancel()


def launch(tk, ttk):
    root = tk.Tk()
    root.title("Frankesso")
    root.geometry("720x580")
    root.minsize(430, 390)
    try:
        root.iconbitmap(default=str(ASSETS / "frankesso.ico"))
    except tk.TclError:
        pass

    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(0, weight=1)

    header = ttk.Frame(frame)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)
    logo = tk.PhotoImage(file=str(ASSETS / "frankesso-favicon.png"))
    ttk.Label(header, image=logo).grid(row=0, column=0, rowspan=2, padx=(0, 12))
    ttk.Label(header, text="Frankesso", font=("Segoe UI", 18, "bold")).grid(row=0, column=1, sticky="sw")
    ttk.Label(header, text="Offline desktop chat · Text only").grid(row=1, column=1, sticky="nw")
    status = tk.StringVar(value="Starting the local model…")
    ttk.Label(frame, textvariable=status).grid(row=1, column=0, pady=(10, 6), sticky="w")

    chat_frame = ttk.Frame(frame)
    chat_frame.grid(row=2, column=0, sticky="nsew")
    chat_frame.columnconfigure(0, weight=1)
    chat_frame.rowconfigure(0, weight=1)
    output = tk.Text(chat_frame, wrap="word", state="disabled", font=("Segoe UI", 11),
                     padx=12, pady=10, height=8)
    output.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(chat_frame, orient="vertical", command=output.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    output.configure(yscrollcommand=scroll.set)

    ttk.Label(frame, text="Message  ·  Enter to send, Shift+Enter for a new line").grid(
        row=3, column=0, pady=(12, 4), sticky="w")
    entry = tk.Text(frame, wrap="word", height=3, font=("Segoe UI", 11), padx=8, pady=6)
    entry.grid(row=4, column=0, sticky="ew")
    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def append(speaker, text):
        output.configure(state="normal")
        output.insert("end", f"{speaker}\n{text}\n\n")
        output.see("end")
        output.configure(state="disabled")

    def available(enabled):
        for button in (send_button, new_button):
            button.state(["!disabled" if enabled else "disabled"])

    def send(*_):
        if send_button.instate(["disabled"]):
            return "break"
        text = entry.get("1.0", "end-1c").strip()
        if not text or len(text) > MAX_PROMPT:
            status.set(f"Enter a message of 1 to {MAX_PROMPT} characters.")
            return "break"
        append("You", text)
        entry.delete("1.0", "end")
        status.set("Writing a reply…")
        available(False)
        worker.inbox.put(text)
        return "break"

    def new_chat():
        available(False)
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.configure(state="disabled")
        entry.delete("1.0", "end")
        worker.inbox.put(None)
        entry.focus_set()

    send_button = ttk.Button(buttons, text="Send", command=send)
    send_button.pack(side="right")
    new_button = ttk.Button(buttons, text="New chat", command=new_chat)
    new_button.pack(side="right", padx=(0, 8))
    available(False)
    entry.bind("<Return>", send)
    entry.bind("<Shift-Return>", lambda _: None)
    entry.focus_set()
    worker = Worker()

    def poll():
        try:
            while True:
                kind, message = worker.outbox.get_nowait()
                if kind == "ready":
                    status.set(message)
                    available(True)
                elif kind == "reply":
                    append("Frankesso", message)
                    status.set("Ready · Offline")
                    available(True)
                elif kind == "error":
                    append("Local model error", message)
                    status.set("Could not reply. Try again.")
                    available(True)
                else:
                    append("Could not start Frankesso",
                           message + "\nCheck your local runtime path and close any other Frankesso session.")
                    status.set("Local model unavailable")
        except Empty:
            root.after(75, poll)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.after(75, poll)
    try:
        root.mainloop()
    finally:
        worker.close()


if __name__ == "__main__":
    try:
        import tkinter as tk
        from tkinter import ttk
        launch(tk, ttk)
    except Exception as error:
        import sys
        if sys.platform != "win32":
            raise
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, f"{error}\n\nFrankesso Desktop requires local Python with Tkinter.",
            "Frankesso could not start", 0x10,
        )
        raise SystemExit(1)
