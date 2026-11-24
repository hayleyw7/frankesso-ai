"""Prepare and verify the exact Qwen asset bundled into the Android APK."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request
from zipfile import ZIP_STORED, ZipFile

NAME = "Qwen3-4B-Q4_K_M.gguf"
PARTS = tuple(f"{NAME}.{index}.part" for index in range(3))
PART_SIZE = 900_000_000
SIZE = 2_497_280_256
SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
URL = (
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF"
    "/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf"
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
    local = os.environ.get("FRANKESSO_MODEL_FILE")
    fd, name = tempfile.mkstemp(prefix=".qwen-", suffix=".part", dir=directory.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            source = Path(local).open("rb") if local else urllib.request.urlopen(URL, timeout=120)
            with source:
                transfer_verified(source, output)
        with temporary.open("rb") as source:
            for part in PARTS:
                target = directory / part
                with target.open("wb") as output:
                    remaining = PART_SIZE
                    while remaining and (block := source.read(min(remaining, 1024 * 1024))):
                        output.write(block)
                        remaining -= len(block)
        print(f"Prepared verified {NAME} ({SIZE:,} bytes) as three APK assets.")
    finally:
        temporary.unlink(missing_ok=True)


def verify_apk(path, destination=None):
    with ZipFile(path) as apk:
        models = [name for name in apk.namelist()
                  if name.startswith("assets/") and ".gguf" in name]
        if sorted(models) != [f"assets/{name}" for name in PARTS]:
            raise ValueError("The APK must contain exactly the three expected model parts.")
        for index, part in enumerate(PARTS):
            asset = apk.getinfo(f"assets/{part}")
            if asset.file_size != min(PART_SIZE, SIZE - index * PART_SIZE) or asset.compress_type != ZIP_STORED:
                raise ValueError(f"Model part must be stored and have the expected size: {part}")
        for notice in ("Qwen-Apache-2.0.txt", "Qwen-NOTICE.txt"):
            if not apk.getinfo(f"assets/third-party/{notice}").file_size:
                raise ValueError(f"The APK must include the Qwen license and attribution: {notice}")
        digest = hashlib.sha256()
        count = 0
        for part in PARTS:
            with apk.open(f"assets/{part}") as source:
                while block := source.read(1024 * 1024):
                    digest.update(block)
                    count += len(block)
                    if destination is not None:
                        destination.write(block)
        if count != SIZE or digest.hexdigest() != SHA256:
            raise ValueError("The combined model SHA-256 is incorrect.")
    print(f"Verified bundled GGUF ({SIZE:,} bytes), SHA-256 {SHA256}, and notices.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify-apk"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--extract-to", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.path)
    elif args.extract_to:
        with args.extract_to.open("wb") as output:
            verify_apk(args.path, output)
    else:
        verify_apk(args.path)


if __name__ == "__main__":
    main()
