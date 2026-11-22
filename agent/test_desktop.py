import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import struct
from threading import Event

import agent
import desktop
import install_desktop
import run_agent
from run_agent import LocalServer


class DesktopTests(unittest.TestCase):
    def test_multiturn_context_is_local_text_only(self):
        local_model = Mock(return_value={"content": "Use clay pots."})
        chat = desktop.Chat(local_model)
        self.assertEqual(chat.ask("What should I use for basil?"), "Use clay pots.")
        chat.ask("How should I label them?")
        messages = local_model.call_args.args[0]
        self.assertEqual(messages[-3]["content"], "What should I use for basil?")
        self.assertEqual(local_model.call_args.kwargs, {"tools_enabled": False})
        local_model.return_value = {"tool_calls": [{"name": "web_search"}]}
        self.assertIn("No action taken", chat.ask("Look up herb prices."))
        self.assertEqual(len(chat.history), 2)

    def test_context_and_input_are_bounded(self):
        local_model = Mock(return_value={"content": "Try a small fern."})
        chat = desktop.Chat(local_model)
        for _ in range(10):
            chat.ask("Plan a window planter. " * 70)
        self.assertEqual(len(chat.history), 6)
        self.assertLessEqual(sum(len(message["content"]) for message in local_model.call_args.args[0][1:-1]),
                             desktop.MAX_CONTEXT)
        with self.assertRaises(ValueError):
            chat.ask("x" * (desktop.MAX_PROMPT + 1))

    def test_http_request_stays_on_loopback_without_tools(self):
        with patch.object(agent.http.client, "HTTPConnection") as connect:
            response = connect.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"choices":[{"message":{"content":"A fern."}}]}'
            desktop.Chat().ask("Plan a window planter.")
            connect.assert_called_once_with("127.0.0.1", agent.PORT, timeout=180)
            payload = json.loads(connect.return_value.request.call_args.args[2])
            self.assertNotIn("tools", payload)
            self.assertNotIn("tool_choice", payload)

    def test_cancel_only_terminates_owned_process(self):
        stopped = Event()
        server = LocalServer(Path("."), stop=stopped)
        server.process = Mock()
        server.process.poll.return_value = None
        server.cancel()
        self.assertTrue(stopped.is_set())
        server.process.terminate.assert_called_once_with()

    @patch.object(run_agent.subprocess, "Popen")
    @patch.object(run_agent.socket, "socket")
    def test_occupied_port_does_not_launch_or_take_over(self, socket, launch):
        check = socket.return_value.__enter__.return_value
        check.connect_ex.return_value = 0
        with self.assertRaisesRegex(RuntimeError, "already in use"):
            with LocalServer(Path(".")):
                self.fail("Unexpected startup")
        check.connect_ex.assert_called_once_with(("127.0.0.1", agent.PORT))
        launch.assert_not_called()

    def test_icon_wraps_existing_bunny_asset(self):
        icon = (desktop.ASSETS / "frankesso.ico").read_bytes()
        self.assertEqual(struct.unpack("<HHH", icon[:6]), (0, 1, 1))
        size, offset = struct.unpack("<II", icon[14:22])
        self.assertEqual(size, len(icon[offset:]))
        self.assertEqual(icon[offset:], (desktop.ASSETS / "frankesso-favicon.png").read_bytes())

    @patch.object(install_desktop.subprocess, "run")
    @patch.object(install_desktop.sys, "platform", "win32")
    @patch.dict(install_desktop.os.environ, {"SystemRoot": "C:/Windows"})
    def test_shortcut_removal_targets_current_users_start_menu(self, invoke):
        install_desktop.run(remove=True)
        command = invoke.call_args.args[0]
        self.assertIn("GetFolderPath('Programs')", command[-1])
        self.assertIn("Frankesso.lnk", command[-1])
        self.assertEqual(invoke.call_args.kwargs["env"]["FRANKESSO_SHORTCUT_REMOVE"], "1")
        self.assertTrue(invoke.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
