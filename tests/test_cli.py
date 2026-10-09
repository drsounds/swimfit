import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swimler.cli import main


class NoopVerifier:
    def __init__(self, _model):
        pass

    def __call__(self, _text):
        return []


class CliTests(unittest.TestCase):
    def test_auto_accept_writes_output_and_audit_without_source_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "contacts.txt"
            output_dir = Path(directory) / "result"
            source.write_text("Contact jane@example.com\n", encoding="utf-8")

            with patch("swimler.cli.LocalOllamaVerifier", NoopVerifier):
                result = main([str(source), "-o", str(output_dir), "-y"])

            output = output_dir / source.name
            audit = output_dir / f"{source.name}.audit.log"
            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "Contact [EMAIL]\n")
            audit_text = audit.read_text(encoding="utf-8")
            self.assertNotIn("jane@example.com", audit_text)
            self.assertIn('"row": 1', audit_text)
            self.assertTrue(
                any(json.loads(line)["operation"] == "write" for line in audit_text.splitlines())
            )
            self.assertEqual(source.read_text(encoding="utf-8"), "Contact jane@example.com\n")


if __name__ == "__main__":
    unittest.main()
