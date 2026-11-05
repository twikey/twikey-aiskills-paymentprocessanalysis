"""Twikey lines trace to data/twikey-claims.md, copy rules hold, pinned files stay as they are, Python 3.8."""
import ast
import glob
import hashlib
import json
import os
import re
import unittest

from tests.helpers import PLUGIN, SCRIPTS, Sandbox, read_text
from xray import checks, claims

REPO = os.path.dirname(os.path.dirname(PLUGIN))
DATA_COPY = [os.path.join(PLUGIN, "data", "manual_steps.json"), os.path.join(PLUGIN, "data", "mail_templates.json")]
SHIPPED_TEXT = (glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")) + [os.path.join(PLUGIN, "data", "twikey-claims.md")]
                + DATA_COPY
                + [os.path.join(REPO, "README.md"), os.path.join(PLUGIN, "README.md"),
                   os.path.join(PLUGIN, ".claude-plugin", "plugin.json"),
                   os.path.join(REPO, ".claude-plugin", "marketplace.json"), os.path.join(PLUGIN, "hooks", "hooks.json")])
CODE = glob.glob(os.path.join(SCRIPTS, "*.py")) + glob.glob(os.path.join(SCRIPTS, "xray", "*.py"))
TESTS = glob.glob(os.path.join(PLUGIN, "tests", "*.py")) + glob.glob(os.path.join(PLUGIN, "tests", "*.json"))
EVERY_FILE = [p for p in glob.glob(os.path.join(REPO, "**", "*"), recursive=True)
              if os.path.isfile(p) and "__pycache__" not in p and "/.git/" not in p]

# Words that must appear in no file of the repository, tests included. Built from pieces, so this file does not
# contain them either.
BRAND = "Auto" + "pay"
PEOPLE = ["Sa" + "bir", "Ko" + "en", "Domin" + "ique", "ko" + "en@"]
INTERNAL = ["fix " + "round", "OPEN" + ".md", "CLAIMS" + "-NOTES", "TO" + "DO"]

# SHA-256 of the reason-code files. en and nl are the website's codes_en.json and codes_nl.json. fr carries three
# corrected typos (AC06 "bloque" -> "bloqué", BE05 "identication" -> "identification", PY01 "Pas routable" ->
# "Non routable").
RCODES_SHA256 = {
    "rcodes_en.json": "4c95653b1c83c7791713c6fc207f29937d7d7a5aa3917288739852833be018c1",
    "rcodes_nl.json": "878a94635ac2dd33f7a48d20425d682514a23ecb7a17470359d9f01dae812684",
    "rcodes_fr.json": "2673744710c8f496a02afc5a23b6406bb4bca127b78c4ad1db2c1e130d4f3dae",
}
FR_CORRECTIONS = {"AC06": ("bloqué", "est bloque,"), "BE05": ("identification", "identication"),
                  "PY01": ("Non routable", "Pas routable")}
# First 16 hex of SHA-256 of each function in scripts/xray/calc.py: the standard formulas must not drift.
CALC_FUNCTIONS = {
    "d": "5d53bd7e373eadbb", "cust_key": "df6e204ffcb9c172", "cust_name": "a7497115eb097634",
    "paid_date": "84cf0ffebe562fdf", "pay_method": "9c97216664b8fccc", "has_mandate": "70ff73e307861c4f",
    "is_paid": "2f88e4b02fdc437c", "is_closed": "9bdec4fa70c775ce", "is_open": "a4b97984b08bb7cc",
    "days_overdue": "4a00296d78ce676c", "money": "aff353ac36b3a265", "slim": "af7797a7fac7909e",
    "customer_stats": "8c8f4389e5c04313", "aging": "df8b7a8ca2ec5461", "dso": "b18e9aa9603ed592",
}
DEMO_URL = ("https://www.twikey.com/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin"
            "&utm_campaign=payment-xray")
RUNS = (["intake"], ["decode"], ["mandates"], ["match"], ["terms"], ["steps"], ["golive", "--tool", "Odoo"])
# month prints only the path of its work pack: its Twikey lines are in the JSON output and in the work pack
JSON_RUNS = RUNS + (["month"],)


def prose_lines(path):
    """Markdown lines outside code blocks and inline code."""
    out, fence = [], False
    for line in read_text(path).splitlines():
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            out.append(re.sub(r"`[^`]*`", "", line))
    return out


# "Twikey: ", "Twikey (Engels): ", "Twikey (vertaald uit het Engels): ", "Twikey : " (French)
PREFIX = re.compile(r"^Twikey( \([^)]+\))? ?: ")
# a line under "What Twikey does:" in the work pack: no "Twikey:" label, the mark (if any) first
PACK_MARK = re.compile(r"^\((Engels|anglais|vertaald uit het Engels|traduit de l'anglais)\) ")


def printed_lines(lang):
    """Every 'Twikey...' line the commands print, and every Twikey line dict in the JSON output."""
    texts, dicts = [], []
    with Sandbox() as s:
        s.cli("demo", "--raw", s.raw, "--lang", lang)
        for argv in JSON_RUNS:
            code, out, err = s.cli(*argv)
            assert code == 0, err
            texts += [ln for ln in out.splitlines() if PREFIX.match(ln)]
            if argv == ["month"]:  # the work pack, on the user's computer: the lines under the Twikey label
                pack = read_text(out.strip()).split("\n---\n")[1]
                texts += ["Twikey: " + PACK_MARK.sub("", ln[2:]) for ln in pack.splitlines() if ln.startswith("- ")]
            code, data = s.cli_json(*argv)

            def walk(v):
                if isinstance(v, dict):
                    if "text" in v and "id" in v:
                        dicts.append(v)
                    for x in v.values():
                        walk(x)
                elif isinstance(v, list):
                    for x in v:
                        walk(x)
            walk(data)
    return texts, dicts


class ClaimsTest(unittest.TestCase):
    def test_every_line_the_code_asks_for_exists(self):
        ids = set(checks.GOLIVE_LINES)
        for path in CODE:
            ids |= set(re.findall(r'claims\.line\("([a-z0-9-]+)"', read_text(path)))
        self.assertTrue(ids)
        for i in ids:
            self.assertIn(i, claims.load()["lines"], i)

    def test_every_twikey_line_printed_is_in_the_claims_file(self):
        texts = claims.all_texts()
        for lang in ("en", "nl", "fr"):
            printed, dicts = printed_lines(lang)
            self.assertGreaterEqual(len(printed), 8)
            for p in printed:
                body = PREFIX.sub("", p)
                self.assertTrue(any(body == t or body.startswith(t + " ") for t in texts), p)
            for d in dicts:
                self.assertIn(d["text"], texts)
                self.assertEqual(d["lang"], lang if not d["english_fallback"] else "en")

    def test_every_line_has_dutch_in_the_je_form(self):
        lines = claims.load()["lines"]
        for cid, v in lines.items():
            nl = v.get("nl")
            self.assertTrue(nl, cid)  # every Twikey line has a Dutch text
            # never addresses the reader with u, uw or jouw, and says domiciliëring, not incasso
            self.assertNotRegex(nl, r"(?i)\b(u|uw|jouw)\b", cid)
            self.assertNotRegex(nl, r"(?i)\bincasso", cid)
            line = claims.line(cid, "nl")
            self.assertFalse(line["english_fallback"], cid)
            # our translation of an English page is marked as such, a quote from a Dutch page carries no mark
            want = "(vertaald uit het Engels)" if v.get("nl-kind") else ""
            self.assertEqual((line["lang"], line["mark"]), ("nl", want), cid)
        self.assertTrue(claims.line("failure-decoder", "nl")["text"].endswith("verlopen kaarten of mandaten”"))
        printed, dicts = printed_lines("nl")
        self.assertFalse([p for p in printed if "(Engels)" in p])
        by_id = {d["id"]: d for d in dicts}
        self.assertEqual(by_id["failure-decoder"]["lang"], "nl")
        self.assertIn("/be/", by_id["failure-decoder"]["source"])
        self.assertFalse(by_id["failure-decoder"]["translated_from_english"])

    def test_dutch_translations_never_look_like_a_quote(self):
        line = claims.line("unmatched-payments", "nl")
        self.assertTrue(line["translated_from_english"])
        self.assertEqual(claims.render(line), "Twikey (vertaald uit het Engels): " + line["text"] +
                         " (https://www.twikey.com/product/reconciliation.html)")
        self.assertTrue(claims.render(line, label=False).startswith("(vertaald uit het Engels) “Onze dashboards"))
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw, "--lang", "nl")
            code, out, err = s.cli("match")
            self.assertIn("Twikey (vertaald uit het Engels): “Onze dashboards", out)
            code, out, err = s.cli("decode")  # a quote from the Belgian Dutch page: no mark
            self.assertIn("Twikey: “Dit stelt ons", out)
            pack = read_text(s.cli("month")[1].strip())
            self.assertIn("- (vertaald uit het Engels) “Onze dashboards", pack)

    def test_french_labels_have_a_space_before_the_colon(self):
        line = claims.line("failure-decoder", "fr")
        self.assertTrue(claims.render(line).startswith("Twikey : « Cela nous permet"))
        self.assertIn(" Formule : « Gestion des échecs", claims.render(line))
        self.assertTrue(claims.render(claims.line("failure-decoder", "en")).startswith("Twikey: “This allows"))
        self.assertIn(" Package: “Transaction", claims.render(claims.line("failure-decoder", "en")))

    def test_six_dutch_lines_are_marked_as_translations(self):
        lines = claims.load()["lines"]
        six = ("unmatched-payments", "terms-vs-reality", "payer-profiles", "b2b-registered", "own-bank",
               "creditor-id")
        for cid, v in lines.items():
            if cid in six:
                # Twikey's translation of the English quote, linked to that English page
                self.assertEqual(v.get("nl-kind"), "translation (nl) of " + v["source"], cid)
                self.assertNotIn("source-nl", v, cid)
                self.assertEqual(claims.line(cid, "nl")["source"], v["source"], cid)
            else:
                # a word-for-word quote from the Belgian Dutch page
                self.assertNotIn("nl-kind", v, cid)
                self.assertIn("/be/", v["source-nl"], cid)

    def test_the_english_mark_stays_for_a_line_without_dutch(self):
        data = claims.load()
        saved = data["lines"]["own-bank"].pop("nl")
        try:
            line = claims.line("own-bank", "nl")
            self.assertTrue(line["english_fallback"])
            self.assertEqual(line["mark"], "(Engels)")
            self.assertTrue(claims.render(line).startswith("Twikey (Engels): "))
        finally:
            data["lines"]["own-bank"]["nl"] = saved

    def test_french_lines_are_quoted(self):
        printed, dicts = printed_lines("fr")
        for d in dicts:
            self.assertFalse(d["english_fallback"], d["id"])
            self.assertIn("/fr/", d["source"])

    def test_claims_lines_follow_the_copy_rules(self):
        lines = claims.load()["lines"]
        for line in lines.values():
            self.assertTrue(line["source"].startswith("https://www.twikey.com"), line["id"])
            for lang in ("en", "nl", "fr"):
                t = line.get(lang)
                if not t:
                    continue
                self.assertNotIn(";", t)
                self.assertNotIn("—", t)
                self.assertNotIn(BRAND.lower(), t.lower())
                self.assertNotRegex(t.lower(), r"process(es)? payments|fraud engine|fraud detection|2,000|99\.")
                self.assertNotRegex(t, r"€\s?\d|\d\s?€")  # never a price
            for k, v in line.items():
                if k.startswith("source"):
                    self.assertTrue(v.startswith("https://www.twikey.com"), (line["id"], k))
        # packages exactly as the pricing page rows, no partner-connector package
        self.assertEqual(claims.line("failure-decoder")["package"],
                         "“Transaction failure management”: Professional. “Advanced failure management”: Premium")
        self.assertEqual(claims.line("core-b2b")["package"], "“Create & manage SEPA B2B mandates (other)”: Professional")
        self.assertNotIn("ERP", read_text(claims.CLAIMS_FILE))
        for gone in ("intake", "hours-check", "existing-mandates", "contact", "payment-plans"):
            self.assertNotIn(gone, lines)
        # the mandate line answers the expired-mandate finding
        self.assertIn("expired cards or mandates", claims.line("mandate-health")["text"])
        cid = claims.line("creditor-id")["text"]
        self.assertIn("at your bank", cid)
        self.assertNotIn("Twikey", cid)
        # one call to action, labels per language
        self.assertEqual(claims.line("demo")["text"], "Ask Twikey for a demo: " + DEMO_URL)
        self.assertTrue(claims.line("demo", "nl")["text"].startswith("Vraag Twikey een demo: "))
        self.assertTrue(claims.line("demo", "fr")["text"].startswith("Demandez une démo à Twikey : "))
        # no line links the pricing page: it is linked once, in the go-live facts
        for line in lines.values():
            self.assertNotIn("pricing", line["source"])

    def test_claims_file_holds_no_internal_notes(self):
        text = read_text(claims.CLAIMS_FILE)
        for internal in ["Not used because", "need a yes", "needs a yes", "open for " + "the CTO", "commit",
                         "build " + "brief", "technical plan"] + PEOPLE:
            self.assertNotIn(internal, text)

    def test_partner_matching(self):
        self.assertEqual(claims.partner_matches("Exact Online"), ["Exact"])
        self.assertEqual(claims.partner_matches("business central"), ["Dynamics 365 Business Central"])
        self.assertEqual(claims.partner_matches("SAP Business One"), ["SAP", "SAP Business One"])
        self.assertEqual(claims.partner_matches("Yuki"), [])
        self.assertEqual(claims.partner_matches(""), [])
        self.assertEqual(len(claims.load()["partners"]), 57)


BANNED = re.compile(r"(?i)herprobeerd|address change|\btwikey (processes|holds)|fraud engine|"
                    r"fraud detection|\b2,000\b|99\.\d+ ?%")
PROHIBITION = re.compile(r"(?i)\b(never|do not|not used|don't)\b")
# Not a public product, internal, or a claim with no page behind it.
NOT_PUBLIC = re.compile(r"(?i)collections team|same numbers before and after|twikey_collect|"
                        r"customers appear as codes|\banalyse (my|the|further|your|our|it)\b|\banalys(ing|ed)\b|"
                        r"you analyse|moving collections to twikey|take over that work|version 1\.1|2023 version|"
                        r"large Belgian bank portals work|a new attempt can collect|97 ?%")


class CopyRulesTest(unittest.TestCase):
    def test_no_brand_people_or_internal_notes_in_any_file(self):
        any_case = [BRAND] + PEOPLE + INTERNAL[:1]
        exact = INTERNAL[1:]
        for path in EVERY_FILE:
            try:
                text = read_text(path)
            except UnicodeDecodeError:
                continue
            where = os.path.relpath(path, REPO)
            for w in any_case:
                self.assertFalse(w.lower() in text.lower(), "%s: %s" % (where, w))
            for w in exact:
                self.assertFalse(w in text, "%s: %s" % (where, w))

    def test_shipped_text(self):
        for path in SHIPPED_TEXT:
            self.assertTrue(os.path.exists(path), path)
            text = read_text(path)
            self.assertNotIn("—", text, path)  # no em-dash
            self.assertNotIn(BRAND.lower(), text.lower(), path)  # not even in a rule that forbids it
            for line in text.splitlines():
                # any other banned word may only appear in a line that forbids it
                if BANNED.search(line):
                    self.assertRegex(line, PROHIBITION, "%s: %s" % (os.path.basename(path), line))
        for path in [p for p in SHIPPED_TEXT if p.endswith(".md") and not p.endswith("twikey-claims.md")]:
            for line in prose_lines(path):
                self.assertNotIn(";", line, "%s: %s" % (os.path.basename(path), line))
                self.assertNotRegex(line, r"€\s?\d", "%s: %s" % (os.path.basename(path), line))  # never a price

    def test_nothing_internal_or_unsourced_ships(self):
        for path in SHIPPED_TEXT + CODE + [os.path.join(PLUGIN, "tests", "make_demo.py")]:
            for n, line in enumerate(read_text(path).splitlines(), 1):
                self.assertIsNone(NOT_PUBLIC.search(line), "%s:%d: %s" % (os.path.relpath(path, REPO), n, line))
        self.assertFalse(os.path.exists(os.path.join(REPO, "OPEN" + ".md")))

    def test_skills_name_no_brand(self):
        for path in glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")):
            text = read_text(path)
            if "brand name" in text:
                self.assertIn("Call it automatic payments, never by a brand name.", text)

    def test_text_output_has_no_semicolons_and_spells_small_numbers(self):
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw)
            for argv in RUNS + (["status"],):
                code, out, err = s.cli(*argv)
                self.assertEqual(code, 0, err)
                for line in out.splitlines():
                    self.assertNotIn(";", line, (argv, line))
                    self.assertNotIn("time(s)", line)
                    self.assertNotRegex(line, r"\b1 name\b|\b1 names\b")
                self.assertNotRegex(out, r"\d{4}-\d{2}-\d{2}", argv)  # dates written out
            code, out, err = s.cli("mandates")
            self.assertIn("presented one more time after it expired", out)
            self.assertIn("Mandates on October 31, 2026", out)
            code, out, err = s.cli("terms")
            self.assertIn("DSO (days sales outstanding", out)


class PinnedFilesTest(unittest.TestCase):
    def test_reason_code_files(self):
        for name, sha in RCODES_SHA256.items():
            with open(os.path.join(PLUGIN, "data", name), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), sha, name)
            with open(os.path.join(PLUGIN, "data", name), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 25)

    def test_french_typos_corrected(self):
        codes = checks.rcodes("fr")
        for code, (fixed, typo) in FR_CORRECTIONS.items():
            self.assertIn(fixed, codes[code]["DESC"], code)
            self.assertNotIn(typo, codes[code]["DESC"], code)

    def test_standard_formulas_are_unchanged(self):
        src = read_text(os.path.join(SCRIPTS, "xray", "calc.py"))
        lines = src.splitlines()
        funcs = {n.name: "\n".join(lines[n.lineno - 1:n.end_lineno]) for n in ast.parse(src).body
                 if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(funcs), set(CALC_FUNCTIONS))  # no forecast, no success rates
        for name, digest in CALC_FUNCTIONS.items():
            self.assertEqual(hashlib.sha256(funcs[name].encode()).hexdigest()[:16], digest, name)


class PythonTest(unittest.TestCase):
    def test_python_38_grammar_and_stdlib_only(self):
        files = CODE + glob.glob(os.path.join(PLUGIN, "tests", "*.py"))
        for path in files:
            src = read_text(path)
            ast.parse(src, filename=path, feature_version=(3, 8))
            self.assertNotRegex(src, r"\.removeprefix\(|\.removesuffix\(|\bzoneinfo\b|functools\.cache\b|"
                                     r"\bmatch .*:\n\s+case ", path)
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = (node.module if isinstance(node, ast.ImportFrom) else node.names[0].name) or ""
                    self.assertNotIn(mod.split(".")[0], ("requests", "defusedxml", "lxml", "pandas", "numpy"), path)

    def test_no_network_code_in_the_plugin(self):
        for path in CODE:
            src = read_text(path)
            self.assertNotRegex(src, r"\bimport (urllib|http|socket|ssl|ftplib|smtplib)|from (urllib|http) ", path)


# Words of a time or money estimate. X-ray 0.2.0 counts steps and never turns them into time or money. Built with
# word boundaries: "factuur", "facturen" and "malheureusement" hold these letters and are fine.
TIME_WORDS = re.compile(r"(?i)\b(hours?|uur|uren|heures?|minutes?|minuten)\b|estimat|schatting")
ROI = re.compile(r"\bROI\b")
# Customer mails: no threats, no fees, no legal language, no Twikey.
MAIL_BANNED = re.compile(r"(?i)twikey|\bfees?\b|\bcosts?\b|interest|penalt|legal|lawyer|court|bailiff|collection agency|"
                         r"incasso|kosten|boete|rente|advocaat|rechtbank|deurwaarder|aanmaning|ingebrekestelling|"
                         r"frais|pénalit|intérêts|avocat|tribunal|huissier|juridique|mise en demeure|"
                         r"last reminder|final notice|laatste herinnering|dernier rappel|"
                         r"\bimmediately\b|onmiddellijk|immédiatement")


class NoEstimatesTest(unittest.TestCase):
    def test_no_time_or_roi_words_in_the_plugin(self):
        # every file of the plugin, tests included, except the test files that assert these words are gone
        exempt = {os.path.join(PLUGIN, "tests", n) for n in ("test_claims.py", "test_guard.py", "test_manifests.py")}
        files = [p for p in glob.glob(os.path.join(PLUGIN, "**", "*"), recursive=True)
                 if os.path.isfile(p) and "__pycache__" not in p and p not in exempt]
        self.assertGreater(len(files), 40)
        for path in files:
            try:
                text = read_text(path)
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                where = "%s:%d: %s" % (os.path.relpath(path, REPO), n, line.strip()[:120])
                self.assertIsNone(TIME_WORDS.search(line), where)
                self.assertIsNone(ROI.search(line), where)
        self.assertIsNone(TIME_WORDS.search("factuur facturen malheureusement huurwaarborg"))
        self.assertIsNotNone(TIME_WORDS.search("3,9 uur per maand"))

    def test_marketplace_xray_entry(self):
        m = json.loads(read_text(os.path.join(REPO, ".claude-plugin", "marketplace.json")))
        entry = [p for p in m["plugins"] if p["name"] == "twikey-payment-xray"][0]
        xray_half = m["description"].split("Payment X-ray", 1)[1]
        for text in (entry["description"], xray_half):
            self.assertIsNone(TIME_WORDS.search(text), text)
            self.assertIn("manual work", text)
            self.assertIn("this month's work", text)


class DataCopyTest(unittest.TestCase):
    """data/manual_steps.json and data/mail_templates.json: reviewable copy in English, Dutch and French."""

    def strings(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                for s in self.strings(v):
                    yield s
        elif isinstance(value, list):
            for v in value:
                for s in self.strings(v):
                    yield s

    def test_copy_rules(self):
        for path in DATA_COPY:
            data = json.loads(read_text(path))
            self.assertEqual(set(data) - {"_about"}, {"en", "nl", "fr"}, path)
            for lang in ("en", "nl", "fr"):
                for s in self.strings(data[lang]):
                    where = "%s %s: %s" % (os.path.basename(path), lang, s)
                    self.assertNotIn(";", s, where)
                    self.assertNotIn("—", s, where)
                    self.assertNotIn("–", s, where)
                    self.assertNotIn(BRAND.lower(), s.lower(), where)
                    if lang == "nl":
                        self.assertNotRegex(s, r"(?i)\b(u|uw|jouw)\b", where)
                        self.assertNotRegex(s, r"(?i)herprobeerd|incasso", where)
                    if lang == "en":  # US spelling
                        self.assertNotRegex(s, r"(?i)organis|recognis|realis|authoris|apologis|colour|favour|"
                                               r"behaviour|cheque|cancelled|cancelling", where)
            # the same keys in every language, so no text is missing in one of them
            def keys(v, prefix=""):
                if isinstance(v, dict):
                    return {k2 for k, x in v.items() for k2 in keys(x, prefix + "/" + k) | {prefix + "/" + k}}
                return set()
            self.assertEqual(keys(data["en"]), keys(data["nl"]), path)
            self.assertEqual(keys(data["en"]), keys(data["fr"]), path)

    def test_mail_templates(self):
        data = json.loads(read_text(DATA_COPY[1]))
        literal = {"en": ("[your company name]", "[link to your mandate form]"),
                   "nl": ("[naam van je bedrijf]", "[link naar je mandaatformulier]"),
                   "fr": ("[nom de votre entreprise]", "[lien vers votre formulaire de mandat]")}
        allowed = {"customer", "invoices", "amount", "failure_date", "new_date", "mandate", "expiry_date", "company"}
        placeholders = {"en": ("[amount]", "[date of the new collection]"),
                        "nl": ("[bedrag]", "[datum van de nieuwe domiciliëring]"),
                        "fr": ("[montant]", "[date du nouveau prélèvement]")}
        for lang in ("en", "nl", "fr"):
            t = data[lang]
            self.assertEqual(t["company"], literal[lang][0])
            self.assertEqual((t["amount_unknown"], t["new_date_unknown"]), placeholders[lang])
            self.assertEqual(set(t["templates"]), {"new_attempt", "new_attempt_neutral", "new_mandate",
                                                   "b2b_register", "conversation", "mandate_renewal"})
            # only insufficient funds asks for funds
            funds = {"en": "funds", "nl": "saldo", "fr": "approvisionné"}[lang]
            self.assertIn(funds, " ".join(t["templates"]["new_attempt"]["body"]))
            self.assertNotIn(funds, " ".join(t["templates"]["new_attempt_neutral"]["body"]))
            self.assertIn("{mandate}", t["templates"]["b2b_register"]["subject"])
            for reason, tpl in t["templates"].items():
                text = (tpl["subject"] + "\n" + tpl.get("subject_many", "") + "\n"
                        + "\n".join(tpl["body"] + tpl.get("body_many", [])))
                if reason in ("new_attempt", "new_attempt_neutral", "new_mandate", "b2b_register", "conversation"):
                    self.assertIn("body_many", tpl, "%s %s: several debts read in the plural" % (lang, reason))
                where = "%s %s" % (lang, reason)
                self.assertTrue(set(re.findall(r"\{(\w+)\}", text)) <= allowed, where)
                self.assertIn("{customer}", text, where)
                self.assertIn("{company}", text, where)
                self.assertIsNone(MAIL_BANNED.search(text), where)
                if reason in ("new_mandate", "mandate_renewal"):
                    self.assertIn(literal[lang][1], text, where)
                if reason != "mandate_renewal":
                    self.assertIn("{invoices}", text, where)
                    self.assertIn("{amount}", text, where)
                if reason.startswith("new_attempt"):
                    self.assertIn("{new_date}", text, where)
                if lang == "en":
                    self.assertNotIn("e-mail", text, where)  # email
                    self.assertNotIn("money on the account", text, where)
                if lang == "fr":
                    self.assertRegex(text.lower(), r"\b(vous|votre|vos)\b", where)
                    self.assertNotRegex(text.lower(), r"\b(tu|ton|ta|tes|toi)\b", where)
            self.assertIn("{invoice}", t["item"])
            self.assertNotIn("{invoice}", t["item_no_invoice"])

    def test_manual_steps_labels(self):
        data = json.loads(read_text(DATA_COPY[0]))
        for lang in ("en", "nl", "fr"):
            for k, v in data[lang]["items"].items():
                self.assertTrue(v["label"] and v["label_one"] and v["checklist"], (lang, k))
                self.assertEqual(v["label"], v["label"].lower()[0] + v["label"][1:], (lang, k))  # used mid-sentence
        self.assertEqual(data["nl"]["items"]["failed_new_attempt"]["label"],
                         "mislukte domiciliëringen die heraangeboden kunnen worden")


if __name__ == "__main__":
    unittest.main()
