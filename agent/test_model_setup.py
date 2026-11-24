import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest

import model_setup


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.destination = self.root / "models"
        self.source = self.root / "fixture.gguf"
        self.body = b"a pretend garden model"
        self.source.write_bytes(self.body)
        self.spec = model_setup.ModelSpec("fern.gguf", len(self.body),
                                           hashlib.sha256(self.body).hexdigest())
        self.stop = Event()

    def import_file(self, progress=lambda *_: None):
        return model_setup.import_model(self.source, self.destination, self.stop, progress, self.spec)

    def test_verifies_and_promotes_the_pinned_local_file(self):
        progress = []
        path = self.import_file(lambda *args: progress.append(args))
        self.assertEqual(path.read_bytes(), self.body)
        self.assertEqual(self.source.read_bytes(), self.body)
        self.assertEqual(progress[-1], (len(self.body), len(self.body)))
        self.assertTrue(model_setup.verify(path, self.stop, self.spec))
        self.assertFalse(list(self.destination.glob("*.part")))

    def test_bad_files_are_not_installed_and_do_not_replace_existing_model(self):
        self.destination.mkdir()
        existing = self.destination / self.spec.filename
        existing.write_bytes(b"previous version")
        for body in (b"x" * len(self.body), self.body[:-1]):
            self.source.write_bytes(body)
            with self.assertRaises(ValueError):
                self.import_file()
            self.assertEqual(existing.read_bytes(), b"previous version")
            self.assertFalse(list(self.destination.glob("*.part")))

    def test_cancel_cleans_partial_and_allows_retry(self):
        with self.assertRaises(model_setup.Canceled):
            self.import_file(lambda *_: self.stop.set())
        self.assertFalse(list(self.destination.iterdir()))
        self.stop.clear()
        self.assertTrue(self.import_file().exists())

    def test_desktop_first_launch_uses_bundled_model_without_user_input(self):
        from unittest.mock import patch
        import desktop

        self.destination.mkdir()
        expected = self.destination / self.spec.filename
        expected.write_bytes(self.body)
        with patch.object(desktop, "ASSETS", self.root / "assets"), \
                patch.object(desktop, "require_avx2"), \
                patch.object(desktop, "LocalServer") as server, \
                patch.object(model_setup, "MODEL", self.spec), \
                patch.object(model_setup, "import_model", side_effect=AssertionError("unexpected import")):
            worker = desktop.Worker(installed=True)
            try:
                self.assertEqual(worker.outbox.get(timeout=3), ("status", "Verifying the bundled model…"))
                self.assertEqual(worker.outbox.get(timeout=3), ("status", "Starting the local model…"))
                self.assertEqual(worker.outbox.get(timeout=3)[0], "ready")
                self.assertEqual(server.call_args.kwargs["model_path"], expected)
            finally:
                worker.close()
                worker.thread.join(3)
            self.assertFalse(worker.thread.is_alive())

    def test_bundled_build_refuses_missing_or_corrupt_model_without_fallback(self):
        from unittest.mock import patch
        import desktop

        with patch.object(desktop, "ASSETS", self.root / "assets"), \
                patch.object(desktop, "require_avx2"), \
                patch.object(desktop, "LocalServer") as server, \
                patch.object(model_setup, "MODEL", self.spec):
            self.destination.mkdir()
            target = self.destination / self.spec.filename
            for case in ("missing", "corrupt"):
                with self.subTest(case=case):
                    if case == "corrupt":
                        target.write_bytes(b"x" * len(self.body))
                    worker = desktop.Worker(installed=True)
                    try:
                        self.assertEqual(worker.outbox.get(timeout=3)[0], "status")
                        kind, message = worker.outbox.get(timeout=3)
                        self.assertEqual(kind, "fatal")
                        self.assertIn("Reinstall Frankesso", message)
                        server.assert_not_called()
                    finally:
                        worker.close()
                        worker.thread.join(3)
