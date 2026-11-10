"""Belgian structured communication (OGM/VCS): +++ddd/dddd/ddddd+++.

Twelve digits. The last two are the first ten modulo 97, and 97 when that remainder is 0.
Only this Belgian format is checked. The RF creditor reference and the Dutch payment reference
are not validated in this release: they count as "other reference (not checked)".
"""
import re

_FORMATTED = re.compile(r"[+*]{3}\s*(\d{3})\s*/\s*(\d{4})\s*/\s*(\d{5})\s*[+*]{3}")
_SLASHED = re.compile(r"(?<![\d/])(\d{3})/(\d{4})/(\d{5})(?![\d/])")
_PLAIN = re.compile(r"^\s*(\d{3})\s*/?\s*(\d{4})\s*/?\s*(\d{5})\s*$")


def check_digits(base10):
    if len(base10) != 10 or not base10.isdigit():
        raise ValueError("an OGM base has ten digits")
    return "%02d" % (int(base10) % 97 or 97)


def is_valid(digits):
    return bool(digits) and len(digits) == 12 and digits.isdigit() and digits[10:] == check_digits(digits[:10])


def fmt(digits):
    return "+++%s/%s/%s+++" % (digits[0:3], digits[3:7], digits[7:12])


def from_field(value):
    """Read a dedicated structured-communication field.

    Returns (formatted OGM or None, status) with status "valid", "invalid", "other" or "absent".
    Accepts +++ddd/dddd/ddddd+++, ***ddd/dddd/ddddd***, ddd/dddd/ddddd and 12 plain digits. Only a value
    in that shape whose check digits are wrong is "invalid". Any other reference (an RF creditor
    reference, a Dutch payment reference, an invoice number) is "other": not checked, never called wrong.
    """
    s = str(value or "").strip()
    if not s:
        return None, "absent"
    if s[:2].upper() == "RF":
        return None, "other"  # ISO 11649 creditor reference, not checked in this release
    m = _FORMATTED.search(s) or _PLAIN.match(s.strip("+* "))
    if not m:
        return None, ("invalid" if s[:3] in ("+++", "***") else "other")
    digits = "".join(m.groups())
    return (fmt(digits), "valid") if is_valid(digits) else (None, "invalid")


def from_text(text):
    """Find a structured communication inside free text.

    Only the written forms with +++, *** or slashes count, so a random 12-digit number in the
    text is never taken for one. Returns (formatted OGM or None, status).
    """
    s = str(text or "")
    found_invalid = False
    for rx in (_FORMATTED, _SLASHED):
        for m in rx.finditer(s):
            digits = "".join(m.groups())
            if is_valid(digits):
                return fmt(digits), "valid"
            found_invalid = True
    return None, ("invalid" if found_invalid else "absent")
