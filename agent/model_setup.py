"""Verify and import a pinned, user-supplied local model file."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import tempfile

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ModelSpec:
    filename: str
    size: int
    sha256: str


MODEL = ModelSpec(
    "Qwen3-4B-Q4_K_M.gguf",
    2497280256,
    "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
)


class Canceled(Exception):
    """A local model operation was canceled."""


def check_cancel(stop):
    if stop.is_set():
        raise Canceled()


def verify(path, stop, spec=MODEL):
    check_cancel(stop)
    if not path.is_file() or path.stat().st_size != spec.size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK):
            check_cancel(stop)
            digest.update(chunk)
    check_cancel(stop)
    return digest.hexdigest() == spec.sha256


def import_model(source, directory, stop, progress, spec=MODEL):
    check_cancel(stop)
    source = Path(source)
    if not source.is_file() or source.stat().st_size != spec.size:
        raise ValueError("Choose the complete Qwen3-4B-Q4_K_M.gguf model file.")
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < spec.size + 64 * CHUNK:
        raise OSError("Not enough free space to import the model.")
    destination = directory / spec.filename
    staged = None
    try:
        digest = hashlib.sha256()
        count = 0
        with source.open("rb") as original, tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix="qwen-import-", suffix=".part", delete=False
        ) as out:
            staged = Path(out.name)
            while chunk := original.read(CHUNK):
                check_cancel(stop)
                count += len(chunk)
                if count > spec.size:
                    raise ValueError("The model was larger than expected.")
                out.write(chunk)
                digest.update(chunk)
                progress(count, spec.size)
        check_cancel(stop)
        if count != spec.size or digest.hexdigest() != spec.sha256:
            raise ValueError("The file did not match the expected Qwen model.")
        staged.replace(destination)
        return destination
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
