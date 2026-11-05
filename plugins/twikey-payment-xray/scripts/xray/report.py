"""The final report: Claude's coded findings with the names put back, written next to the raw files.

Runs on the user's computer. The CLI prints only the path of the report, never its contents.
"""
import datetime as dt
import os
import re

from . import VERSION, claims
from .common import REPORT_PREFIX, XrayError, long_date

_CODE = re.compile(r"(?<![A-Za-z0-9])([CMA]\d{3,}|[IRE]\d{4,})(?![A-Za-z0-9])")

# What Claude saw: the workspace holds nothing else (tests/test_intake.py, WorkspaceHoldsNoRawValuesTest).
TEXT = {
    "en": {"title": "Twikey Payment X-ray report",
           "made": "Made on %s with Twikey Payment X-ray %s. Names and numbers were put back on your own computer. "
                   "Claude saw amounts, dates, counts, statuses and bank reason codes, with codes in place of "
                   "names, account numbers, mandate references, invoice numbers and payment references. Twikey "
                   "received nothing.",
           "files": "Files read", "file": "file %s", "no_ref": "%s (no reference in your export)",
           "footer": "Twikey Payment X-ray %s. The numbers come from your own exports."},
    "nl": {"title": "Twikey Payment X-ray rapport",
           "made": "Gemaakt op %s met Twikey Payment X-ray %s. De namen en nummers zijn op je eigen computer "
                   "teruggezet. Claude zag bedragen, datums, aantallen, statussen en redencodes van de bank, met "
                   "codes in plaats van namen, rekeningnummers, mandaatreferenties, factuurnummers en "
                   "betaalreferenties. Twikey heeft niets ontvangen.",
           "files": "Gelezen bestanden", "file": "bestand %s", "no_ref": "%s (geen referentie in je export)",
           "footer": "Twikey Payment X-ray %s. De cijfers komen uit je eigen exports."},
    "fr": {"title": "Rapport Twikey Payment X-ray",
           "made": "Établi le %s avec Twikey Payment X-ray %s. Les noms et numéros ont été remis sur votre propre "
                   "ordinateur. Claude a vu des montants, des dates, des nombres, des statuts et des codes motif "
                   "de la banque, avec des codes à la place des noms, numéros de compte, références de mandat, "
                   "numéros de facture et références de paiement. Twikey n'a rien reçu.",
           "files": "Fichiers lus", "file": "fichier %s", "no_ref": "%s (pas de référence dans votre export)",
           "footer": "Twikey Payment X-ray %s. Les chiffres viennent de vos propres exports."},
}

# Sentences about codes that are true in findings.md but wrong once the names are back.
_CODES_NOTE = re.compile(
    r"[^\n.]*(?:appear as codes|The report puts the names back|Klanten (?:staan|verschijnen) (?:er )?als codes?|"
    r"Les clients apparaissent (?:sous forme de|comme des) codes?)[^\n.]*\.?[ \t]*", re.I)


def mask_iban(iban):
    s = (iban or "").replace(" ", "")
    if len(s) < 8:
        return "****"
    return "%s** **** **** %s" % (s[:2], s[-4:])


def decode_codes(text, key, lang="en"):
    """Replace codes that exist in the key with the real values. Unknown codes stay as they are."""
    no_ref = (TEXT.get(lang) or TEXT["en"])["no_ref"]

    def repl(m):
        code = m.group(1)
        if code[0] == "C" and code in key.parties:
            p = key.parties[code]
            return p.get("name") or (p.get("numbers") or [code])[0]
        if code[0] == "M" and code in key.mandates:
            return key.mandates[code] or no_ref % code
        if code[0] == "I" and code in key.invoices:
            return key.invoices[code]
        if code[0] == "A" and code in key.accounts:
            return mask_iban(key.accounts[code])
        if code[0] == "R" and code in key.refs:
            return key.refs[code]
        if code[0] == "E" and code in key.e2e_ids:
            return key.e2e_ids[code]
        return code
    return _CODE.sub(repl, text)


def drop_codes_note(text):
    return _CODES_NOTE.sub("", text)


def unique_path(raw_dir, day, prefix=REPORT_PREFIX):
    """<prefix><date>.md next to the raw exports, with -2, -3 ... when that name is taken: never overwrites."""
    base = os.path.join(raw_dir, "%s%s" % (prefix, day.isoformat()))
    path, n = base + ".md", 2
    while os.path.exists(path):
        path, n = "%s-%d.md" % (base, n), n + 1
    return path


_SUMMARY = re.compile(r"(?m)^##[ \t]*(What we found|Wat we vonden|Ce que nous avons trouvé)[ \t]*\n(?:[ \t]*\n)?"
                      r"(?:^[ \t]*(?:[-*]|\d+[.)])[ \t].*(?:\n|\Z))+")
_DEMO_LINK = re.compile(r"(?m)^.*twikey\.com/(?:be/|fr/)?demo\.html.*$\n?")


def split_summary(text):
    """The "What we found" section (three lines, biggest numbers first) and the rest of the findings."""
    m = _SUMMARY.search(text)
    if not m:
        return None, text
    rest = re.sub(r"\n{3,}", "\n\n", text[:m.start()] + text[m.end():])
    return m.group(0).strip(), rest.strip()


def render(findings_text, key, extra_texts=(), today=None, lang="en"):
    today = today or dt.date.today()
    t = TEXT.get(lang) or TEXT["en"]
    demo = claims.line("demo", lang)
    # One call to action: the demo link once, at the end. Copies in the findings or the plan are dropped.
    summary, rest = split_summary(_DEMO_LINK.sub("", drop_codes_note(findings_text.strip())))
    colon = claims.COLON.get(lang, ":")
    parts = ["# %s" % t["title"], ""]
    if summary:
        parts += [decode_codes(summary, key, lang), ""]
    parts += [t["made"] % (long_date(today, lang), VERSION), "", decode_codes(rest, key, lang)]
    for x in extra_texts:
        parts += ["", decode_codes(_DEMO_LINK.sub("", drop_codes_note(x.strip())), key, lang)]
    files = getattr(key, "files", None) or {}
    if files:
        parts += ["", "%s%s" % (t["files"], colon), ""]
        # the key labels files "file 2", in English: the list says it in the report's language
        parts += ["- %s%s %s" % (t["file"] % label.split()[-1], colon, name)
                  for label, name in sorted(files.items(), key=lambda kv: int(kv[0].split()[-1]))]
    parts += ["", demo["text"], "", "---", "", t["footer"] % VERSION, ""]
    return "\n".join(parts)


def write_report(raw_dir, findings_path, key, extra_paths=(), today=None, lang="en"):
    if not os.path.exists(findings_path):
        raise XrayError("No findings.md in the workspace yet. Run the scan first.")
    with open(findings_path, encoding="utf-8") as f:
        findings = f.read()
    extras = []
    for p in extra_paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                extras.append(f.read())
    today = today or dt.date.today()
    path = unique_path(raw_dir, today)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(findings, key, extras, today, lang))
    return path
