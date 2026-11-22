"""First-launch installer for one pinned public model. No chat data enters this module."""
from dataclasses import dataclass
from http.client import HTTPException
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ModelSpec:
    filename: str
    url: str
    size: int
    sha256: str


MODEL = ModelSpec(
    "Qwen3-4B-Q4_K_M.gguf",
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/"
    "bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf",
    2497280256,
    "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
)


class Canceled(Exception):
    """A download or local verification was canceled."""


def check_cancel(stop):
    if stop.is_set():
        raise Canceled()


class HTTPSModelRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        host = target.hostname or ""
        if (target.scheme != "https" or target.username or target.password or
                target.port not in (None, 443) or not (
                    host == "huggingface.co" or host.endswith((".huggingface.co", ".hf.co")))):
            raise ValueError("The download server redirected outside Hugging Face.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_model(url):
    # Keep download separate from chat; don't attach account or environment credentials.
    opener = build_opener(ProxyHandler({}), HTTPSHandler(), HTTPSModelRedirects())
    return opener.open(Request(url, headers={"User-Agent": "Frankesso-Model-Setup",
                                            "Accept-Encoding": "identity"}), timeout=12)


def verify(path, stop, spec=MODEL):
    check_cancel(stop)
    if not path.is_file() or path.stat().st_size != spec.size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK):
            check_cancel(stop)
            digest.update(chunk)
    return digest.hexdigest() == spec.sha256


def download(directory, stop, progress, spec=MODEL, fetch=open_model):
    check_cancel(stop)
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < spec.size + 64 * CHUNK:
        raise OSError("Not enough free disk space for the model. Free at least 2.6 GB and try again.")
    destination = directory / spec.filename
    staged = None
    try:
        with fetch(spec.url) as response:
            if response.headers.get("Content-Length") not in (None, str(spec.size)):
                raise ValueError("The server reported an unexpected file size.")
            digest = hashlib.sha256()
            count = 0
            with tempfile.NamedTemporaryFile(mode="wb", dir=directory,
                                             prefix="qwen-download-", suffix=".part", delete=False) as out:
                staged = Path(out.name)
                while True:
                    check_cancel(stop)
                    chunk = response.read1(CHUNK)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > spec.size:
                        raise ValueError("The model was larger than expected.")
                    out.write(chunk)
                    digest.update(chunk)
                    progress(count, spec.size)
        check_cancel(stop)
        if count != spec.size or digest.hexdigest() != spec.sha256:
            raise ValueError("The downloaded model failed verification. Try downloading it again.")
        staged.replace(destination)
        return destination
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
