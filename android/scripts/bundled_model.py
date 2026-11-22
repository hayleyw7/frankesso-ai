"""Prepare and verify the exact Qwen asset bundled into the Android APK."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request
from zipfile import ZIP_STORED, ZipFile

NAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
OLD_NAME = "qwen2.5-coder-0.5b-q4_k_m.gguf"
SIZE = 491_400_032
SHA256 = "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
URL = (
    "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    "/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf"
)


def transfer_verified(source, destination=None):
    sha = hashlib.sha256()
    count = 0
    while block := source.read(1024 * 1024):
        count += len(block)
        if count > SIZE:
            raise ValueError("Model bytes exceed the expected size.")
        sha.update(block)
        if destination is not None:
            destination.write(block)
    if count != SIZE or sha.hexdigest() != SHA256:
        raise ValueError("Qwen model size or SHA-256 mismatch.")


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / OLD_NAME).unlink(missing_ok=True)
    target = directory / NAME
    if target.is_file() and target.stat().st_size == SIZE:
        try:
            with target.open("rb") as existing:
                transfer_verified(existing)
            print(f"Reused verified {NAME}.")
            return
        except ValueError:
            pass
    local = os.environ.get("FRANKESSO_MODEL_FILE")
    fd, name = tempfile.mkstemp(prefix=".qwen-", suffix=".part", dir=directory.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            source = Path(local).open("rb") if local else urllib.request.urlopen(URL, timeout=120)
            with source:
                transfer_verified(source, output)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Prepared verified {NAME} ({SIZE:,} bytes).")


def verify_apk(path):
    with ZipFile(path) as apk:
        models = [name for name in apk.namelist() if name.startswith("assets/") and name.endswith(".gguf")]
        if models != [f"assets/{NAME}"]:
            raise ValueError("The APK must contain exactly one bundled model.")
        asset = apk.getinfo(f"assets/{NAME}")
        if asset.file_size != SIZE or asset.compress_type != ZIP_STORED:
            raise ValueError("The APK must contain the exact model as an uncompressed asset.")
        for notice in ("Qwen-Apache-2.0.txt", "Qwen-NOTICE.txt"):
            if not apk.getinfo(f"assets/third-party/{notice}").file_size:
                raise ValueError(f"The APK must include the Qwen license and attribution: {notice}")
        with apk.open(asset) as source:
            transfer_verified(source)
    print(f"Verified bundled GGUF ({SIZE:,} bytes), SHA-256 {SHA256}, and notices.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify-apk"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else verify_apk)(args.path)


if __name__ == "__main__":
    main()
