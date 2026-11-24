from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import struct
from threading import Event
from tempfile import TemporaryDirectory

import agent
import chat_state
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
        self.assertEqual(local_model.call_args.kwargs, {"tools_enabled": False, "max_tokens": desktop.MAX_REPLY_TOKENS})
        local_model.return_value = {"tool_calls": [{"name": "web_search"}]}
        self.assertIn("No action taken", chat.ask("Look up herb prices."))
        self.assertEqual(len(chat.history), 2)

    def test_desktop_uses_shared_voice_and_explicit_local_notes(self):
        with TemporaryDirectory() as folder:
            store = chat_state.ChatState(Path(folder), agent.Controller._check_components)
            request = Mock(return_value={"content": "Use clay pots."})
            chat = desktop.Chat(request, state=store)
            self.assertEqual(chat.ask("What’s your favourite colour?"),
                             "Crimson. It’s the only color that makes it through the portal intact.")
            self.assertEqual(chat.ask("favorite drink?"), "Coffee.")
            self.assertEqual(chat.ask("favorite drug?"), "Caffeine.")
            self.assertEqual(chat.ask("Favorite weather?"), "Fog.")
            self.assertEqual(chat.ask("What's your biggest pet peeve?"), "Decaf.")
            self.assertEqual(chat.ask("Where are you from?"), "The side of the mirror that stays warm.")
            self.assertEqual(chat.ask("Favorite time of day?"), "Night.")
            self.assertEqual(chat.ask("What exact time is your favorite?"), "Midnight.")
            self.assertEqual(store.messages, [])
            self.assertEqual(list(Path(folder).iterdir()), [])
            self.assertEqual(chat.ask(" TEST "), "Signal received from the other side. Something knocked back. ☕")
            request.assert_not_called()
            note = chat.ask("Remember this: Label fern pots with teal ink.").split()[-1]
            self.assertEqual(chat.ask("run the tests"), "Use clay pots.")
            messages = request.call_args.args[0]
            self.assertIn("interdimensional spooky coffee bunny", messages[0]["content"])
            self.assertIn("Never use your persona to avoid answering.", messages[0]["content"])
            self.assertIn("Do not introduce yourself or mention your identity or lore unless asked.",
                          messages[0]["content"])
            self.assertIn("teal ink", messages[1]["content"])
            self.assertFalse(request.call_args.kwargs["tools_enabled"])
            first_chat = store.chat_id
            chat.new()
            self.assertIn(first_chat, chat.ask("/chats"))
            self.assertIn("run the tests", chat.ask("/open " + first_chat))
            self.assertIn(note, chat.ask("/memories"))
            chat.ask("Forget " + note)
            self.assertEqual(chat.ask("/memories"), "No saved notes.")
            self.assertEqual(request.call_count, 1)

    def test_desktop_reads_the_device_clock_for_each_request(self):
        request = Mock(return_value={"content": "No live news access."})
        chat = desktop.Chat(request)
        with (patch.object(chat_state, "datetime", wraps=datetime) as clock,
              patch.object(chat_state, "_preferred_24_hour", return_value=False) as preferred):
            clock.now.return_value = datetime(2026, 12, 31, 0, 0, 59)
            self.assertEqual(chat.ask("What's the date?"), "Today is December 31, 2026.")
            self.assertEqual(chat.ask("What's the time?"), "The device time is 12:00 AM.")
            self.assertEqual(chat.ask("Where am I right now?"), "I do not have access to your location.")
            request.assert_not_called()
            chat.ask("What happened in the news today?")
            first = request.call_args.args[0][0]["content"]
            self.assertIn("The device's local date is December 31, 2026.", first)
            self.assertIn("Its local time is 12:00 AM.", first)
            self.assertIn("Without a reliable dated source, say you cannot verify time-sensitive facts.", first)
            clock.now.return_value = datetime(2027, 1, 1, 12, 59, 59)
            self.assertEqual(chat.ask("What's the time?"), "The device time is 12:59 PM.")
            preferred.return_value = True
            self.assertEqual(chat.ask("What\'s the time?"), "The device time is 12:59.")
            chat.ask("What happened in the news today?")
            second = request.call_args.args[0][0]["content"]
            self.assertIn("The device's local date is January 1, 2027.", second)
            self.assertNotIn("December 31, 2026", second)

    def test_desktop_rejects_tool_calls_even_with_saved_context(self):
        with TemporaryDirectory() as folder:
            store = chat_state.ChatState(Path(folder), agent.Controller._check_components)
            store.remember("Check which pots need water.")
            request = Mock(return_value={"tool_calls": [{"name": "web_search"}]})
            chat = desktop.Chat(request, state=store)
            self.assertIn("No action taken", chat.ask("What should we do?"))
            self.assertEqual(store.messages, [])
            self.assertFalse(request.call_args.kwargs["tools_enabled"])

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
            self.assertEqual(payload.get("max_tokens"), desktop.MAX_REPLY_TOKENS)
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

    @patch.object(run_agent.subprocess, "Popen")
    @patch.object(run_agent.socket, "socket")
    def test_packaged_startup_skips_warmup_and_retains_failure_diagnostics(self, socket, launch):
        socket.return_value.__enter__.return_value.connect_ex.return_value = 1
        def process(*args, **kwargs):
            self.assertIn("--no-warmup", args[0])
            kwargs["stderr"].write("synthetic garden runtime failed\n")
            kwargs["stderr"].flush()
            result = Mock(returncode=7)
            result.poll.return_value = 7
            return result
        launch.side_effect = process
        server = LocalServer(Path("."), skip_warmup=True)
        with self.assertRaisesRegex(RuntimeError, "exited"):
            with server:
                self.fail("Unexpected startup")
        self.assertIn("synthetic garden runtime failed", server.startup_log)
        self.assertFalse(server.log_path.exists())

    def test_system_theme_updates_without_manual_override(self):
        root = Mock()
        render = Mock()
        read = Mock(side_effect=["light", "dark", "dark", "light"])
        desktop.watch_system_theme(root, "light", render, read)
        for _ in range(4):
            delay, callback = root.after.call_args.args
            self.assertEqual(delay, 1000)
            callback()
        self.assertEqual([call.args[0] for call in render.call_args_list], ["dark", "light"])

    def test_dark_theme_uses_the_inverse_palette(self):
        root, ttk = Mock(), Mock()
        desktop.apply_chat_theme(root, ttk, "dark")
        root.configure.assert_called_once_with(background="#0A0909")
        styles = {call.args[0]: call.kwargs for call in ttk.Style.return_value.configure.call_args_list}
        self.assertEqual(styles["Frankesso.TLabel"]["foreground"], "#FAF2E4")
        primary = styles["Frankesso.Primary.TButton"]
        self.assertEqual((primary["background"], primary["foreground"]), ("#FAF2E4", "#0A0909"))
        self.assertEqual(desktop.chat_text_colors("dark")["background"], "#0A0909")

    def test_progressive_test_and_model_replies_follow_same_history_commit(self):
        with TemporaryDirectory() as folder:
            store = chat_state.ChatState(Path(folder), agent.Controller._check_components)
            wanted = "Signal received from the other side. Something knocked back. ☕"
            request = Mock(return_value={"content": "Plant a fern. 🌿"})
            chat = desktop.Chat(request, state=store)
            self.assertEqual(chat.ask("test", defer_history=True), wanted)
            self.assertEqual("".join(desktop.reveal_chunks(wanted)), wanted)
            self.assertEqual(list(desktop.reveal_chunks("🌿abcé")), ["🌿abc", "é"])
            chat.finish(False)
            self.assertEqual(store.messages, [])
            request.assert_not_called()
            reply = chat.ask("Name an easy plant.", defer_history=True)
            self.assertEqual("".join(desktop.reveal_chunks(reply)), "Plant a fern. 🌿")
            self.assertEqual(store.messages, [])
            chat.finish(True)
            self.assertEqual(store.messages[-1]["content"], "Plant a fern. 🌿")
            self.assertEqual((desktop.REPLY_INTERVAL_MS, desktop.REPLY_STEP), (30, 4))

    def test_windows_content_uses_shared_cream_palette(self):
        root, ttk = Mock(), Mock()
        desktop.apply_chat_theme(root, ttk)
        root.configure.assert_called_once_with(background="#FAF2E4")
        styles = {call.args[0]: call.kwargs for call in ttk.Style.return_value.configure.call_args_list}
        primary = styles["Frankesso.Primary.TButton"]
        self.assertEqual((primary["background"], primary["foreground"]), ("#0A0909", "#FAF2E4"))
        self.assertEqual(styles["Frankesso.Secondary.TButton"]["background"], "#FAF2E4")
        self.assertEqual(styles["Frankesso.TLabel"]["foreground"], "#0A0909")
        self.assertEqual(desktop.chat_text_colors()["background"], "#FAF2E4")
        self.assertEqual(desktop.blend(desktop.INK, desktop.CREAM, desktop.DISABLED_LABEL_ALPHA), "#524E4A")

    def test_button_surfaces_have_rounded_page_matte_and_continuous_muted_outline(self):
        import zlib

        def pixels(png):
            width, height = struct.unpack(">II", png[16:24])
            size = struct.unpack(">I", png[33:37])[0]
            data = zlib.decompress(png[41:41 + size])
            return width, height, lambda x, y: tuple(data[y * (width * 4 + 1) + 1 + x * 4:
                                                       y * (width * 4 + 1) + 5 + x * 4])

        for page, text in (desktop.theme_colors("light"), desktop.theme_colors("dark")):
            for primary in (False, True):
                surface = desktop.button_surfaces(page, text, primary)
                width, height, sample = pixels(surface["normal"])
                self.assertEqual((width, height), (desktop.BUTTON_WIDTH, 48))
                self.assertEqual(sample(0, 0), (*desktop.rgb(page), 255))
                self.assertEqual(sample(width // 2, height // 2), (*desktop.rgb(text if primary else page), 255))
                _, _, disabled = pixels(surface["disabled"])
                border = (*desktop.rgb(desktop.blend(text, page, desktop.DISABLED_OUTLINE_ALPHA)), 255)
                for x in range(15, width - 15):
                    self.assertEqual(disabled(x, 0), border)
                self.assertEqual(disabled(0, 0), (*desktop.rgb(page), 255))
                self.assertNotEqual(surface["focus"], surface["normal"])

    def test_chat_panels_have_rounded_surfaces_in_both_themes(self):
        for mode in ("light", "dark"):
            page, foreground = desktop.theme_colors(mode)
            normal = desktop.chat_surface_png(page, foreground)
            composer = desktop.chat_surface_png(page, foreground, input_field=True)
            self.assertNotEqual(normal, composer)
            self.assertEqual(struct.unpack(">II", normal[16:24]), (32, 32))
            self.assertEqual(desktop.CHAT_RADIUS, 10)
            self.assertEqual(desktop.chat_text_colors(mode)["highlightthickness"], 0)
            self.assertEqual(desktop.chat_text_colors(mode)["selectforeground"], page)
    def test_dark_display_uses_a_separate_logo_not_the_native_icon(self):
        self.assertEqual(desktop.theme_brand_asset("light").name, "frankesso-logo.png")
        self.assertEqual(desktop.theme_brand_asset("dark").name, "frankesso-logo-dark.png")

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
