from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile

import document_readers as readers


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agent-doc-test-")
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def archive(self, name, members):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            for key, value in members.items():
                archive.writestr(key, value)
        return path

    def test_docx_offline_no_external_relationships(self):
        path = self.archive("sample.docx", {"word/document.xml": '<document><p><r><t>Offline document fixture</t></r></p></document>',
            "word/_rels/document.xml.rels": '<Relationships><Relationship Target="https://example.com" TargetMode="External"/></Relationships>'})
        with patch("socket.getaddrinfo", side_effect=AssertionError("No DNS allowed")):
            self.assertEqual(readers.read_document(path)["text"], "Offline document fixture")

    def test_xlsx_cached_formula_no_execution(self):
        path = self.archive("sample.xlsx", {"xl/sharedStrings.xml": '<sst><si><t>Apricot</t></si></sst>',
            "xl/worksheets/sheet1.xml": '<worksheet><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>'})
        text = readers.read_document(path)["text"]
        self.assertIn("A1: Apricot", text)
        self.assertIn("B1: 2 [formula present; cached value only]", text)

    def test_pptx_and_opendocument(self):
        pptx = self.archive("sample.pptx", {"ppt/slides/slide1.xml": '<slide><t>Slide fixture</t></slide>'})
        odt = self.archive("sample.odt", {"content.xml": '<document><p>OpenDocument fixture</p></document>'})
        self.assertIn("Slide fixture", readers.read_document(pptx)["text"])
        self.assertEqual(readers.read_document(odt)["text"], "OpenDocument fixture")

    def test_xml_entities_rejected(self):
        path = self.archive("sample.docx", {"word/document.xml": '<!DOCTYPE d [<!ENTITY x "unsafe">]><d><p>&x;</p></d>'})
        with self.assertRaisesRegex(ValueError, "DTD/entity"):
            readers.read_document(path)

    def test_zip_members_never_extracted(self):
        path = self.archive("sample.zip", {"../escape.txt": "test", "run.py": "raise Exception()"})
        result = readers.read_document(path)
        self.assertEqual(len(result["entries"]), 2)
        self.assertFalse((self.root / "run.py").exists())

    def test_utf16_and_unsupported(self):
        path = self.root / "unicode.txt"
        path.write_text("Unicode fixture", encoding="utf-16")
        self.assertEqual(readers.read_document(path)["text"], "Unicode fixture")
        legacy = self.root / "old.doc"
        legacy.write_bytes(b"old document")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            readers.read_document(legacy)

    def test_wav_metadata(self):
        path = self.root / "test.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\x00" * 16000)
        self.assertEqual(readers.read_document(path)["seconds"], 1)

    @unittest.skipUnless(readers.capabilities()["pdf_text"], "pypdf not installed in this runtime")
    def test_pdf_text(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 72 700 Td (PDF fixture APRICOT) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        path = self.root / "test.pdf"
        with path.open("wb") as output:
            writer.write(output)
        with patch("socket.getaddrinfo", side_effect=AssertionError("No DNS allowed")):
            self.assertIn("PDF fixture APRICOT", readers.read_document(path)["text"])

    @unittest.skipUnless(readers.capabilities()["image_metadata"], "Pillow not installed in this runtime")
    def test_image_metadata(self):
        from PIL import Image
        path = self.root / "test.png"
        Image.new("RGB", (12, 7)).save(path)
        result = readers.read_document(path)
        self.assertEqual((result["width"], result["height"]), (12, 7))


if __name__ == "__main__":
    unittest.main(verbosity=2)
