"""The demo company against tests/expected_demo.json, written by hand from the spec in make_demo.py."""
import filecmp
import json
import os
import re
import shutil
import tempfile
import unittest

from tests import make_demo
from tests.helpers import DEMO, Sandbox, expected, load, read_text

E = expected()

SECRETS = ([n for n in make_demo.NAMES if n] + [make_demo.LANDLORD, make_demo.COMPANY] + make_demo.SUPPLIERS
           + [n.rsplit(" ", 1)[0] for n in make_demo.NAMES if n and n.split()[-1] in ("BV", "NV", "SRL", "SA", "VOF", "VZW")]
           + ["Voorbeeldstraat", "Huurlaan", "Leverancierslaan", "boekhouding@", "Voorschot", "huurwaarborg",
              "Deel betaling", "Factuur VF"]
           # file names can hold names, so no command prints them
           + [os.path.splitext(f)[0] for f in os.listdir(DEMO)])
PATTERNS = [re.compile(r"\bBE\d{2}\s?\d{4}"), re.compile(r"\bVF-\d{4}\b"), re.compile(r"FICT-[MB]-"),
            re.compile(r"\bK10\d\d\b"), re.compile(r"[\w.]+@[\w.]+\.example")]


def leaks(text):
    found = [s for s in SECRETS if s in text or s.upper() in text]
    found += [p.pattern for p in PATTERNS if p.search(text)]
    return found


class DemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.box = Sandbox().__enter__()
        cls.demo_code, cls.intake = cls.box.cli_json("demo", "--raw", cls.box.raw)

    @classmethod
    def tearDownClass(cls):
        cls.box.__exit__(None, None, None)

    def run_json(self, *argv):
        code, data = self.box.cli_json(*argv)
        self.assertEqual(code, 0, data)
        return data

    # ------------------------------------------------------------------ intake

    def test_intake(self):
        self.assertEqual(self.demo_code, 0)
        e, t = E["intake"], self.intake["totals"]
        for k in ("invoices", "parties", "customers", "other_parties", "mandate_rows", "mandate_codes",
                  "bank_credit_lines", "debit_lines_skipped", "own_transfers_skipped", "collections_collected",
                  "failed_collections", "failed_amount_unknown", "duplicates_removed",
                  "invalid_structured_communications"):
            self.assertEqual(t[k], e[k], k)
        files = {f["file"]: f for f in self.intake["files"]}
        self.assertEqual(set(files), set(e["kinds"]))
        for name, kind in e["kinds"].items():
            got = files[name]["kind"] if files[name]["format"] == "csv" else files[name]["format"]
            self.assertEqual(got, kind, name)
        for name, cols in e["dropped_columns"].items():
            self.assertEqual(files[name]["columns_dropped"], cols, name)
        for name, cols in e["read_not_stored"].items():
            self.assertEqual(files[name]["read_not_stored"], cols, name)

    # ------------------------------------------------------------------ checks

    def test_decode(self):
        d, e = self.run_json("decode"), E["decode"]
        self.assertEqual(d["total"], e["total"])
        by = {r["code"]: r for r in d["by_code"]}
        self.assertEqual(set(by), set(e["by_code"]))
        for code, want in e["by_code"].items():
            self.assertEqual((by[code]["count"], by[code]["amount"], by[code]["known"]),
                             (want["count"], want["amount"], want["known"]), code)
            if "meaning" in want:  # a code outside Twikey's list: the EPC reason, no Twikey page
                self.assertEqual(by[code]["meaning"], want["meaning"])
                self.assertIsNone(by[code]["page"])
        self.assertEqual(d["by_code"][0]["code"], e["top_code"])  # the biggest code, by euros and by count
        self.assertEqual(max(d["by_code"], key=lambda r: r["count"])["code"], e["top_code"])
        self.assertEqual({k: {"count": v["count"], "amount": v["amount"]} for k, v in d["by_category"].items()},
                         e["by_category"])
        self.assertEqual(d["days_of_month"], e["days_of_month"])  # a rate, days with two months or more
        self.assertEqual(d["days_of_month_overall"], e["days_of_month_overall"])
        self.assertEqual(d["failures_by_day"], e["failures_by_day"])
        self.assertEqual(d["repeat_customers"], e["repeat_customers"])
        self.assertEqual(d["unknown_codes"], e["unknown_codes"])
        # failures touch only a few of the 14 direct debit customers
        dd = {"C%03d" % n for n in range(1, 15)}
        coll = load(os.path.join(self.box.home, "collections.json"))
        with_failures = sorted({c["customer"] for c in coll if c["status"] == "failed"} & dd)
        self.assertEqual(with_failures, e["direct_debit_customers_with_failures"])
        self.assertLessEqual(len(with_failures), 4)

    def test_mandates(self):
        d, e = self.run_json("mandates", "--on", E["mandates"]["on"]), E["mandates"]
        for k in ("rows", "codes", "core", "b2b", "to_renew"):
            self.assertEqual(d[k], e[k], k)
        for issue in ("expired", "expiring_90_days", "unused_since_signing", "last_collection_unknown",
                      "missing_reference",
                      "missing_signature_date", "signature_missing", "duplicate_reference", "possible_duplicate",
                      "iban_changed", "b2b_not_confirmed"):
            got = d["issues"][issue]
            if issue == "expiring_90_days":
                got = [{k: v for k, v in i.items() if k != "last_presented"} for i in got]
            if issue == "unused_since_signing":
                got = [{k: v for k, v in i.items() if k != "signed_on"} for i in got]
            self.assertEqual(got, e[issue], issue)

    def test_match(self):
        d, e = self.run_json("match"), E["match"]
        self.assertEqual(d["credit_lines"], e["credit_lines"])
        for cat in ("matched", "paid_but_open", "partial", "bundled", "double", "unmatched", "other_receipts"):
            self.assertEqual((d[cat]["count"], d[cat]["amount"]), (e[cat]["count"], e[cat]["amount"]), cat)
            if "customers" in e[cat]:
                self.assertEqual(d[cat]["customers"], e[cat]["customers"], cat)
        self.assertEqual(d["partial"]["still_open"], e["partial"]["still_open"])
        self.assertEqual(d["bundled"]["invoices"], e["bundled"]["invoices"])
        for k in ("known_customer", "unknown_party", "mentions_open_invoice"):
            self.assertEqual(d["unmatched"][k], e["unmatched"][k], k)

    def test_terms(self):
        d, e = self.run_json("terms"), E["terms"]
        for p, custs in e["profiles"].items():
            self.assertEqual(d["profiles"][p]["customers"], custs, p)
        rows = {r["customer"]: r for r in d["customers"]}
        fourteen = sorted(c for c, r in rows.items() if r["agreed_terms_days"] == 14)
        self.assertEqual(fourteen, e["agreed_terms_days"]["14"])
        self.assertTrue(all(r["agreed_terms_days"] in (14, 30) for r in rows.values()))
        for c, want in e["samples"].items():
            for k, v in want.items():
                self.assertEqual(rows[c][k], v, "%s %s" % (c, k))
        self.assertEqual(d["open_receivables"], e["open_receivables"])
        self.assertEqual(d["overdue"], e["overdue"])
        self.assertEqual(d["aging"], e["aging"])
        for k in ("dso_90d", "terms_days_90d", "dso_minus_terms"):
            self.assertEqual(d[k], e[k], k)
        # a customer with failed collections is never clockwork
        failed = {c for c in self.run_json("decode")["repeat_customers"]}
        self.assertFalse(failed & set(d["profiles"]["clockwork"]["customers"]))

    def test_steps(self):
        d, e = self.run_json("steps"), E["steps"]
        self.assertEqual([i["id"] for i in d["items"]], list(e["items"]))  # biggest steps_total first
        by = {i["id"]: i for i in d["items"]}
        for k, want in e["items"].items():
            self.assertEqual({f: by[k][f] for f in want}, want, k)
        for k, want in e["examples"].items():
            self.assertEqual(by[k]["examples"], want, k)
        for k in ("total_items", "total_steps", "per_month_total", "per_month_steps_total", "per_month_left_out"):
            self.assertEqual(d[k], e[k], k)
        # the counts come from the other checks, never re-derived
        self.assertEqual(by["failed_new_attempt"]["count"], E["decode"]["by_category"]["new_attempt"]["count"])
        self.assertEqual(by["paid_but_open"]["count"], E["match"]["paid_but_open"]["count"])
        self.assertEqual([t["id"] for t in d["twikey"]], ["failure-decoder", "unmatched-payments"])
        code, out, err = self.box.cli("steps")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Manual work in your files, as of October 31, 2026.")
        self.assertEqual(lines[1], "168 invoices more than seven days late: 168 × (send a reminder · follow up) = "
                                   "336 steps (14.0 a month over 12 months)")
        self.assertIn("9 failed collections worth a new attempt: 9 × (look up what the reason code means · tell the "
                      "customer · present the collection again in your bank tool · check whether it came through) = "
                      "36 steps (0.8 a month over 12 months)", lines)
        self.assertIn("1 paid invoice still open in your books: 1 × (find the payment · close the invoice) = 2 steps "
                      "(0.3 a month over 3 months)", lines)
        self.assertIn("5 payments to book by hand (no match, partial or bundled): 5 × (find who paid · find the "
                      "invoice or invoices · book the match by hand) = 15 steps (1.7 a month over 3 months)", lines)
        self.assertIn("1 invoice paid twice: 1 × (contact the customer · refund or credit the amount · record it) = "
                      "3 steps (0.3 a month over 3 months)", lines)
        self.assertIn("Total: 205 items, 462 steps (the lines cover different periods).", lines)
        # exact per-month values, rounded once: 17.9 and 41.0, not the 18.0 and 41.4 of rounded values added up
        self.assertIn("Per month, for the item types counted over a period: 17.9 items, 41.0 steps.", lines)
        self.assertIn("None in your files: failed collections caused by your own file or setup.", lines)
        self.assertNotIn("0 ×", out)  # item types without items are named once, not counted
        self.assertIn("check which mandates have expired or will expire", out)
        self.assertNotIn("Not checked", out)

    def test_month(self):
        d, e = self.run_json("month"), E["month"]
        self.assertEqual(d["counts"], e["counts"])
        self.assertEqual([{k: a[k] for k in e["new_attempts"][0]} for a in d["new_attempts"]], e["new_attempts"])
        self.assertEqual(d["collected_later"], e["collected_later"])  # C004 in August and C006 in September
        self.assertEqual(d["closed"], e["closed"])
        self.assertEqual({k: d["suggested_day"][k] for k in e["suggested_day"]}, e["suggested_day"])
        self.assertEqual([{k: m[k] for k in e["mails"][0]} for m in d["mails"]], e["mails"])
        self.assertEqual(len({m["customer"] for m in d["mails"]}), len(d["mails"]))  # one mail per customer
        self.assertEqual([{k: r[k] for k in e["mandates_to_renew"][0]} for r in d["mandates_to_renew"]],
                         e["mandates_to_renew"])
        self.assertEqual([r["customer"] for r in d["mandates_to_renew"] if r["status"] == "expired" and r["mail"] is None],
                         e["renewal_without_draft"])
        self.assertEqual([r["mail"] for r in d["mandates_to_renew"] if r["status"] == "expiring"], [None])
        self.assertEqual(d["checked"], dict.fromkeys(("new_attempts", "mails", "mandates_to_renew", "match_suggestions",
                                                       "paid_but_open", "double_payment"), True))
        ms = d["match_suggestions"]
        self.assertEqual([{k: x[k] for k in ("invoice", "customer", "amount")} for x in ms["double_payment"]],
                         e["double_payment"])
        self.assertEqual([{"customer": ln["customer"], "amount": ln["amount"], "category": ln["category"],
                           "candidates": [{"invoice": c["invoice"], "strength": c["strength"]} for c in ln["candidates"]]}
                          for ln in ms["lines"]], e["match_lines"])
        self.assertEqual(ms["without_candidate"], e["counts"]["without_candidate"])
        self.assertEqual([{k: x[k] for k in ("invoice", "customer", "amount")} for x in ms["paid_but_open"]],
                         e["paid_but_open"])
        # the fixed top-level keys both builders code against
        for k in ("version", "check", "as_of", "since_days", "period", "language", "mail_language", "counts",
                  "new_attempts", "suggested_day", "mails", "mandates_to_renew", "match_suggestions", "closing",
                  "paths"):
            self.assertIn(k, d, k)
        self.assertEqual((d["check"], d["as_of"], d["since_days"]), ("month", "2026-10-31", 90))
        # the exports run from the first failed collection (November 5, 2025) to the last bank line (October 28)
        self.assertEqual(d["period"], {"from": "2025-11-05", "to": "2026-10-28"})
        self.assertEqual(set(d["paths"]), {"month_report"})
        self.assertEqual([t["id"] for t in d["closing"]["twikey"]], ["failure-decoder", "unmatched-payments"])
        self.assertEqual(d["closing"]["demo"]["id"], "demo")
        self.assertEqual(d["closing"]["text"], "Claude prepared this once, from your exports of November 2025 to "
                                               "October 2026. Nothing was sent and no bank file was written.")
        # month.json in the workspace holds the same coded content
        self.assertEqual(load(os.path.join(self.box.home, "month.json")), d)

    def test_month_prints_only_the_path_and_the_pack_holds_the_names(self):
        before = set(os.listdir(self.box.raw)) | {"twikey-xray-key.json"}
        ws_before = set(os.listdir(self.box.home))
        code, out, err = self.box.cli("month")
        self.assertEqual(code, 0, err)
        path = out.strip()
        self.assertEqual(out, path + "\n")  # the path, nothing else
        self.assertTrue(path.startswith(self.box.raw + os.sep))
        self.assertRegex(os.path.basename(path), r"^twikey-xray-month-2026-10-31(-\d+)?\.md$")
        self.assertEqual(leaks(out + err), [])
        # nothing written but the work pack next to the exports and month.json in the workspace
        self.assertEqual(set(os.listdir(self.box.raw)) - before, {os.path.basename(path)})
        self.assertEqual(set(os.listdir(self.box.home)) - ws_before, set() if "month.json" in ws_before
                         else {"month.json"})
        text = read_text(path)
        for code_, name in E["month"]["names"].items():
            self.assertIn(name, text, code_)
        self.assertNotRegex(text, r"(?<![A-Za-z0-9])(C0\d\d|I0\d{3}|M0\d\d)(?![A-Za-z0-9])")  # no code left
        self.assertNotIn("{", text)
        self.assertEqual(text.count("demo.html"), 1)
        self.assertEqual(text.count("Check each draft, then send it yourself."), 2)  # mails and renewals
        self.assertIn("## 1. Collections worth a new attempt", text)
        self.assertIn("Suggested day: day 25 of the month, next on November 25, 2026. Of the two collection days with "
                      "20 collections or more over two months or more in your files, day 25 has the lowest failure "
                      "rate: 0.0% (21 collections over three months, none of them failed), against 21.7% for all "
                      "collections. "
                      "At least 14 days from today, the usual SEPA pre-notification period. Check what your mandate "
                      "terms say.", text)
        self.assertIn("Made on November 3, 2026", text)  # today, injected: no test depends on the real date
        self.assertIn("### Paid twice", text)
        self.assertIn("A collection on it before December 20, 2026 keeps it valid", text)
        self.assertNotIn("€0.00", text)
        self.assertIn("Nothing was sent and no bank file was written.", text)
        for bank_file in ("<?xml", "pain.008", "CstmrDrctDbtInitn", "PmtInf"):
            self.assertNotIn(bank_file, text)
        code, out2, _ = self.box.cli("month")
        self.assertNotEqual(out2.strip(), path)  # a second work pack never overwrites the first

    def test_month_mails_in_every_language(self):
        for lang in ("en", "nl", "fr"):
            for mail_lang in ("en", "nl", "fr"):
                d = self.run_json("month", "--lang", lang, "--mail-lang", mail_lang)
                self.assertEqual((d["language"], d["mail_language"]), (lang, mail_lang))
                texts = [m["subject"] + m["body"] for m in d["mails"]]
                texts += [r["mail"]["subject"] + r["mail"]["body"] for r in d["mandates_to_renew"] if r["mail"]]
                self.assertEqual(len(texts), 7)  # five customers in part 2, two renewals (C022, C027)
                for t in texts:
                    self.assertNotIn("{", t)
                    self.assertNotIn("}", t)
                    self.assertNotIn("Twikey", t)
                    self.assertNotIn(";", t)
                    self.assertNotIn("—", t)
                company = {"en": "[your company name]", "nl": "[naam van je bedrijf]",
                           "fr": "[nom de votre entreprise]"}[mail_lang]
                self.assertTrue(all(company in t for t in texts))
                body = d["mails"][0]["body"]  # C006, a new attempt on the suggested day
                self.assertIn({"en": "November 25, 2026", "nl": "25 november 2026", "fr": "25 novembre 2026"}[mail_lang],
                              body)
                self.assertIn({"en": "€550.50", "nl": "€550,50", "fr": "€550,50"}[mail_lang], body)
                self.assertIn("C006", body)
                self.assertIn("I0071", body)
                if mail_lang == "nl":
                    for t in texts:
                        self.assertNotRegex(t, r"(?i)\b(u|uw)\b")
                        self.assertNotRegex(t, r"(?i)herprobeerd|incasso")
                pack = read_text(d["paths"]["month_report"])  # the work pack, with names
                self.assertNotIn(";", pack)
                self.assertNotIn("—", pack)
                self.assertNotIn("{", pack)
                self.assertNotRegex(pack, r"\d{4}-\d{2}-\d{2}")  # dates written out
                self.assertEqual(pack.count({"en": "Check each draft, then send it yourself.",
                                             "nl": "Kijk elk concept na en verstuur het dan zelf.",
                                             "fr": "Vérifiez chaque brouillon, puis envoyez-le vous-même."}[lang]), 2)
                if lang == "nl":
                    self.assertNotRegex(pack, r"\b(u|uw)\b")
                    self.assertNotIn("herprobeerd", pack)
                if mail_lang == "fr":  # the vous form, never tu
                    for t in texts:
                        self.assertRegex(t.lower(), r"\b(vous|votre|vos)\b")
                        self.assertNotRegex(t.lower(), r"\b(tu|ton|ta|tes|toi)\b")
        code, data = self.box.cli_json("month", "--since-days", "0")
        self.assertEqual(code, 1)

    def test_golive(self):
        e = E["golive"]
        for tool, listed in e["tools"].items():
            d = self.run_json("golive", "--tool", tool)
            self.assertEqual(d["tool"]["listed_as"], [listed] if listed else [], tool)
        for k in ("customers", "direct_debit_customers", "invoices_per_month", "mandates_core", "mandates_b2b",
                  "mandates_to_renew", "mandates_never_used", "b2b_not_confirmed", "failed_per_month",
                  "open_receivables", "overdue"):
            self.assertEqual(d[k], e[k], k)
        # one definition of mandates to renew in golive, steps and month
        steps = {i["id"]: i for i in self.run_json("steps")["items"]}
        self.assertEqual(d["mandates_to_renew"], steps["mandate_renew"]["count"])
        self.assertEqual(d["mandates_to_renew"], self.run_json("month")["counts"]["mandates_to_renew"])
        d = self.run_json("golive", "--tool", "Exact")
        self.assertEqual(d["tool"]["partners_page"], "https://www.twikey.com/partners.html")
        self.assertNotIn("package", d["tool"])
        self.assertNotIn("ERP", json.dumps(d))  # no package claim for partner connectors
        self.assertNotIn("Not a Twikey line", json.dumps(d))
        self.assertEqual(d["pricing_page"], "https://www.twikey.com/pricing.html")
        code, out, err = self.box.cli("golive", "--tool", "Exact")
        self.assertEqual(out.count("pricing.html"), 1)  # the pricing page is linked once
        self.assertIn("Listed on Twikey's partners page", out)

    def test_lang_before_or_after_the_command_and_local_number_format(self):
        for argv in (["--lang", "nl", "terms"], ["terms", "--lang", "nl"]):
            code, out, err = self.box.cli(*argv)
            self.assertEqual(code, 0, err)
            self.assertIn("Openstaande vorderingen €74.335,50, waarvan vervallen €42.068,00.", out)
            self.assertIn("61,1 dagen", out)
            self.assertIn("31 oktober 2026", out)
        code, out, err = self.box.cli("decode", "--lang", "fr")
        self.assertIn("40,0%", out)
        self.assertIn("€12.484,50", out)
        code, out, err = self.box.cli("decode")
        self.assertIn("40.0%", out)
        self.assertIn("€12,484.50", out)
        code, out, err = self.box.cli("steps", "--lang", "nl")
        self.assertIn("168 facturen die meer dan zeven dagen te laat zijn: 168 × (een herinnering sturen · opvolgen) = "
                      "336 stappen (14,0 per maand over 12 maanden)", out)
        self.assertIn("Totaal: 205 items, 462 stappen (de regels gaan over verschillende periodes).", out)
        code, out, err = self.box.cli("--lang", "fr", "steps")
        self.assertIn("Total : 205 éléments, 462 étapes (les lignes couvrent des périodes différentes).", out)
        self.assertIn("(1,7 par mois sur 3 mois)", out)

    def test_dutch_and_french_output_is_fully_translated(self):
        from xray import reasons
        words = ("the|and|to|with|from|for|failed|collections?|payments?|invoices?|months?|none|days?|Expired|Rule|"
                 "Method|Customers?|Ledger|Workspace|Raw folder|Mandates|overdue|Facts|Accounting|Package|"
                 "not checked")
        # "of" and "open" are Dutch words too, "Total" and "Questions" are French
        english = {"nl": re.compile(r"\b(%s|Total|Questions)\b" % words), "fr": re.compile(r"\b(%s|of|open)\b" % words)}
        allowed = list(reasons.EPC_SDD.values()) + ["findings.md", "go-live-plan.md", "Twikey Payment X-ray"]
        outputs = []
        with Sandbox() as s:  # intake in its own workspace, so self.box keeps its ledger
            for lang in ("nl", "fr"):
                code, out, err = s.cli("demo", "--raw", s.raw, "--lang", lang)
                self.assertEqual(code, 0, err)
                outputs.append((lang, ["demo"], out.split("\n", 1)[1]))  # the first line names the scratch folder
        for lang in ("nl", "fr"):
            for argv in (["decode"], ["mandates"], ["match"], ["terms"], ["steps"], ["golive", "--tool", "Exact"],
                         ["status"]):
                code, out, err = self.box.cli(*(argv + ["--lang", lang]))
                self.assertEqual(code, 0, err)
                outputs.append((lang, argv, out))
        for lang, argv, out in outputs:
            for line in out.splitlines():
                if re.match(r"^Twikey( \([^)]+\))? ?: ", line):
                    continue  # the Twikey lines are checked word for word in test_claims
                for a in allowed:
                    line = line.replace(a, "")
                line = re.sub(r"https://\S+", "", line)
                self.assertIsNone(english[lang].search(line), (lang, argv, line))
        # the example in the fix list: dates and months in the same language as the words around them
        for lang, want in (("nl", "(5 november 2025 tot 5 oktober 2026, 12 maanden)"),
                           ("fr", "(5 novembre 2025 à 5 octobre 2026, 12 mois)")):
            self.assertIn(want, self.box.cli("decode", "--lang", lang)[1])

    def test_decode_names_codes_not_on_twikeys_page(self):
        code, out, err = self.box.cli("decode")
        self.assertIn("Codes not on Twikey's reason-code page: ED05 (EPC rulebook reason: Settlement of the "
                      "collection failed)", out)
        self.assertNotIn("Unknown codes", out)
        # the EPC text exists only in English: Dutch and French say so, as they do for an English Twikey line
        self.assertIn("ED05 (reden volgens het EPC-rulebook, in het Engels: Settlement of the collection failed)",
                      self.box.cli("decode", "--lang", "nl")[1])
        self.assertIn("ED05 (motif selon le rulebook de l'EPC, en anglais : Settlement of the collection failed)",
                      self.box.cli("decode", "--lang", "fr")[1])

    def test_french_small_numbers_in_words_in_sentences(self):
        code, out, err = self.box.cli("golive", "--lang", "fr")
        self.assertEqual(code, 0, err)
        self.assertIn("Mandats : 19 Core, trois B2B, quatre à renouveler (expirés, ou qui expirent dans les 90 "
                      "jours), deux jamais utilisés depuis la signature, un B2B non confirmé auprès de la banque du "
                      "client", out)
        self.assertIn("paie après des prélèvements échoués trois", out)
        self.assertIn("trop tôt pour le dire aucun", out)
        code, out, err = self.box.cli("mandates", "--lang", "fr")
        self.assertIn("présenté encore une fois après son expiration", out)

    def test_dutch_labels_read_naturally(self):
        code, out, err = self.box.cli("steps", "--lang", "nl")
        self.assertIn("betalingen om met de hand te boeken (niet gekoppeld, gedeeltelijk of gebundeld)", out)
        self.assertIn("1 betaalde factuur die nog openstaat in je boekhouding", out)
        self.assertNotIn("match", out)
        self.assertIn("  Niet gekoppeld: drie,", self.box.cli("match", "--lang", "nl")[1])

    def test_french_twikey_labels_have_a_space_before_the_colon(self):
        code, out, err = self.box.cli("decode", "--lang", "fr")
        self.assertIn("Twikey : « Cela nous permet", out)
        self.assertIn(" Formule : « Gestion des échecs", out)
        self.assertNotRegex(out, r"Twikey:|Formule:")
        # the categories per reason code too
        self.assertIn("échange : 3, nouveau mandat : 1", out)
        self.assertNotRegex(out, r"\w: \d")

    def test_mandate_counts_say_what_they_count(self):
        code, out, err = self.box.cli("mandates")
        self.assertIn("22 rows (19 Core, three B2B), 21 references.", out)

    def test_status_never_mixes_periods(self):
        code, out, err = self.box.cli("status")
        self.assertEqual(code, 0, err)
        self.assertIn("Collections in the bank statements: 42 (August 4, 2026 to October 26, 2026)", out)
        self.assertIn("Failed collections: 19 (November 5, 2025 to October 5, 2026)", out)
        self.assertNotIn("42 collections, 18 failed", out)

    def test_xml_files_show_entries_not_lines(self):
        code, out, err = self.box.cli("intake")
        # August statement: 11 transfers to account 1 (C026-C031 on the 16th, C032-C036 on the 28th), four direct
        # debit batches (Aug 4 Core, Aug 4 B2B, Aug 18 retry, Aug 25 Core) and one supplier payment = 16 entries
        self.assertIn("file 1 (camt.053, 16 entries)", out)
        self.assertIn("file 8 (pain.002, 4 entries)", out)
        self.assertNotRegex(out, r"(camt|pain)\.\d+, \d+ lines")

    # ------------------------------------------------------------------ privacy

    def test_no_command_prints_a_name(self):
        runs = [["status"], ["intake"], ["decode"], ["decode", "--lang", "nl"], ["decode", "--lang", "fr"],
                ["mandates"], ["match"], ["terms"], ["steps"], ["steps", "--lang", "nl"], ["steps", "--lang", "fr"],
                ["month"], ["month", "--lang", "nl"], ["month", "--lang", "fr", "--mail-lang", "nl"],
                ["golive", "--tool", "Exact"]]
        for argv in runs:
            for extra in ([], ["--json"]):
                code, out, err = self.box.cli(*(argv + extra))
                self.assertEqual(code, 0, (argv, err))
                self.assertEqual(leaks(out + err), [], argv + extra)

    def test_workspace_holds_only_coded_data(self):
        for name in os.listdir(self.box.home):
            self.assertEqual(leaks(read_text(os.path.join(self.box.home, name))), [], name)

    def test_report_puts_names_back_and_prints_only_its_path(self):
        pbo = self.run_json("match")["paid_but_open"]["invoices"][0]
        with open(os.path.join(self.box.home, "findings.md"), "w", encoding="utf-8") as f:
            f.write("# Findings\n\nAs of October 31, 2026. Customers appear as codes. The report puts the names "
                    "back.\n\n## What we found\n\n- 19 failed collections, €12,484.50.\n- C001 is fine.\n"
                    "- Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-xray\n\n"
                    "## 1. Failed collections\n\nM004 changed account. %s is paid at the bank but open.\n" % pbo)
        with open(os.path.join(self.box.home, "go-live-plan.md"), "w", encoding="utf-8") as f:
            f.write("# Go-live plan\n\nStart with C001.\n\nAsk Twikey for a demo: https://www.twikey.com/demo.html\n")
        code, out, err = self.box.cli("report")
        self.assertEqual(code, 0, err)
        path = out.strip()
        self.assertEqual(out, path + "\n")
        self.assertTrue(path.startswith(self.box.raw + os.sep))
        self.assertEqual(leaks(out), [])
        text = read_text(path)
        self.assertIn(E["report"]["C001"], text)
        self.assertIn(E["report"]["M004"], text)
        self.assertIn("VF-0421", text)  # C028's September invoice: 353 + 40 + 28
        self.assertNotIn("C001 is fine", text)
        # the named report never says customers appear as codes
        self.assertNotIn("appear as codes", text)
        self.assertNotIn("puts the names back", text)
        self.assertIn("Names and numbers were put back on your own computer. Claude saw amounts, dates, counts, "
                      "statuses and bank reason codes, with codes in place of names, account numbers, mandate "
                      "references, invoice numbers and payment references.", text)
        self.assertNotIn("only saw codes", text)
        self.assertIn("As of October 31, 2026.", text)
        # it opens with "What we found", right under the title
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(lines[1], "## What we found")
        self.assertTrue(lines[2].startswith("- 19 failed collections"))
        # one call to action, once, before the footer, with the plugin's UTM tags
        demo = ("Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin"
                "&utm_campaign=payment-xray")
        self.assertEqual(text.count("demo.html"), 1)
        self.assertLess(text.index(demo), text.index("---"))
        self.assertNotIn("contact.html", text)
        self.assertIn("file 5: factuurhistoriek.csv", text)  # the report, on the user's computer, names the files
        self.assertTrue(text.rstrip().endswith("Twikey Payment X-ray 0.2.2. The numbers come from your own exports."))
        code, out2, _ = self.box.cli("report")
        self.assertNotEqual(out2.strip(), path)  # a second report never overwrites the first

    def test_report_frame_in_dutch_and_french(self):
        # M021 has no reference in the mandate export
        with open(os.path.join(self.box.home, "findings.md"), "w", encoding="utf-8") as f:
            f.write("# Findings\n\n## 2. Mandaten\n\nZonder referentie: M021.\n")
        for lang, files, label, no_ref in (
                ("nl", "Gelezen bestanden:", "- bestand 5: factuurhistoriek.csv", "M021 (geen referentie in je export)"),
                ("fr", "Fichiers lus :", "- fichier 5 : factuurhistoriek.csv",
                 "M021 (pas de référence dans votre export)")):
            code, out, err = self.box.cli("report", "--lang", lang)
            self.assertEqual(code, 0, err)
            text = read_text(out.strip())
            self.assertIn(files, text)
            self.assertIn(label, text)
            self.assertIn(no_ref, text)
            self.assertNotRegex(text, r"\bfile \d|no reference")


class MissingExportsTest(unittest.TestCase):
    """Only the invoice history and the failed-collections CSV: no bank statement, no mandate list."""

    def test_sections_without_their_export_say_not_checked(self):
        with Sandbox() as s:
            s.copy_demo(["factuurhistoriek.csv", "impayes-2025-11_2026-07.csv"])
            self.assertEqual(s.cli("--as-of", "2026-07-31", "init", "--raw", s.raw)[0], 0)
            self.assertEqual(s.cli("intake")[0], 0)
            code, d = s.cli_json("month", "--since-days", "200")
            self.assertEqual(code, 0, d)
            self.assertEqual(d["checked"], {"new_attempts": True, "mails": True, "mandates_to_renew": False,
                                            "match_suggestions": False, "paid_but_open": False,
                                            "double_payment": False})
            self.assertEqual(d["not_checked"]["match_suggestions"], "Not checked: no bank statement in your exports.")
            pack = read_text(d["paths"]["month_report"])
            self.assertIn("## 3. Mandates to renew\n\nNot checked: no mandate list in your exports.", pack)
            self.assertIn("## 4. Match suggestions\n\nNot checked: no bank statement in your exports.", pack)
            code, out, err = s.cli("steps")
            self.assertIn("Not checked: no bank statement in your exports. Not counted for that reason: payments to "
                          "book by hand (no match, partial or bundled), invoices paid twice and paid invoices still "
                          "open in your books.", out)
            self.assertIn("Not checked: no mandate list in your exports.", out)
            self.assertNotIn("None in your files: mandates", out)
            code, data = s.cli_json("steps")
            self.assertEqual(sorted(data["not_checked"]), ["double_payment", "mandate_fix", "mandate_renew",
                                                           "paid_but_open", "unmatched"])
            for cmd, line in (("match", "Not checked: no bank statement in your exports."),
                              ("mandates", "Not checked: no mandate list in your exports.")):
                code, out, err = s.cli(cmd)
                self.assertEqual(out.splitlines()[0], line, cmd)
                self.assertFalse(s.cli_json(cmd)[1]["checked"])
            self.assertTrue(s.cli_json("decode")[1]["checked"])


class IntakeLanguageTest(unittest.TestCase):
    def test_what_the_file_readers_say_comes_in_the_users_language(self):
        with Sandbox() as s:
            s.write_raw("export.xlsx", "not a csv")
            s.write_raw("lijst.csv", "a;b\n1;2\n")
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake", "--lang", "nl")
            self.assertEqual(code, 2, err)
            self.assertIn("bestand 1: Rekenbladen worden niet gelezen. Bewaar het blad als CSV.", out)
            self.assertIn("bestand 2 (CSV, 2 regels): geen kopregel met bekende kolomnamen in de eerste 30 regels", out)
            self.assertNotIn("file 1", out)
            code, out, err = s.cli("intake", "--lang", "fr")
            self.assertIn("Les tableurs ne sont pas lus. Enregistrez la feuille en CSV.", out)
            self.assertIn("fichier 2", out)


class MonthErrorsTest(unittest.TestCase):
    def test_no_key_file(self):
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw)
            os.remove(os.path.join(s.raw, "twikey-xray-key.json"))
            code, out, err = s.cli("month")
            self.assertEqual((code, out), (1, ""))
            self.assertIn("No key file next to the exports. Run `intake` first.", err)

    def test_raw_folder_missing(self):
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw)
            shutil.rmtree(s.raw)
            code, data = s.cli_json("month")
            self.assertEqual(code, 1)
            self.assertEqual(data["error"], "Raw folder not found. Run `init --raw <folder>` first.")
            self.assertFalse(os.path.exists(os.path.join(s.home, "month.json")))


class RepeatedFlagsTest(unittest.TestCase):
    def test_map_and_skip_keep_every_flag(self):
        from tests.helpers import twikey_xray
        a = twikey_xray.build_parser().parse_args(["intake", "--map", "1:#1=amount", "--map", "2:#2=amount",
                                                   "--skip", "3", "--skip", "4", "5"])
        self.assertEqual(a.map, ["1:#1=amount", "2:#2=amount"])
        self.assertEqual(a.skip, ["3", "4", "5"])
        a = twikey_xray.build_parser().parse_args(["intake", "--map", "1:#1=amount", "2:#2=amount"])
        self.assertEqual(a.map, ["1:#1=amount", "2:#2=amount"])


class DemoFilesTest(unittest.TestCase):
    def test_leak_detector_fires(self):
        for text in ("CAFÉ DEMO VOF paid", "Bakkerij Voorbeeld", "iban BE10999000100104", "VF-0421", "FICT-M-0004",
                     "K1001", "boekhouding@klant01.example", "Groothandel Fictief NV"):
            self.assertNotEqual(leaks(text), [], text)
        self.assertEqual(leaks("C001 paid €425.50 on 2026-10-05, M004, I0327"), [])

    def test_demo_files_are_rebuilt_from_the_spec(self):
        tmp = tempfile.mkdtemp(prefix="xray-demo-")
        try:
            names = make_demo.main(tmp)
            self.assertEqual(names, sorted(f for f in os.listdir(DEMO)))
            match, mismatch, errors = filecmp.cmpfiles(DEMO, tmp, names, shallow=False)
            self.assertEqual((mismatch, errors), ([], []))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_expected_file_was_written_for_this_spec(self):
        self.assertEqual(E["as_of"], make_demo.AS_OF.isoformat())
        self.assertEqual(load(os.path.join(os.path.dirname(__file__), "expected_demo.json"))["as_of"], "2026-10-31")


if __name__ == "__main__":
    unittest.main()
