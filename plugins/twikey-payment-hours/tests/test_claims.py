"""The Twikey lines: references/twikey-claims.md is well formed, and every Twikey line the calculator prints is in it
word for word, with one of its own twikey.com links.

Run from skills-v2: python3 -B -m unittest discover -s tests -v
"""
import datetime
import os
import re
import sys
import unittest
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, "scripts"))

import hours  # noqa: E402
from test_hours import SAMPLE, build  # noqa: E402

SITE = "https://www.twikey.com"
BRAND = "auto" + "pay"  # the brand word the copy never uses, built from parts so this file stays clean too
UTM = "utm_source=twikey-payment-hours&utm_medium=claude-skills&utm_campaign=payment-hours"

# The sample plus every method a Twikey rule line speaks to, so all of them print.
FULL = SAMPLE + [
    "method.sdd_core.share=0", "method.sdd_core.fee_fixed=0.30", "method.sdd_core.days=5",
    "method.card_recurring.share=0", "method.card_recurring.fee_pct=1.2", "method.card_recurring.days=3",
    "method.bancontact.share=0", "method.wero.share=0", "method.paypal.share=0", "method.link.share=0",
]


def claim_urls(c):
    urls = {c["source"]}
    for k in ("source-nl", "source-fr"):
        if k in c:
            urls.add(c[k])
    if "nl-kind" in c:
        urls.add(c["nl-kind"].split(" of ", 1)[1].strip())
    return urls


class ClaimsFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claims, cls.pricing = hours.load_claims()
        with open(hours.CLAIMS, encoding="utf-8") as f:
            cls.text = f.read()
        cls.lines = {cid: c for cid, c in cls.claims.items() if cid != "demo"}

    def test_lines_exist(self):
        for cid in ("auto-collect", "reconciliation", "reminders", "failed-auto", "orchestration", "demo"):
            self.assertIn(cid, self.claims)
        for gone in ("dunning", "payment-links", "failed-payments", "renewed-consent"):
            self.assertNotIn(gone, self.claims)

    def test_only_lines_that_say_automated_carry_steps(self):
        for cid in ("collect-when-due", "tokenization", "own-account"):
            self.assertEqual(self.claims[cid]["steps"], [], cid)

    def test_every_line_has_english_and_a_twikey_source(self):
        for cid, c in self.claims.items():
            self.assertTrue(c.get("en"), cid)
            self.assertTrue(c.get("source", "").startswith(SITE), cid)
            for k in ("source-nl", "source-fr"):
                if k in c:
                    self.assertTrue(c[k].startswith(SITE), (cid, k))
            if "source-nl" in c:
                self.assertTrue(c["source-nl"].startswith(SITE + "/be/"), cid)
            if "source-fr" in c:
                self.assertTrue(c["source-fr"].startswith(SITE + "/fr/"), cid)

    def test_steps_and_methods_are_valid_ids(self):
        for cid, c in self.claims.items():
            for step in c["steps"]:
                self.assertIn(step, hours.STEPS, cid)
            for method in c["methods"]:
                self.assertIn(method, hours.METHODS + ["all"], cid)
        covered = sorted(set(s for c in self.claims.values() for s in c["steps"]), key=hours.STEPS.index)
        self.assertEqual(covered, ["collect", "match", "chase", "failed"])

    def test_dutch_lines(self):
        for cid, c in self.lines.items():
            self.assertIn("nl", c, cid)
            if "source-nl" not in c:  # no word-for-word /be/ page: our own translation, marked as one
                self.assertRegex(c.get("nl-kind", ""), r"^translation \(nl\) of https://www\.twikey\.com/\S+$", cid)
            if "nl-kind" in c:
                self.assertEqual(c["nl-kind"].split(" of ", 1)[1].strip(), c["source"], cid)
            self.assertNotRegex(c["nl"], r"(?i)\b(u|uw)\b", cid)

    def test_french_lines(self):
        for cid, c in self.lines.items():
            if "fr" in c:
                self.assertIn("source-fr", c, cid)
                self.assertTrue(c["fr"].startswith("« ") and c["fr"].endswith(" »"), cid)

    def test_packages_in_three_languages(self):
        for cid, c in self.lines.items():
            if "package" in c:
                self.assertIn("package-nl", c, cid)
                self.assertIn("package-fr", c, cid)

    def test_demo(self):
        demo = self.claims["demo"]
        paths = {"en": SITE + "/demo.html", "nl": SITE + "/be/demo.html", "fr": SITE + "/fr/demo.html"}
        for lang in hours.LANGS:
            urls = re.findall(r"https://\S+", demo[lang])
            self.assertEqual(len(urls), 1, lang)
            parts = urlsplit(urls[0])
            self.assertEqual("%s://%s%s" % (parts.scheme, parts.netloc, parts.path), paths[lang])
            self.assertEqual(parts.query, UTM, lang)

    def test_pricing(self):
        self.assertEqual(self.pricing, {"en": SITE + "/pricing.html", "nl": SITE + "/be/pricing.html",
                                        "fr": SITE + "/fr/pricing.html"})

    def test_no_price_and_no_brand_word(self):
        self.assertNotIn("€", self.text)
        self.assertNotIn(BRAND, self.text.lower())
        self.assertNotRegex(self.text, r"\bEUR\b|\$\d")


class PrintedLines(unittest.TestCase):
    """Run process, methods and report on a full ledger in three languages and check every Twikey line."""

    LINE = re.compile(r"Twikey(?: \((?:English|Engels|anglais|vertaald uit het Engels)\))? ?: (.+) "
                      r"\((https://www\.twikey\.com[^)\s]*)\)$")
    PKG = re.compile(r"(?:Pricing page row|Rij op de prijspagina|Ligne de la page des tarifs) ?: (.+)$")

    @classmethod
    def setUpClass(cls):
        cls.claims, _ = hours.load_claims()
        led = build(FULL)
        cls.outputs = {}
        for lang in hours.LANGS:
            cls.outputs[lang] = "\n".join([
                hours.cmd_process(led, lang), hours.cmd_methods(led, lang),
                hours.cmd_report(led, lang, today=datetime.date(2026, 11, 4))])

    def test_quotes_word_for_word_with_their_own_link(self):
        texts = {}
        for cid, c in self.claims.items():
            for lang in hours.LANGS:
                if lang in c:
                    texts.setdefault(c[lang], set()).add(cid)
        for lang, out in self.outputs.items():
            found = 0
            for line in out.splitlines():
                m = self.LINE.search(line)
                if not m:
                    continue
                quote, url = m.group(1), m.group(2)
                self.assertIn(quote, texts, (lang, line))
                self.assertTrue(any(url in claim_urls(self.claims[cid]) for cid in texts[quote]), (lang, line))
                found += 1
            self.assertGreaterEqual(found, 15, lang)

    def test_every_twikey_mention_is_a_claims_line(self):
        allowed = ("Payment Hours by Twikey", "Payment Hours van Twikey", "Payment Hours par Twikey",
                   "Where Twikey fits", "Waar Twikey past", "Où Twikey intervient", "Twikey's site", "Twikey page",
                   "page de Twikey", "Twikey volgens zijn site", "Twikey automatise", "Twikey-pagina",
                   "Twikey hem automatiseert", "Twikey overneemt", "Twikey takes over", "Twikey l'automatise",
                   "Twikey prend en charge")
        for lang, out in self.outputs.items():
            for line in out.splitlines():
                if "Twikey" not in line or self.LINE.search(line) or line == self.claims["demo"][lang]:
                    continue
                rest = line
                for a in allowed:
                    rest = rest.replace(a, "")
                self.assertNotIn("Twikey", rest, (lang, line))

    def test_no_package_rows(self):
        packages = [c[k] for c in self.claims.values() for k in ("package", "package-nl", "package-fr") if k in c]
        for lang, out in self.outputs.items():
            self.assertEqual([m.group(0) for m in map(self.PKG.search, out.splitlines()) if m], [], lang)
            for row in packages:
                self.assertNotIn(row, out, lang)

    def test_twikey_lines_only_at_the_end(self):
        fits = {"en": "Where Twikey fits", "nl": "Waar Twikey past", "fr": "Où Twikey intervient"}
        led = build(FULL)
        for lang in hours.LANGS:
            self.assertNotIn("Twikey", hours.cmd_process(led, lang))
            for out in (hours.cmd_methods(led, lang), hours.cmd_report(led, lang, today=datetime.date(2026, 11, 4))):
                body, final = out.split("## " + fits[lang])
                self.assertNotIn("Twikey", body, lang)
                self.assertTrue(any(self.LINE.search(line) for line in final.splitlines()), lang)

    def test_language_of_each_line(self):
        nl, fr = self.outputs["nl"], self.outputs["fr"]
        self.assertNotIn("Twikey (Engels)", nl)  # every line has Dutch text
        self.assertIn("Twikey (anglais) : " + self.claims["card-chargebacks"]["en"], fr)  # no French page
        self.assertIn(self.claims["reconciliation"]["fr"], fr)
        # Our own Dutch translation says so and links the English page it translates.
        self.assertIn("Twikey (vertaald uit het Engels): " + self.claims["b2b-registered"]["nl"] + " ("
                      + self.claims["b2b-registered"]["source"] + ")", nl)
        self.assertIn("Twikey (vertaald uit het Engels): " + self.claims["auto-collect"]["nl"], nl)
        self.assertIn("Twikey: " + self.claims["reconciliation"]["nl"], nl)  # word for word from /be/
        self.assertNotIn("vertaald", self.outputs["en"] + fr)
        for lang in hours.LANGS:
            self.assertEqual(self.outputs[lang].count(self.claims["demo"][lang]), 1, lang)


if __name__ == "__main__":
    unittest.main()
