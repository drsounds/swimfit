import unittest

from swimfit.anonymizer import anonymize_line


def no_entities(_text):
    return []


class AnonymizerTests(unittest.TestCase):
    def test_redacts_emails_and_phones_but_not_dates(self):
        result, counts = anonymize_line(
            "Email jane@example.com; call +1 (555) 222-1234 on 2024-02-01",
            no_entities,
        )

        self.assertEqual(result, "Email [EMAIL]; call [PHONE] on 2024-02-01")
        self.assertEqual(counts, {"email": 1, "phone": 1})

    def test_detector_entities_are_redacted_without_altering_brands(self):
        def detect(_text):
            return [
                {"text": "Sam Taylor", "category": "person"},
                {"text": "Acme", "category": "person"},
            ]

        result, counts = anonymize_line(
            "Sam Taylor works at Acme and Acme Labs.", detect, brands=["Acme"]
        )

        self.assertEqual(result, "[PERSON] works at Acme and Acme Labs.")
        self.assertEqual(counts, {"person": 1})

    def test_brand_words_do_not_protect_email_addresses(self):
        result, counts = anonymize_line(
            "Contact info@acme.com", no_entities, brands=["Acme"]
        )

        self.assertEqual(result, "Contact [EMAIL]")
        self.assertEqual(counts, {"email": 1})

    def test_brand_words_are_not_removed_as_phone_data(self):
        result, counts = anonymize_line(
            "Call 1-800-ACME or visit Acme.", no_entities, ["Acme"]
        )

        self.assertEqual(result, "Call 1-800-ACME or visit Acme.")
        self.assertEqual(counts, {})
