"""Bounded, offline extraction. Never execute macros, scripts, links or archive members."""
import importlib.util
from pathlib import Path
import re
import wave
import xml.etree.ElementTree as ET
import zipfile

LIMIT = 6000
MAX_FILE = 64 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024


def capabilities():
    return {"office_xml": True, "text": True, "zip_listing": True, "wav_metadata": True,
            "pdf_text": importlib.util.find_spec("pypdf") is not None,
            "image_metadata": importlib.util.find_spec("PIL") is not None,
            "ocr": False, "audio_transcription": False, "legacy_office": False}


def checked_archive(path):
    archive = zipfile.ZipFile(path)
    items = archive.infolist()
    if len(items) > 2000 or sum(i.file_size for i in items) > 32 * 1024 * 1024:
        archive.close()
        raise ValueError("Archive exceeds extraction limits")
    return archive


def xml(archive, name):
    info = archive.getinfo(name)
    if info.file_size > MAX_XML:
        raise ValueError("Document XML part exceeds 2 MiB")
    data = archive.read(name)
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML DTD/entity declarations are not allowed")
    return ET.fromstring(data)


def localtag(element):
    return element.tag.rsplit("}", 1)[-1]


def office(path):
    suffix = path.suffix.lower()
    with checked_archive(path) as archive:
        names = archive.namelist()
        if suffix == ".docx":
            tree = xml(archive, "word/document.xml")
            return "\n".join("".join(n.text or "" for n in p.iter() if localtag(n) == "t")
                             for p in tree.iter() if localtag(p) == "p")
        if suffix in {".odt", ".ods", ".odp"}:
            tree = xml(archive, "content.xml")
            return "\n".join("".join(n.itertext()) for n in tree.iter() if localtag(n) in {"p", "h"})
        if suffix == ".pptx":
            slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                            key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
            chunks = []
            for name in slides[:20]:
                chunks.append(name + "\n" + "\n".join(n.text or "" for n in xml(archive, name).iter() if localtag(n) == "t"))
                if sum(map(len, chunks)) >= LIMIT:
                    break
            return "\n\n".join(chunks)
        if suffix == ".xlsx":
            strings = []
            if "xl/sharedStrings.xml" in names:
                strings = ["".join(n.text or "" for n in item.iter() if localtag(n) == "t")
                           for item in xml(archive, "xl/sharedStrings.xml") if localtag(item) == "si"]
            sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
            chunks = []
            for name in sheets[:10]:
                chunks.append(name)
                for cell in xml(archive, name).iter():
                    if localtag(cell) != "c":
                        continue
                    value = next((n.text or "" for n in cell if localtag(n) == "v"), "")
                    if cell.get("t") == "s" and value.isdigit():
                        value = strings[int(value)] if int(value) < len(strings) else "[invalid string index]"
                    elif cell.get("t") == "inlineStr":
                        value = "".join(n.text or "" for n in cell.iter() if localtag(n) == "t")
                    formula = next((n.text or "" for n in cell if localtag(n) == "f"), None)
                    chunks.append(cell.get("r", "cell") + ": " + value + (" [formula present; cached value only]" if formula else ""))
                    if sum(map(len, chunks)) >= LIMIT:
                        return "\n".join(chunks)
            return "\n".join(chunks)
    raise ValueError("Unsupported Office format")


def read_document(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError("Document is not a regular file under 64 MiB")
    suffix = path.suffix.lower()
    limitation = "Bounded text extraction; formatting and embedded content are omitted."
    if suffix in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        text = office(path)
        limitation += " Macros, links and formulas are never executed. Spreadsheet cells use cached values."
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("PDF library unavailable in this Python; use the bundled-runtime launcher")
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are unsupported; no password guessing is attempted")
        chunks = []
        for page in reader.pages[:5]:
            chunks.append(page.extract_text() or "")
            if sum(map(len, chunks)) >= LIMIT:
                break
        text = "\n".join(chunks)
        limitation = "First five pages at most; text layer only. No OCR, JavaScript or attachment execution."
        if not text.strip():
            limitation += " No extractable text found; this may be a scanned PDF."
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
        try:
            from PIL import Image
        except ImportError:
            raise ValueError("Image metadata library unavailable in this Python; use the bundled-runtime launcher")
        with Image.open(path) as image:
            return {"format": image.format, "width": image.width, "height": image.height,
                    "mode": image.mode, "limitation": "Metadata only; this text model cannot see or OCR the image."}
    elif suffix == ".wav":
        with wave.open(str(path), "rb") as audio:
            return {"channels": audio.getnchannels(), "sample_rate": audio.getframerate(),
                    "seconds": audio.getnframes() / audio.getframerate(), "limitation": "WAV metadata only; no transcription."}
    elif suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            return {"entries": [{"name": i.filename, "bytes": i.file_size} for i in archive.infolist()[:100]],
                    "limitation": "First 100 archive entries only. Nothing extracted or executed."}
    elif suffix in {".txt", ".md", ".csv", ".tsv", ".json", ".jsonl", ".xml", ".html", ".htm", ".log", ".ini", ".toml", ".yaml", ".yml", ".py", ".js", ".ts", ".css", ".sql", ".ps1", ".cmd", ".bat", ".c", ".cpp", ".h", ".rs", ".go"}:
        with path.open("rb") as source:
            raw = source.read(256 * 1024)
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        text = raw.decode(encoding, errors="replace")
        limitation = "Text only; at most the first 256 KiB read. HTML/scripts are never executed."
    else:
        raise ValueError("Unsupported document type. Legacy .doc/.xls/.ppt, OCR, audio transcription and arbitrary binary decoding are not enabled.")
    return {"text": text[:LIMIT], "truncated": len(text) > LIMIT, "limitation": limitation}
