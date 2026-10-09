import io
import unittest
import zipfile

from swimfit.processing import clean_bytes, clean_zip


def no_entities(_text):
    return []


class ProcessingTests(unittest.TestCase):
    def test_text_cleaning_preserves_line_numbers_and_line_endings(self):
        cleaned, records, kind = clean_bytes(
            "notes.txt",
            b"jane@example.com\r\nNothing to redact\n",
            no_entities,
        )

        self.assertEqual(cleaned, b"[EMAIL]\r\nNothing to redact\n")
        self.assertEqual(kind, "text")
        self.assertEqual(
            records,
            [
                {
                    "file": "notes.txt",
                    "row": 1,
                    "operation": "redact",
                    "counts": {"email": 1},
                }
            ],
        )

    def test_binary_files_are_preserved(self):
        data = b"\x00\xff\x01"

        cleaned, records, kind = clean_bytes("image.bin", data, no_entities)

        self.assertEqual(cleaned, data)
        self.assertEqual(records, [])
        self.assertEqual(kind, "binary")

    def test_zip_cleans_text_and_preserves_binary_members(self):
        source = io.BytesIO()
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("notes.txt", "jane@example.com")
            archive.writestr("image.bin", b"\x00\xff")

        cleaned, records = clean_zip(source.getvalue(), no_entities)

        with zipfile.ZipFile(io.BytesIO(cleaned)) as archive:
            self.assertEqual(archive.read("notes.txt"), b"[EMAIL]")
            self.assertEqual(archive.read("image.bin"), b"\x00\xff")
        self.assertEqual(
            [record["operation"] for record in records], ["redact", "skip_binary"]
        )

    def test_csv_cleans_cells_and_audits_data_row_numbers(self):
        cleaned, records, kind = clean_bytes(
            "contacts.csv",
            b"name,email\nJane,jane@example.com\n",
            no_entities,
        )

        self.assertEqual(cleaned, b"name,email\nJane,[EMAIL]\n")
        self.assertEqual(kind, "text")
        self.assertEqual(
            records,
            [
                {
                    "file": "contacts.csv",
                    "row": 2,
                    "column": 2,
                    "operation": "redact",
                    "counts": {"email": 1},
                }
            ],
        )

    def test_zip_reviewer_can_reject_a_member(self):
        source = io.BytesIO()
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("notes.txt", "jane@example.com")

        cleaned, records = clean_zip(
            source.getvalue(),
            no_entities,
            reviewer=lambda original, _changed, _name: (False, original),
        )

        with zipfile.ZipFile(io.BytesIO(cleaned)) as archive:
            self.assertEqual(archive.read("notes.txt"), b"jane@example.com")
        self.assertIn("reject", [record["operation"] for record in records])
