import unittest

from tests import helpers  # noqa: F401  (sets sys.path)
from xray import ogm


class OgmTest(unittest.TestCase):
    def test_check_digits_by_hand(self):
        # 2600000001 = 97 x 26804123 + 70
        self.assertEqual(ogm.check_digits("2600000001"), "70")
        # 909337554 = 97 x 9374613 + 93
        self.assertEqual(ogm.check_digits("0909337554"), "93")
        # remainder 0 becomes 97
        self.assertEqual(ogm.check_digits("0000000097"), "97")
        self.assertEqual(ogm.check_digits("0000000194"), "97")

    def test_is_valid(self):
        self.assertTrue(ogm.is_valid("260000000170"))
        self.assertTrue(ogm.is_valid("090933755493"))
        self.assertTrue(ogm.is_valid("000000009797"))
        self.assertFalse(ogm.is_valid("260000000171"))
        self.assertFalse(ogm.is_valid("000000009700"))  # 00 is never a valid check
        self.assertFalse(ogm.is_valid("26000000017"))
        self.assertFalse(ogm.is_valid("26000000017a"))
        self.assertFalse(ogm.is_valid(""))

    def test_from_field_forms(self):
        for v in ("+++260/0000/00170+++", "***260/0000/00170***", "260/0000/00170", "260000000170",
                  " +++ 260 / 0000 / 00170 +++ "):
            self.assertEqual(ogm.from_field(v), ("+++260/0000/00170+++", "valid"), v)
        self.assertEqual(ogm.from_field(""), (None, "absent"))
        self.assertEqual(ogm.from_field(None), (None, "absent"))
        self.assertEqual(ogm.from_field("+++260/0000/00171+++"), (None, "invalid"))
        self.assertEqual(ogm.from_field("+++260/0000/0017+++"), (None, "invalid"))
        self.assertEqual(ogm.from_field("RF18539007547034"), (None, "other"))
        # a reference that is not in the OGM shape is "other", never "wrong check digits"
        for v in ("factuur 12", "INV-2026-0042", "1234567890123456", "0000 1234 5678 9012"):
            self.assertEqual(ogm.from_field(v), (None, "other"), v)

    def test_from_text_only_written_forms(self):
        self.assertEqual(ogm.from_text("betaling +++090/9337/55493+++ dank u"), ("+++090/9337/55493+++", "valid"))
        self.assertEqual(ogm.from_text("ref 090/9337/55493"), ("+++090/9337/55493+++", "valid"))
        # a bare 12-digit number in free text is not taken for a structured communication
        self.assertEqual(ogm.from_text("order 090933755493"), (None, "absent"))
        self.assertEqual(ogm.from_text("+++090/9337/55494+++"), (None, "invalid"))
        self.assertEqual(ogm.from_text(""), (None, "absent"))
        # an invalid one first, a valid one later: the valid one wins
        self.assertEqual(ogm.from_text("+++090/9337/55494+++ or +++260/0000/00170+++"),
                         ("+++260/0000/00170+++", "valid"))


if __name__ == "__main__":
    unittest.main()
