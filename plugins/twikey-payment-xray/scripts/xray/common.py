"""Shared helpers: workspace paths, JSON files, dates, money, months, name normalization."""
import calendar
import datetime as dt
import json
import os
import re
import sys
import unicodedata

from . import VERSION

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PLUGIN_ROOT, "data")
DEMO_DIR = os.path.join(PLUGIN_ROOT, "demo")

DEFAULT_HOME = "twikey-xray-workspace"
KEY_FILE = "twikey-xray-key.json"
REPORT_PREFIX = "twikey-xray-report-"
MONTH_PREFIX = "twikey-xray-month-"
REGISTRY_FILE = "raw-folders.json"

DEFAULT_CONFIG = {
    "version": VERSION,
    "raw_dir": None,
    "as_of": None,
    "lang": "en",
    "currency": "EUR",
    "default_terms_days": 30,
    "demo": False,
    "column_maps": {},
    # Read by the standard formulas in xray/calc.py.
    "paid_states": ["PAID"],
    "closed_states": ["ARCHIVED", "CANCELLED", "CREDITED"],
    "key_clients": [],
}


class XrayError(Exception):
    """An error the user can act on. The CLI prints the message and exits 1."""


# Today's date. None means the computer's date. Tests set it, so no test depends on the day it runs.
TODAY = None


def today():
    return TODAY or dt.date.today()


def state_dir():
    """Folder outside every workspace that holds the guard's list of raw folders."""
    return os.path.abspath(os.path.expanduser(os.environ.get("TWIKEY_XRAY_STATE_DIR") or "~/.twikey-xray"))


def registry_path():
    return os.path.join(state_dir(), REGISTRY_FILE)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=False, default=str)
        f.write("\n")
    os.replace(tmp, path)


def real(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def inside(path, folder):
    """True when path is folder itself or lies below it (after resolving symlinks)."""
    p, f = real(path), real(folder)
    return p == f or p.startswith(f.rstrip(os.sep) + os.sep)


# --------------------------------------------------------------------------- dates

def parse_iso(s):
    if not s:
        return None
    try:
        return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError, TypeError):
        return None


def iso(d):
    return d.isoformat() if d else None


def add_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _easter(year):
    """Easter Sunday (Gregorian calendar, the anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l_) // 433
    month = (h + l_ - 7 * m + 90) // 25
    return dt.date(year, month, (h + l_ - 7 * m + 33 * month + 19) % 32)


def closing_days(year):
    """Days the SEPA payment system (TARGET2) is closed besides weekends."""
    easter = _easter(year)
    return {dt.date(year, 1, 1), easter - dt.timedelta(days=2), easter + dt.timedelta(days=1), dt.date(year, 5, 1),
            dt.date(year, 12, 25), dt.date(year, 12, 26)}


def working_day(d):
    """The day itself, or the next day the SEPA payment system is open."""
    while d.weekday() >= 5 or d in closing_days(d.year):
        d += dt.timedelta(days=1)
    return d


MONTH_NAMES = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
}


def long_date(d, lang="en"):
    """A date written out in the user's language: October 31, 2026 / 31 oktober 2026 / 31 octobre 2026."""
    if isinstance(d, str):
        d = parse_iso(d)
    if not d:
        return "-"
    lang = lang if lang in MONTH_NAMES else "en"
    month = MONTH_NAMES[lang][d.month - 1]
    if lang == "en":
        return "%s %d, %d" % (month, d.day, d.year)
    if lang == "fr" and d.day == 1:
        return "1er %s %d" % (month, d.year)
    return "%d %s %d" % (d.day, month, d.year)


def month_year(d, lang="en"):
    if isinstance(d, str):
        d = parse_iso(d)
    if not d:
        return "-"
    lang = lang if lang in MONTH_NAMES else "en"
    return "%s %d" % (MONTH_NAMES[lang][d.month - 1], d.year)


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
NUMBER_WORDS_NL = ["nul", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien"]


def num(n, lang="en"):
    """Numbers one to ten spelled out in English and Dutch prose, larger numbers in digits. French uses digits:
    its one is "un" or "une" by the noun that follows."""
    if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 10:
        if lang == "nl":
            return NUMBER_WORDS_NL[n]
        if lang != "fr":
            return NUMBER_WORDS[n]
    return str(n)


NUMBER_WORDS_FR = ["aucun", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"]


def num_fr(n, fem=False):
    """French zero to ten in words where the gender of the noun is known: 'aucun', 'une', 'trois'. Larger numbers
    in digits."""
    if isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 10:
        w = NUMBER_WORDS_FR[n]
        return w + "e" if fem and n < 2 else w
    return str(n)


NO_WORD = {"en": "no", "nl": "geen"}


def plural(n, one, many, lang="en"):
    """'no invoices', 'one time', 'three times', '12 invoices' (Dutch 'geen facturen', French '0 facture')."""
    if n == 0:
        if lang == "fr":
            return "0 %s" % one
        return "%s %s" % (NO_WORD.get(lang, "no"), many)
    return "%s %s" % (num(n, lang), one if n == 1 else many)


def months_spanned(dates):
    """Number of calendar months from the first to the last date, both included."""
    ds = [d for d in dates if d]
    if not ds:
        return 0
    a, b = min(ds), max(ds)
    return (b.year - a.year) * 12 + (b.month - a.month) + 1


# --------------------------------------------------------------------------- money

def cents(value):
    """Round a float amount to whole cents (int)."""
    return int(round(float(value) * 100))


def cents_known(value):
    """Cents of an amount, 0 for an amount that is not known (None)."""
    return 0 if value is None else cents(value)


def euros(c):
    return round(c / 100.0, 2)


def _local(s, lang):
    """1,234.50 -> 1.234,50 for Dutch and French."""
    if lang in ("nl", "fr"):
        return s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return s


def money(amount, currency="EUR", lang="en"):
    """Symbol first: €1,234.50 in English, €1.234,50 in Dutch and French."""
    a = float(amount or 0)
    sign = "-" if a < 0 else ""
    s = _local(format(abs(round(a, 2)), ",.2f"), lang)
    if currency == "EUR":
        return "%s€%s" % (sign, s)
    return "%s%s %s" % (sign, currency, s)


def dec(x, places=1, lang="en"):
    """A decimal number in the user's language: 3.9 / 3,9."""
    if x is None:
        return "-"
    return _local(format(round(float(x), places), ",.%df" % places), lang)


def pct(x, lang="en"):
    """22.6% / 22,6%."""
    return dec(x, 1, lang) + "%"


# --------------------------------------------------------------------------- names

LEGAL_FORMS = {
    "nv", "bv", "bvba", "sprl", "srl", "sa", "vof", "commv", "cv", "cvba", "scrl", "sc", "scs", "vzw", "asbl",
    "gcv", "snc", "eurl", "sarl", "sas", "gmbh", "ag", "kg", "ltd", "llc", "inc", "bvio", "ebvba", "esv", "cvoa",
    "plc", "ivzw", "aisbl", "stichting", "fondation",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_text(s):
    """Lower case, no accents, only letters and digits separated by single spaces."""
    s = strip_accents(str(s or "")).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def norm_name(s):
    """Party name for linking files: no case, accents, punctuation or legal form."""
    words = norm_text(s).split()
    while words and words[-1] in LEGAL_FORMS:
        words.pop()
    while words and words[0] in LEGAL_FORMS:
        words.pop(0)
    return " ".join(words)


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def eprint(msg):
    print(msg, file=sys.stderr)
