from datetime import datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from threading import Event
import unittest
from unittest.mock import patch

import chat_state
import desktop
import macos_desktop
import run_agent


class MacDesktopTests(unittest.TestCase):
    def test_drag_install_path_with_spaces(self):
        app = Path("/Applications/Frankesso Local.app/Contents")
        self.assertEqual(macos_desktop.bundle_runtime(app / "MacOS" / "Frankesso"),
                         app / "Resources" / "FrankessoRuntime")
        with self.assertRaisesRegex(RuntimeError, "Frankesso.app"):
            macos_desktop.bundle_runtime("/usr/bin/python3")

    def test_uses_mac_app_support_and_not_windows_state(self):
        with patch.object(chat_state.sys, "platform", "darwin"), \
                patch.object(Path, "home", return_value=Path("/Users/example")), \
                patch.dict(os.environ, LOCALAPPDATA="/wrong"):
            self.assertEqual(chat_state.state_root(),
                             Path("/Users/example/Library/Application Support/Frankesso/chat-state"))

    def test_bundled_mac_worker_uses_local_model_without_windows_cpu_probe(self):
        with TemporaryDirectory() as folder, \
                patch.object(desktop, "require_avx2", side_effect=AssertionError("Windows-only")), \
                patch.object(desktop, "LocalServer") as local_server, \
                patch.object(desktop.Worker, "bundled_model") as bundled:
            runtime = Path(folder)
            bundled.return_value = runtime / "models" / "local.gguf"
            with patch.object(chat_state, "state_root", return_value=runtime / "chat-state"):
                worker = desktop.Worker(installed=True, package_root=runtime)
                try:
                    self.assertEqual(worker.outbox.get(timeout=2), ("ready", desktop.READY))
                    bundled.assert_called_once_with(runtime)
                    self.assertEqual(local_server.call_args.args, (runtime,))
                    self.assertEqual(local_server.call_args.kwargs["model_path"], bundled.return_value)
                    self.assertIsInstance(local_server.call_args.kwargs["stop"], Event)
                finally:
                    worker.close()
                    worker.thread.join(timeout=2)

    @unittest.skipUnless(sys.platform == "darwin", "requires Core Foundation")
    def test_native_clock_preference_drives_exact_answer(self):
        uses_24_hour = chat_state._apple_uses_24_hour()
        self.assertIsInstance(uses_24_hour, bool)
        with patch.object(chat_state, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 11, 24, 16, 43, 59)
            expected_time = "16:43" if uses_24_hour else "4:43 PM"
            self.assertEqual(desktop.Chat().ask("What time exactly?"),
                             f"The device time is {expected_time}.")

    def test_macos_loader_environment_is_sanitized(self):
        self.assertEqual(run_agent.server_environment(
            {"HOME": "/Users/example", "DYLD_INSERT_LIBRARIES": "x", "LLAMA_ARG_HOST": "x"}),
            {"HOME": "/Users/example"})


if __name__ == "__main__":
    unittest.main()
