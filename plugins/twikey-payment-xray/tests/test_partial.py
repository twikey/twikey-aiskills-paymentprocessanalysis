"""Partial export sets, built from the demo files only: a check or a part of one that needs an export the user did
not give says "Not checked" and names it. It never prints none, zero or €0.00 for it, in text, --json, month.json
or the work pack."""
import datetime as dt
import json
import os
import unittest

from tests.helpers import Sandbox, read_text
from tests.test_checks import coll, failed, inv, line, mandate
from xray import checks, month
from xray import cli_text
from xray.common import DEFAULT_CONFIG

D = dt.date
BANK = ["camt053-2026-08.xml", "camt053-2026-09.xml", "camt053-2026-10.xml"]
INVOICES = ["factuurhistoriek.csv"]
MANDATES = ["mandates-export.csv"]
PAIN002 = ["pain002-2026-08.xml", "pain002-2026-09.xml", "pain002-2026-10.xml"]
NO_INVOICES = "Not checked: no invoice list in your exports."
NO_FAILURES = ("Not checked: no file with failed collections in your exports (a pain.002, a camt.053 or camt.054 "
               "statement, or a failed-collections export).")
NO_REJECTIONS = ("Not checked: no pain.002 status report or failed-collections export in your exports. Not counted "
                 "for that reason: collections rejected or refused before the collection date.")
NO_RETURNS = ("Not checked: no camt.053 or camt.054 statement or failed-collections export in your exports. Not "
              "counted for that reason: collections returned or refunded after the collection date.")


class PartialSet:
    """A sandbox with some of the demo files, intake done, as of the demo date."""

    def __init__(self, names):
        self.box = Sandbox()
        self.names = names

    def __enter__(self):
        s = self.box.__enter__()
        s.copy_demo(self.names)
        assert s.cli("--as-of", "2026-10-31", "init", "--raw", s.raw)[0] == 0
        assert s.cli("intake")[0] == 0
        return self

    def __exit__(self, *exc):
        self.box.__exit__(*exc)

    def text(self, *argv):
        code, out, err = self.box.cli(*argv)
        assert code == 0, err
        return out

    def json(self, *argv):
        code, data = self.box.cli_json(*argv)
        assert code == 0, data
        return data

    def month(self, *argv):
        d = self.json("month", *argv)
        return d, read_text(d["paths"]["month_report"])


class BankStatementOnlyTest(unittest.TestCase):
    """The case of the real test run: camt.053 statements, no invoice list, no mandate list."""

    @classmethod
    def setUpClass(cls):
        cls.p = PartialSet(BANK).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.p.__exit__(None, None, None)

    def test_terms_says_not_checked_and_nothing_else(self):
        out = self.p.text("terms")
        self.assertEqual(out.splitlines()[0], NO_INVOICES)
        for word in ("€0.00", "Clockwork", "no customers", "Open receivables", "Aging", "code   terms"):
            self.assertNotIn(word, out)
        d = self.p.json("terms")
        self.assertFalse(d["checked"])
        self.assertEqual(d["not_checked"], NO_INVOICES)
        for k in ("profiles", "customers", "open_receivables", "overdue", "aging", "dso_90d"):
            self.assertIsNone(d[k], k)
        self.assertEqual(self.p.text("--lang", "nl", "terms").splitlines()[0],
                         "Niet nagekeken: geen factuurlijst in je exports.")
        self.assertEqual(self.p.text("--lang", "fr", "terms").splitlines()[0],
                         "Non vérifié : aucune liste de factures dans vos exports.")

    def test_match_counts_the_bank_payments_and_checks_nothing_else(self):
        lines = self.p.text("match").splitlines()
        self.assertEqual(lines[0], "Bank payments in: 29, €32,463.50 (August 16, 2026 to October 20, 2026).")
        self.assertEqual(lines[1], NO_INVOICES)
        out = "\n".join(lines)
        for word in ("none", "€0.00", "Paid twice", "Matched to an invoice", "No match", "Method:"):
            self.assertNotIn(word, out)
        d = self.p.json("match")
        self.assertFalse(d["checked"])
        self.assertEqual(d["credit_lines"], {"count": 29, "amount": 32463.5})
        for k in checks.MATCH_GROUPS:
            self.assertIsNone(d[k], k)

    def test_month_match_parts_are_not_checked(self):
        d, pack = self.p.month("--since-days", "120")
        for k in ("match_suggestions", "paid_but_open", "double_payment"):
            self.assertFalse(d["checked"][k], k)
            self.assertEqual(d["not_checked"][k], NO_INVOICES)
        self.assertTrue(d["checked"]["new_attempts"])
        self.assertIsNone(d["match_suggestions"])
        for k in ("match_lines", "without_candidate", "paid_but_open", "double_payment", "mandates_to_renew"):
            self.assertIsNone(d["counts"][k], k)
        self.assertIsNone(d["older_open"])
        self.assertIn("## 4. Match suggestions\n\nNot checked: no invoice list in your exports.\n", pack)
        self.assertNotIn("### Paid twice", pack)
        self.assertNotIn("Payments without a candidate", pack)
        # a collection without an invoice says the list is missing, never that no invoice was found
        self.assertIn("No invoice list in your exports: check in your books that the amount is still owed.", pack)
        self.assertNotIn("No invoice found", pack)
        self.assertNotIn("No invoice was found", pack)
        workspace = json.loads(read_text(os.path.join(self.p.box.home, "month.json")))
        self.assertEqual(workspace["checked"], d["checked"])

    def test_steps_name_the_invoice_list_for_matching(self):
        out = self.p.text("steps")
        self.assertIn("Not checked: no invoice list in your exports. Not counted for that reason: payments to book "
                      "by hand (no match, partial or bundled), invoices paid twice, paid invoices still open in your "
                      "books and invoices more than seven days late.", out)
        self.assertNotIn("payments to book by hand (no match, partial or bundled): 18", out)
        none_line = [ln for ln in out.splitlines() if ln.startswith("None in your files:")][0]
        self.assertNotIn("paid twice", none_line)  # not checked is never "none in your files"
        by = {i["id"]: i for i in self.p.json("steps")["items"]}
        for k in ("unmatched", "double_payment", "paid_but_open", "late_invoice", "mandate_renew"):
            self.assertEqual((by[k]["checked"], by[k]["count"], by[k]["steps_total"]), (False, None, None), k)
        self.assertEqual(by["unmatched"]["not_checked"], NO_INVOICES)

    def test_decode_names_the_kind_of_failure_it_could_not_count(self):
        lines = self.p.text("decode").splitlines()
        self.assertTrue(lines[0].startswith("Failed collections: four, €2,377.00"))
        self.assertEqual(lines[1], NO_REJECTIONS)
        d = self.p.json("decode")
        self.assertEqual(d["kinds_checked"], {"rejections": False, "returns": True})
        self.assertEqual(d["not_counted"], [NO_REJECTIONS])

    def test_golive_leaves_out_what_it_could_not_count(self):
        out = self.p.text("golive")
        for word in ("Customers:", "Open receivables:", "Payer profiles:", "Mandates:", "€0.00"):
            self.assertNotIn(word, out)
        self.assertIn("Not checked: no invoice list in your exports. Not counted for that reason: customers, invoices "
                      "a month, open receivables and payer profiles.", out)
        self.assertIn("Not checked: no mandate list in your exports. Not counted for that reason: mandates.", out)
        d = self.p.json("golive")
        for k in ("customers", "open_receivables", "overdue", "profiles", "mandates_core", "mandates_to_renew"):
            self.assertIsNone(d[k], k)
        self.assertEqual(d["failed_per_month"], 2.0)

    def test_status_counts_what_was_read(self):
        out = self.p.text("status")
        self.assertIn("  Bank payments in: 29 (August 16, 2026 to October 20, 2026)", out)


class NoFailuresInTheFilesTest(unittest.TestCase):
    """A statement with collections and no failed one: none in your files, and no empty sections."""

    def test_decode_with_zero_failures(self):
        with PartialSet(BANK[:1]) as p:
            out = p.text("decode")
            lines = out.splitlines()
            self.assertEqual(lines[0], "Failed collections: none in your files.")
            self.assertEqual(lines[1], NO_REJECTIONS)
            for word in ("€0.00", "By reason code", "What the codes point to", "(- to -", "no months"):
                self.assertNotIn(word, out)
            d = p.json("decode")
            self.assertTrue(d["checked"])
            self.assertEqual((d["total"]["count"], d["by_code"], d["by_category"]), (0, [], {}))
            self.assertEqual(p.text("--lang", "nl", "decode").splitlines()[0],
                             "Mislukte domiciliëringen: geen in je bestanden.")
            self.assertEqual(p.text("--lang", "fr", "decode").splitlines()[0],
                             "Prélèvements échoués : aucun dans vos fichiers.")


class InvoicesOnlyTest(unittest.TestCase):
    def test_no_failures_file_leaves_pays_after_failures_unchecked(self):
        with PartialSet(INVOICES) as p:
            out = p.text("terms")
            self.assertNotIn("Pays after failed collections (", out)
            self.assertIn("Clockwork (pays on average at most five days late, failed collections not checked): 23 "
                          "customers", out)
            self.assertIn(NO_FAILURES + " Not counted for that reason: customers who pay after failed collections.",
                          out)
            d = p.json("terms")
            self.assertIsNone(d["profiles"]["after_failures"])
            self.assertTrue(all(r["failed_collections"] is None for r in d["customers"]))
            self.assertEqual(d["open_receivables"], 74335.5)  # the invoice list is there: checked
            g = p.json("golive")
            self.assertIsNone(g["profiles"]["after_failures"])
            self.assertIsNone(g["failed_per_month"])
            out = p.text("status")
            self.assertIn("  Bank payments in: no bank statement in your exports", out)
            self.assertIn("  Collections in the bank statements: no camt.053 or camt.054 statement in your exports",
                          out)
            self.assertIn("  Failed collections: no file with failed collections in your exports", out)
            self.assertNotIn(": none", out)
            d, pack = p.month()
            self.assertIsNone(d["older_open"])
            self.assertEqual(set(d["closed"].values()), {None})
            self.assertIsNone(d["new_attempts"])
            self.assertIn("## 1. Collections worth a new attempt\n\n" + NO_FAILURES, pack)
            self.assertNotIn("None.", pack)


class MandatesOnlyTest(unittest.TestCase):
    def test_issues_that_need_collections_are_not_checked(self):
        with PartialSet(MANDATES) as p:
            out = p.text("mandates")
            self.assertNotIn("Collections from more than one account:", out)
            self.assertNotIn("Last collection unknown:", out)
            self.assertIn("Expired: no collection presented for 36 months: three", out)  # the list has the dates
            self.assertIn(NO_RETURNS.split(" Not counted")[0] + " Not counted for that reason: mandates whose last "
                          "collection is unknown.", out)
            self.assertIn("Not counted for that reason: collections from more than one account.", out)
            d = p.json("mandates")
            self.assertIsNone(d["issues"]["iban_changed"])
            self.assertIsNone(d["counts"]["last_collection_unknown"])
            self.assertEqual(d["to_renew"], 4)
            self.assertEqual(sorted(d["not_checked_issues"]), ["iban_changed", "last_collection_unknown"])
            d, pack = p.month()
            self.assertTrue(d["checked"]["mandates_to_renew"])
            self.assertEqual({r["still_active"] for r in d["mandates_to_renew"]}, {None})
            self.assertIn("Whether it is still active is not checked: that needs the invoice list and a file with "
                          "collections in your exports.", pack)
            self.assertNotIn("No open invoice and no collection", pack)


class RejectionsOnlyTest(unittest.TestCase):
    def test_pain002_only(self):
        with PartialSet(PAIN002) as p:
            lines = p.text("decode").splitlines()
            self.assertTrue(lines[0].startswith("Failed collections: six, €4,903.00"))
            self.assertEqual(lines[1], NO_RETURNS)
            d = p.json("decode")
            self.assertIsNone(d["days_of_month_overall"])
            self.assertEqual(d["days_of_month_not_checked"], "Not checked: no camt.053 or camt.054 statement in "
                                                             "your exports.")
            d, pack = p.month()
            self.assertEqual(d["day_statistics"]["no_day_reason"], "not_checked")
            self.assertIsNone(d["day_statistics"]["overall_presented"])
            self.assertIn("Suggested day not checked: it needs the collections presented on each day, from a "
                          "camt.053 or camt.054 statement, and there is none in your exports.", pack)
            self.assertNotIn("Too little history", pack)


class InvoicesAndMandatesTest(unittest.TestCase):
    def test_no_bank_file(self):
        with PartialSet(INVOICES + MANDATES) as p:
            g = p.json("golive")
            self.assertEqual((g["customers"], g["mandates_to_renew"]), (41, 4))
            self.assertIsNone(g["failed_per_month"])
            self.assertEqual(sorted(g["not_checked"]), ["after_failures", "failed_per_month"])
            out = p.text("golive")
            self.assertNotIn("Failed collections a month", out)
            self.assertNotIn("pays after failed collections none", out)
            d, pack = p.month()
            self.assertEqual(d["not_checked"]["match_suggestions"], "Not checked: no bank statement in your exports.")
            self.assertIsNone(d["older_open"])
            # an open invoice is enough to call a customer active, so these are checked
            self.assertEqual({r["still_active"] for r in d["mandates_to_renew"]}, {True})


class SourcesTest(unittest.TestCase):
    def files(self, *kinds):
        return [{"format": "csv", "kind": k} if k in ("invoices", "mandates", "bank", "failed_collections")
                else {"format": k, "kind": "bank"} for k in kinds]

    def test_kinds_of_failure_file(self):
        s = checks.sources(self.files("camt.053"))
        self.assertEqual((s["failures"], s["rejections"], s["returns"], s["collected"]), (True, False, True, True))
        s = checks.sources(self.files("pain.002"))
        self.assertEqual((s["failures"], s["rejections"], s["returns"], s["collected"]), (True, True, False, False))
        s = checks.sources(self.files("failed_collections"))
        self.assertEqual((s["rejections"], s["returns"], s["collected"]), (True, True, False))
        # a mandate list with dates of last collection is enough for the 36-month rule
        s = checks.sources(self.files("mandates"), mandates=[mandate(last_collection_date="2024-01-01")])
        self.assertTrue(s["last_collection"])
        self.assertFalse(checks.sources(self.files("mandates"), mandates=[mandate()])["last_collection"])

    def test_without_intake_json_nothing_is_called_not_checked_on_a_guess(self):
        s = checks.sources(None, {"invoices": {}}, [mandate()], [coll("2026-09-01", "failed")], [])
        self.assertEqual((s["rejections"], s["returns"], s["collected"], s["last_collection"]),
                         (True, True, True, True))


class ChecksTest(unittest.TestCase):
    ON = D(2026, 10, 31)
    ALL = dict.fromkeys(checks.SOURCES, True)

    def test_match_without_invoices(self):
        r = checks.match({"invoices": {}}, [line(1, "2026-09-01", 10.0, "C1")], "nl")
        self.assertFalse(r["checked"])
        self.assertEqual(r["not_checked"], "Niet nagekeken: geen factuurlijst in je exports.")
        self.assertEqual(r["credit_lines"], {"count": 1, "amount": 10.0})
        self.assertIsNone(r["double"])

    def test_terms_without_failures(self):
        store = {"invoices": {"I1": inv("I1", "C1", 10.0, "PAID", paid="2026-09-01")}}
        r = checks.terms(store, dict(DEFAULT_CONFIG), self.ON, [], "fr", dict(self.ALL, failures=False))
        self.assertIsNone(r["profiles"]["after_failures"])
        self.assertEqual(r["rules"]["clockwork"], "paie en moyenne avec au plus cinq jours de retard, prélèvements "
                                                  "échoués non vérifiés")
        self.assertEqual(r["not_counted"], [checks.not_checked("failures", "fr") + " Pas comptés pour cette "
                                            "raison : clients qui paient après des prélèvements échoués."])
        # with the file, the profile is checked and the rule is the usual one
        r = checks.terms(store, dict(DEFAULT_CONFIG), self.ON, [], "en", self.ALL)
        self.assertEqual(r["profiles"]["after_failures"]["count"], 0)
        self.assertEqual(r["not_counted"], [])

    def test_mandates_without_a_date_of_last_collection(self):
        src = dict(self.ALL, last_collection=False, returns=False, collections=False, failures=False)
        r = checks.mandate_health([mandate(signed_date="2020-01-01")], [], self.ON, "en", src)
        self.assertTrue(r["checked"])
        for k in ("expired", "expiring_90_days", "unused_since_signing", "last_collection_unknown", "iban_changed"):
            self.assertIsNone(r["issues"][k], k)
        self.assertIsNone(r["to_renew"])
        self.assertEqual(r["issues"]["missing_reference"], [])  # the list alone checks this
        self.assertEqual(r["not_counted"][0], checks.not_checked("last_collection") + " Not counted for that "
                         "reason: expired mandates, mandates that expire within 90 days and mandates never used since "
                         "signing.")

    def test_steps_matching_needs_both_exports(self):
        store = {"invoices": {"I1": inv("I1", "C1", 10.0)}}
        r = checks.steps({"invoices": {}}, [], [], [line(1, "2026-09-01", 10.0, "C1")], self.ON)
        by = {i["id"]: i for i in r["items"]}
        self.assertEqual(by["unmatched"]["not_checked"], checks.not_checked("invoices"))
        self.assertIsNone(by["unmatched"]["count"])
        r = checks.steps(store, [], [], [], self.ON)
        self.assertEqual({i["id"]: i for i in r["items"]}["unmatched"]["not_checked"], checks.not_checked("bank"))
        # not checked comes last and counts for nothing in the totals
        self.assertEqual(r["items"][0]["id"], "late_invoice")
        self.assertEqual(r["total_items"], 1)


class MonthTest(unittest.TestCase):
    ON, TODAY = D(2026, 10, 31), D(2026, 11, 2)

    def prep(self, store=None, collections=(), mandates=(), bank=(), lang="en", **source):
        src = dict(dict.fromkeys(checks.SOURCES, True), **source)
        return month.prepare(store or {"invoices": {}}, list(mandates), list(collections), list(bank), self.ON, 90,
                             lang, None, self.TODAY, src)

    def test_no_invoice_list_in_every_language(self):
        for lang, item, mail in (
                ("en", "No invoice list in your exports: check in your books that the amount is still owed.",
                 "No invoice list in your exports: check in your books that each amount in this mail is still "
                 "owed before you send it."),
                ("nl", "Geen factuurlijst in je exports: kijk in je boekhouding na of het bedrag nog verschuldigd is.",
                 "Geen factuurlijst in je exports: kijk in je boekhouding na of elk bedrag in deze mail nog "
                 "verschuldigd is voor je de mail verstuurt."),
                ("fr", "Aucune liste de factures dans vos exports : vérifiez dans votre comptabilité que le montant "
                       "est encore dû.",
                 "Aucune liste de factures dans vos exports : vérifiez dans votre comptabilité que chaque montant "
                 "de ce mail est encore dû avant de l'envoyer.")):
            r = self.prep(collections=[failed("2026-10-05", cust="C1", code="M1")], lang=lang, invoices=False)
            text = month.render(r, today=self.TODAY)
            self.assertIn(item, text, lang)
            self.assertIn(mail, text, lang)
            self.assertIn(checks.not_checked("invoices", lang), text, lang)  # part 4

    def test_match_parts_need_the_invoices(self):
        r = self.prep(bank=[line(1, "2026-10-01", 10.0, "C1")], invoices=False)
        self.assertEqual({k: r["checked"][k] for k in ("match_suggestions", "paid_but_open", "double_payment")},
                         dict.fromkeys(("match_suggestions", "paid_but_open", "double_payment"), False))
        self.assertIsNone(r["match_suggestions"])
        self.assertIsNone(r["counts"]["without_candidate"])


class NewStringsTest(unittest.TestCase):
    """Every string added for not checked parts exists in English, Dutch and French, in the copy rules."""

    TABLES = (checks.NOT_CHECKED, checks.NOT_COUNTED, checks.KIND_LABELS, checks.ISSUE_LABELS, checks.PROFILE_LABELS,
              checks.CLOCKWORK_NO_FAILURES, checks.GOLIVE_LABELS)
    CLI_KEYS = ("dec_none", "match_none", "bank_in_missing", "coll_in_missing", "failed_in_missing",
                "gl_mandates_short")
    MONTH_KEYS = ("no_day_not_checked", "no_invoice_list", "no_invoice_mail_list", "active_unknown")

    def check(self, s, lang, where):
        for ch in (";", "—", "–", "!"):
            self.assertNotIn(ch, s, where)
        if lang == "nl":
            self.assertNotRegex(s, r"(?i)\b(u|uw|jouw)\b", where)
        if lang == "fr":
            self.assertNotRegex(s, r"(?i)\btu\b|\bton\b|\btes\b", where)

    def test_same_keys_and_copy_rules(self):
        for table in self.TABLES:
            self.assertEqual(set(table), {"en", "nl", "fr"})
            keys = [set(table[lang]) if isinstance(table[lang], dict) else None for lang in ("en", "nl", "fr")]
            self.assertEqual(keys[0], keys[1])
            self.assertEqual(keys[0], keys[2])
            for lang in ("en", "nl", "fr"):
                for s in (table[lang].values() if isinstance(table[lang], dict) else [table[lang]]):
                    self.check(s, lang, s)
        for lang in ("en", "nl", "fr"):
            for k in self.CLI_KEYS:
                self.check(cli_text.TEXT[lang][k], lang, k)
            for k in self.MONTH_KEYS:
                self.check(month.TEXT[lang][k], lang, k)


if __name__ == "__main__":
    unittest.main()
