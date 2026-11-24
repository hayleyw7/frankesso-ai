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

    def test_desktop_first_launch_waits_for_local_import_and_does_not_require_network(self):
        from unittest.mock import patch
        import desktop
        import_local_file = model_setup.import_model

        with patch.dict(desktop.os.environ, {"LOCALAPPDATA": str(self.root)}), \
                patch.object(desktop, "require_avx2"), \
                patch.object(desktop, "LocalServer") as server, \
                patch.object(model_setup, "MODEL", self.spec), \
                patch.object(model_setup, "import_model",
                             side_effect=lambda source, dest, stop, progress: import_local_file(source, dest, stop, progress, self.spec)) as importer:
            worker = desktop.Worker(installed=True)
            try:
                self.assertEqual(worker.outbox.get(timeout=3)[0], "needs_model")
                server.assert_not_called()
                worker.inbox.put("https://fixture.invalid/wrong.gguf")
                self.assertEqual(worker.outbox.get(timeout=3)[0], "needs_model")
                importer.assert_not_called()
                worker.inbox.put(str(self.source))
                self.assertEqual(worker.outbox.get(timeout=3)[0], "status")
                self.assertEqual(worker.outbox.get(timeout=3)[0], "progress")
                self.assertEqual(worker.outbox.get(timeout=3)[0], "model_ready")
                self.assertEqual(worker.outbox.get(timeout=3)[0], "ready")
                self.assertEqual(importer.call_args.args[0], self.source)
                self.assertEqual(server.call_args.kwargs["model_path"], self.root / "FrankessoDesktop" / "models" / self.spec.filename)
            finally:
                worker.close()
                worker.thread.join(3)
