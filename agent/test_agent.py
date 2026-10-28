import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent
from run_agent import server_environment


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agent-test-")
        self.root = Path(self.tmp.name)
        self.file = self.root / "note.txt"
        self.file.write_text("apricot 527\n", encoding="utf-8", newline="")
        self.decisions = []
        self.prompts = []
        self.web_calls = []
        def approval(action, details):
            self.prompts.append((action, details))
            return self.decisions.pop(0)
        def broker(query):
            self.web_calls.append(query)
            return {"simulation": True}
        self.controller = agent.Controller(self.root, approval, broker)

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_list_search(self):
        self.assertEqual(self.controller.execute("read_file", {"path": "note.txt"})["content"], "apricot 527\n")
        self.assertIn("note.txt", self.controller.execute("list_files", {"path": "."})["files"])
        self.assertEqual(len(self.controller.execute("search_files", {"path": ".", "query": "apricot"})["matches"]), 1)

    def test_denied_then_approved_write(self):
        self.decisions = [False, True]
        self.assertTrue(self.controller.execute("write_file", {"path": "note.txt", "content": "new"})["denied"])
        self.assertEqual(self.file.read_text(), "apricot 527\n")
        result = self.controller.execute("write_file", {"path": "note.txt", "content": "new"})
        self.assertTrue(result["changed"])
        self.assertEqual(Path(result["backup"]).read_text(), "apricot 527\n")
        self.assertEqual(self.file.read_text(), "new")
        self.assertEqual(len(self.prompts), 2)

    def test_web_requires_approval_every_time(self):
        self.decisions = [False, True, False]
        for _ in range(3):
            self.controller.execute("web_search", {"query": "test only"})
        self.assertEqual(self.web_calls, ["test only"])
        self.assertEqual(len(self.prompts), 3)

    def test_path_escape_and_devices(self):
        for path in ["../outside", "..\\outside", "C:\\Windows\\win.ini", "\\\\host\\share", "note.txt:stream", "NUL", "CON.txt", "foo.", "foo "]:
            with self.subTest(path=path):
                self.assertIn("error", self.controller.execute("read_file", {"path": path}))

    def test_reparse_rejected(self):
        real = Path.lstat
        def altered(path):
            if path == self.file:
                return type("Info", (), {"st_mode": 0o100644, "st_file_attributes": 0x400})()
            return real(path)
        with patch.object(Path, "lstat", altered):
            self.assertIn("error", self.controller.execute("read_file", {"path": "note.txt"}))

    def test_unknown_tools_and_arguments(self):
        for name, args in [("exec_shell_command", {"command": "curl example.com"}), ("read_file", {"path": "note.txt", "approved": True}), ("web_search", {"query": 1})]:
            self.assertIn("error", self.controller.execute(name, args))

    def test_explicit_local_root_and_approved_edit(self):
        with tempfile.TemporaryDirectory(prefix="agent-approved-test-") as approved:
            target = Path(approved) / "fixture.txt"
            target.write_text("approved fixture", encoding="utf-8")
            self.assertIn("error", self.controller.execute("read_file", {"path": str(target)}))
            scoped = agent.Controller(self.root, lambda *_: False, approved_roots=[approved])
            self.assertEqual(scoped.execute("read_file", {"path": str(target)})["content"], "approved fixture")
            self.assertTrue(scoped.execute("write_file", {"path": str(target), "content": "changed"})["denied"])
            self.assertEqual(target.read_text(), "approved fixture")

    def test_binary_and_size_limits(self):
        self.file.write_bytes(b"\x00binary")
        self.assertIn("error", self.controller.execute("read_file", {"path": "note.txt"}))
        self.file.write_bytes(b"x" * (agent.MAX_BYTES + 1))
        self.assertIn("error", self.controller.execute("read_file", {"path": "note.txt"}))

    def test_approval_rechecks_content(self):
        def edit_during_approval(*_):
            self.file.write_text("changed externally")
            return True
        self.controller.approval = edit_during_approval
        result = self.controller.execute("write_file", {"path": "note.txt", "content": "replace"})
        self.assertIn("error", result)
        self.assertEqual(self.file.read_text(), "changed externally")

    def test_malformed_model_call_does_not_execute(self):
        responses = iter([{"tool_calls": [{"id": "a", "function": {"name": "write_file", "arguments": "not JSON"}}]}, {"content": "Stopped"}])
        self.assertEqual(self.controller.turn("test", lambda _: next(responses)), "Stopped")
        self.assertEqual(self.prompts, [])

    def test_inherited_server_tools_cannot_bypass_controller(self):
        result = server_environment({"PATH": "test-path", "LLAMA_ARG_TOOLS": "exec_shell_command",
                                     "LLAMA_ARG_MCP_SERVERS_JSON": "unapproved", "llama_arg_host": "0.0.0.0"})
        self.assertEqual(result, {"PATH": "test-path"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
