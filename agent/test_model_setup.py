import hashlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from urllib.request import Request

import model_setup


class Response(io.BytesIO):
    def __init__(self, data, reported=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if reported is None else reported)}


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.body = b"a pretend garden model"
        self.spec = model_setup.ModelSpec("fern.garden", "https://huggingface.co/fixture",
                                          len(self.body), hashlib.sha256(self.body).hexdigest())
        self.stop = Event()

    def download(self, fetch, progress=lambda *_: None):
        return model_setup.download(self.root, self.stop, progress, self.spec, fetch)

    def test_verifies_and_promotes_the_pinned_file(self):
        def fetch(url):
            self.assertEqual(url, self.spec.url)
            return Response(self.body)
        progress = []
        path = self.download(fetch, lambda *args: progress.append(args))
        self.assertEqual(path.read_bytes(), self.body)
        self.assertEqual(progress[-1], (len(self.body), len(self.body)))
        self.assertTrue(model_setup.verify(path, self.stop, self.spec))
        self.assertFalse(any(self.root.glob("*.part")))

    def test_corrupt_or_incomplete_files_are_not_installed(self):
        existing = self.root / self.spec.filename
        existing.write_bytes(b"previous version")
        for response in (Response(b"x" * len(self.body)), Response(self.body[:-1], reported=len(self.body))):
            with self.assertRaisesRegex(ValueError, "failed verification"):
                self.download(lambda _: response)
            self.assertEqual(existing.read_bytes(), b"previous version")
            self.assertFalse(any(self.root.glob("*.part")))

    def test_cancel_cleans_partial_and_allows_retry(self):
        with self.assertRaises(model_setup.Canceled):
            self.download(lambda _: Response(self.body), lambda *_: self.stop.set())
        self.assertFalse(list(self.root.iterdir()))
        self.stop.clear()
        self.assertTrue(self.download(lambda _: Response(self.body)).exists())

    def test_rejects_non_hf_or_non_https_redirect(self):
        redirect = model_setup.HTTPSModelRedirects()
        origin = Request(self.spec.url)
        for url in ("http://hf.co/file", "https://other.invalid/file", "https://huggingface.co:444/file",
                    "https://huggingface.co.other.invalid/file", "https://user@huggingface.co/file"):
            with self.assertRaises(ValueError):
                redirect.redirect_request(origin, None, 302, "", {}, url)
        accepted = redirect.redirect_request(origin, None, 302, "", {}, "https://cdn.hf.co/file")
        self.assertEqual(accepted.host, "cdn.hf.co")


if __name__ == "__main__":
    unittest.main()
