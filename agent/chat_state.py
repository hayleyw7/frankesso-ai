"""Explicitly local chat history and manually saved notes. No model tools."""
from datetime import date
import json
import os
from pathlib import Path
import re
import tempfile
import sys
import uuid

ID = re.compile(r"[0-9a-f]{32}")
MAX_CHAT_MESSAGES = 200
MAX_MESSAGE = 8000
MAX_NOTES = 100
MAX_NOTE = 500
MAX_CONTEXT = 1800


def state_root():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Frankesso" / "chat-state"
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Frankesso" / "chat-state" if base else Path.home() / ".frankesso" / "chat-state"


class ChatState:
    def __init__(self, root, check_components):
        self.root = root.absolute()
        self.check = check_components
        self.chat_id = uuid.uuid4().hex
        self.messages = []

    def _path(self, name):
        path = self.root / name
        self.check(path)
        return path

    def _read(self, name, limit):
        path = self._path(name)
        try:
            with path.open("rb") as source:
                data = source.read(limit + 1)
        except FileNotFoundError:
            return []
        if len(data) > limit:
            raise ValueError("Local chat data is too large.")
        try:
            rows = json.loads(data)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Local chat data could not be read.") from error
        if not isinstance(rows, list):
            raise ValueError("Invalid local chat data.")
        return rows

    def _write(self, name, rows):
        path = self._path(name)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".chat-", delete=False) as out:
                staged = Path(out.name)
                out.write(json.dumps(rows, ensure_ascii=False).encode("utf-8"))
            self.check(path)
            staged.replace(path)
        finally:
            if staged and staged.exists():
                staged.unlink()

    @staticmethod
    def _chat_file(chat_id):
        if not ID.fullmatch(chat_id):
            raise ValueError("Use a chat ID from /chats.")
        return "chat-" + chat_id + ".json"

    def _chat(self, chat_id):
        name = self._chat_file(chat_id)
        if not self._path(name).is_file():
            raise ValueError("Chat not found.")
        messages = self._read(name, MAX_CHAT_MESSAGES * (MAX_MESSAGE * 6 + 64))
        if not all(isinstance(row, dict) and row.get("role") in {"user", "assistant"}
                   and isinstance(row.get("content"), str) for row in messages):
            raise ValueError("Invalid local chat history.")
        return messages

    def new(self):
        self.chat_id = uuid.uuid4().hex
        self.messages = []

    def open(self, chat_id):
        messages = self._chat(chat_id)
        self.chat_id, self.messages = chat_id, messages

    def delete(self, chat_id):
        name = self._chat_file(chat_id)
        self._path(name).unlink(missing_ok=False)
        if chat_id == self.chat_id:
            self.new()

    def chats(self):
        self.check(self.root)
        chats = []
        for path in sorted(self.root.glob("chat-*.json")):
            chat_id = path.stem.removeprefix("chat-")
            if ID.fullmatch(chat_id):
                try:
                    rows = self._chat(chat_id)
                    self.check(path)
                    chats.append((path.stat().st_mtime_ns, chat_id, rows[0]["content"] if rows else ""))
                except (ValueError, OSError):
                    continue
        return [(chat_id, " ".join(title.split())[:80]) for _, chat_id, title in sorted(chats, reverse=True)]

    def save_turn(self, user, assistant):
        messages = (self.messages + [
            {"role": "user", "content": user[:MAX_MESSAGE]},
            {"role": "assistant", "content": assistant[:MAX_MESSAGE]},
        ])[-MAX_CHAT_MESSAGES:]
        self._write(self._chat_file(self.chat_id), messages)
        self.messages = messages

    def notes(self):
        rows = self._read("notes.json", MAX_NOTES * (MAX_NOTE * 6 + 96))
        if not all(isinstance(row, dict) and isinstance(row.get("text"), str)
                   and isinstance(row.get("id"), str) and ID.fullmatch(row["id"]) for row in rows):
            raise ValueError("Invalid local notes.")
        return rows

    def remember(self, note):
        if not note or len(note) > MAX_NOTE:
            raise ValueError(f"Provide a note of 1-{MAX_NOTE} characters.")
        if note == "APPROVE ONCE":
            raise ValueError("Approval phrases are not saved.")
        notes = self.notes()
        for row in notes:
            if note.casefold() == row["text"].casefold():
                return row["id"], False
        if len(notes) >= MAX_NOTES:
            raise ValueError("Note limit reached. Forget a note first.")
        note_id = uuid.uuid4().hex
        self._write("notes.json", notes + [{"id": note_id, "text": note}])
        return note_id, True

    def forget(self, target):
        target = target.casefold()
        notes = self.notes()
        matches = [row for row in notes if target in (row["id"], row["text"].casefold())]
        if len(matches) != 1:
            raise ValueError("No unique match. Use a note ID from /memories or its exact text.")
        self._write("notes.json", [row for row in notes if row != matches[0]])

    def context(self, include_history=True):
        # A text-only call gets bounded excerpts, not executable messages or tool records.
        notes = []
        history = []
        for row in reversed(self.notes()):
            item = row["text"][:250]
            if len(json.dumps([item] + notes, ensure_ascii=False)) > MAX_CONTEXT // 3:
                break
            notes.insert(0, item)
        if include_history:
            for row in reversed(self.messages[-12:]):
                item = {"speaker": row["role"], "text": row["content"][:450]}
                if len(json.dumps([item] + history, ensure_ascii=False)) > MAX_CONTEXT * 2 // 3:
                    break
                history.insert(0, item)
        return json.dumps({"notes": notes, "history": history}, ensure_ascii=False) if notes or history else ""


def command(state, prompt):
    """Handle only direct terminal input. Return None when input is not a command."""
    value = prompt.strip()
    lower = value.casefold()
    if lower == "/new":
        state.new()
        return "New chat."
    if lower == "/chats":
        return "\n".join(f"{chat_id}  {title}" for chat_id, title in state.chats()) or "No saved chats."
    if lower.startswith("/open "):
        state.open(value[6:].strip())
        return "\n".join(f"{row['role']}: {row['content']}" for row in state.messages)
    if lower.startswith("/delete "):
        state.delete(value[8:].strip())
        return "Chat deleted."
    if lower == "/memories":
        return "\n".join(f"{row['id']}  {row['text']}" for row in state.notes()) or "No saved notes."
    if lower.startswith("remember this:"):
        note_id, added = state.remember(value[len("remember this:"):].strip())
        return ("Saved locally: " if added else "Already saved: ") + note_id
    if lower.startswith(("forget ", "forget:")):
        state.forget(value[7:].strip())
        return "Note removed. Saved chats are unchanged."
    return None


TEST_REPLY = "Signal received from the other side. Something knocked back. ☕"
FAVORITE_COLOR_REPLY = "Crimson. It’s the only color that makes it through the portal intact."
FAVORITE_QUESTION = re.compile(
    r"(?:what(?:['’]s| is) your )?favou?rite (colou?r|food or drink|food|drink|drug|weather|time of day|exact time|clock time|hour)"
)
PET_PEEVE_QUESTION = re.compile(r"(?:what(?:['’]s| is) your )?(?:biggest )?pet peeve")


def device_date_context():
    return (
        f"\nThe device's local date is {date.today().isoformat()}. This gives the date only. It does not verify current events. "
        "For facts that can change, use a reliable dated local reference if available. "
        "State the fact as of the reference date, separate from the device date, and say you cannot verify that it is still current. "
        "If no reliable dated reference is available, say you cannot verify. Do not guess or invent a source or date. "
        "The app update date is not a reference."
    )


def direct_response(prompt):
    value = " ".join(prompt.casefold().split())
    if value == "test":
        return TEST_REPLY
    question = value.rstrip("?!.")
    if question in {"what is today's date", "what's today's date", "what is the date",
                    "what's the date", "what is the date today", "what's the date today",
                    "what day is it", "what day is it today", "what is today’s date",
                    "what’s today’s date", "today's date", "today’s date"}:
        return f"Today is {date.today().isoformat()}."
    if question in {"what year is it", "what is the current year",
                    "what's the current year", "what’s the current year"}:
        return f"The current year is {date.today().year}."
    if PET_PEEVE_QUESTION.fullmatch(question):
        return "Decaf."
    if question == "where are you from":
        return "The side of the mirror that stays warm."
    if question in {"what exact time is your favorite", "what exact time is your favourite"}:
        return "Midnight."
    match = FAVORITE_QUESTION.fullmatch(question)
    if not match:
        return None
    topic = match[1]
    if topic in {"color", "colour"}:
        return FAVORITE_COLOR_REPLY
    if topic == "weather":
        return "Fog."
    if topic == "time of day":
        return "Night."
    if topic in {"exact time", "clock time", "hour"}:
        return "Midnight."
    return "Caffeine." if topic == "drug" else "Coffee."


def advisory_mode(prompt):
    value = prompt.strip()
    lower = value.casefold()
    for prefix, kind in (("just the diff", "diff"), ("let's talk", "talk"), ("let’s talk", "talk")):
        if lower == prefix or lower.startswith((prefix + ":", prefix + " ")):
            return kind, value[len(prefix):].lstrip(": ").strip()
    return None, prompt


def advisory_instruction(mode):
    if mode == "diff":
        return " Give only the proposed diff. Do not claim to have edited a file."
    if mode == "talk":
        return " Discuss options. Do not make changes or claim to have acted."
    return ""


def missing_advice_topic(mode):
    return "Add what you’d like to " + ("see a diff for." if mode == "diff" else "talk through.")
