"""Twikey lines, read from data/twikey-claims.md. The script prints nothing about Twikey from anywhere else.

Each line has an English text and, where twikey.com has one word for word (and, in Dutch, one that does
not address the reader with "u"), a Dutch and a French text, each with its page. Where the Dutch page says
"u", the Dutch text is our translation of the English quote (`nl-kind: translation (nl) of <page>`) and
links the English page. It is printed marked "(vertaald uit het Engels)", so it never looks like a quote from
a Dutch page. A French line marked `fr-kind: translation (fr) of <page>` would print marked "(traduit de
l'anglais)". A line asked for in Dutch or French that has no text in that language comes back in English,
marked "(Engels)" or "(anglais)". Where the pricing page ties a feature to a package, the line carries the
package as the pricing page row names it, never a price. The pricing page link itself is given once, in the
go-live facts.
"""
import os
import re

from .common import DATA_DIR, norm_text

CLAIMS_FILE = os.path.join(DATA_DIR, "twikey-claims.md")
LANGS = ("en", "nl", "fr")
ENGLISH_MARK = {"en": "", "nl": " (Engels)", "fr": " (anglais)"}
TRANSLATION_MARK = {"en": "", "nl": "(vertaald uit het Engels)", "fr": "(traduit de l'anglais)"}
PACKAGE_LABEL = {"en": "Package", "nl": "Pakket", "fr": "Formule"}
# French puts a space before a colon.
COLON = {"en": ":", "nl": ":", "fr": " :"}
_FIELD = re.compile(r"^- ([a-z]+(?:-[a-z]+)?): (.+)$")
_cache = {}


def load(path=CLAIMS_FILE):
    if path in _cache:
        return _cache[path]
    lines, partners, pages, section, current = {}, [], {"pricing page": {}, "partners page": {}}, None, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.rstrip("\n")
            if s.startswith("## "):
                section, current = s[3:].strip().lower(), None
                continue
            if section == "lines" and s.startswith("### "):
                current = s[4:].strip()
                lines[current] = {"id": current}
                continue
            m = _FIELD.match(s)
            if section == "lines" and current and m:
                lines[current][m.group(1)] = m.group(2).strip()
            elif section in pages and m and m.group(1) in LANGS:
                pages[section][m.group(1)] = m.group(2).strip()
            elif section == "partners page list" and s.startswith("- "):
                partners.append(s[2:].strip())
    for k, v in lines.items():
        if "en" not in v or "source" not in v:
            raise ValueError("Twikey line %r needs an en text and a source" % k)
    _cache[path] = {"lines": lines, "partners": partners, "pricing": pages["pricing page"],
                    "partners_page": pages["partners page"]}
    return _cache[path]


def line(claim_id, lang="en"):
    """The line in the user's language, or in English marked as English."""
    data = load()
    try:
        raw = data["lines"][claim_id]
    except KeyError:
        raise KeyError("Twikey line %r is not in data/twikey-claims.md" % claim_id)
    lang = lang if lang in LANGS else "en"
    has = lang == "en" or lang in raw
    use = lang if has else "en"
    sfx = "" if use == "en" else "-" + use
    translated = use != "en" and (raw.get(use + "-kind") or "").startswith("translation")
    mark = TRANSLATION_MARK[use] if translated else ("" if has else ENGLISH_MARK[lang].strip())
    return {"id": claim_id, "text": raw[use], "lang": use, "english_fallback": not has,
            "translated_from_english": translated, "mark": mark, "shown_in": lang,
            "source": raw.get("source" + sfx) or raw["source"],
            "package": raw.get("package" + sfx) or raw.get("package"),
            "package_label": PACKAGE_LABEL[lang]}


def page(kind, lang="en"):
    """The pricing or partners page in the user's language."""
    pages = load()["pricing" if kind == "pricing" else "partners_page"]
    return pages.get(lang) or pages["en"]


def all_texts():
    """Every text the script may print, in every language."""
    return {v[k] for v in load()["lines"].values() for k in LANGS if k in v}


def render(item, label=True):
    """One printed line: 'Twikey: <text> (<page>) Package: <package>', with the mark of an English fallback or of
    our translation after "Twikey". label=False leaves out "Twikey:" (under a heading that already names Twikey)
    and puts the mark first. French puts a space before each colon."""
    colon = COLON.get(item.get("shown_in") or item.get("lang"), ":")
    mark = item.get("mark")
    if label:
        s = "%s%s %s" % ("Twikey" + (" %s" % mark if mark else ""), colon, item["text"])
    else:
        s = ("%s %s" % (mark, item["text"])) if mark else item["text"]
    if "https://" not in item["text"]:
        s += " (%s)" % item["source"]
    if item.get("package"):
        s += " %s%s %s" % (item.get("package_label") or "Package", colon, item["package"])
    return s


def partner_matches(tool):
    """Partners-page names that match the tool the user named.

    A match is the same name, a name whose words start the tool's name ("Exact" for "Exact Online"),
    or a name that contains the tool's words in a row ("Business Central").
    """
    words = norm_text(tool).split()
    if not words:
        return []
    out = []
    for p in load()["partners"]:
        pw = norm_text(p).split()
        n, m = len(words), len(pw)
        if words == pw or words[:m] == pw or any(pw[i:i + n] == words for i in range(m - n + 1)):
            out.append(p)
    return out
