"""The demo company against tests/expected_demo.json, written from the spec in make_demo.py."""
import filecmp
import os
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tests import make_demo
from tests.helpers import DEMO, Sandbox, expected, load, read_text

E = expected()

SECRETS = ([n for n in make_demo.NAMES if n] + [make_demo.LANDLORD, make_demo.COMPANY, make_demo.SUPPLIER,
                                                make_demo.BANK_BIC]
           + [n.rsplit(" ", 1)[0] for n in make_demo.NAMES if n and n.split()[-1] in ("BV", "NV", "SRL", "SA", "VOF", "VZW")]
           + ["huurwaarborg", "Betaling", "Aankoop goederen"]
           # file names can hold names, so no command prints them
           + [os.path.splitext(f)[0] for f in os.listdir(DEMO)])
PATTERNS = [re.compile(r"\bBE\d{2}\s?\d{4}"), re.compile(r"\bVF-\d{4}\b"), re.compile(r"(CORE|B2B)-GF-\d"),
            re.compile(r"\bGF-\d{8}-\d{4}\b"), re.compile(r"\bRF\d\d"), re.compile(r"\+\+\+")]


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
        for k, v in e.items():
            if k != "entries_per_file":
                self.assertEqual(t[k], v, k)
        self.assertEqual({f["file"]: f["entries"] for f in self.intake["files"]}, e["entries_per_file"])
        self.assertEqual({f["format"] for f in self.intake["files"]}, {"camt.053"})
        self.assertEqual(self.intake["skipped_files"], [])

    def test_xml_files_show_entries_not_lines(self):
        code, out, err = self.box.cli("intake")
        self.assertIn("  file 1 (camt.053, 32 entries): 41 records kept", out)
        self.assertIn("Intake: 12 statements read from the raw folder.", out)
        self.assertIn("Ledger: 14 customers paying by direct debit and 26 payers paying by transfer (40 codes), 14 "
                      "mandates.", out)
        self.assertNotRegex(out, r"\d+ lines")

    # ------------------------------------------------------------------ checks

    def test_decode(self):
        d, e = self.run_json("decode"), E["decode"]
        self.assertEqual(d["total"], e["total"])
        by = {r["code"] or "null": r for r in d["by_code"]}
        self.assertEqual(set(by), set(e["by_code"]))
        for code, want in e["by_code"].items():
            self.assertEqual((by[code]["count"], by[code]["amount"], by[code]["known"]),
                             (want["count"], want["amount"], want["known"]), code)
        self.assertEqual(by["null"]["label"], "reason not on the statement")
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
        coll = load(os.path.join(self.box.home, "collections.json"))
        with_failures = sorted({c["customer"] for c in coll if c["status"] == "failed"})
        self.assertEqual(with_failures, e["direct_debit_customers_with_failures"])
        # every return found the collection it returns: no failure keeps its booking date
        self.assertEqual(d["days_of_month_return_booked"], {})

    def test_payments(self):
        d, e = self.run_json("payments"), E["payments"]
        self.assertEqual(d["credit_lines"], e["credit_lines"])
        for g, want in e["groups"].items():
            self.assertEqual({k: d["groups"][g][k] for k in want}, want, g)
        self.assertEqual({k: d["by_hand"][k] for k in e["by_hand"]}, e["by_hand"])
        code, out, err = self.box.cli("payments")
        self.assertIn("To book by hand: 77 of 291 (26.5%), €95,713.00, 6.4 a month.", out)
        self.assertIn("  Structured communication with wrong check digits: two, €2,276.00  C029, C030", out)

    def test_steps(self):
        d, e = self.run_json("steps"), E["steps"]
        self.assertEqual([i["id"] for i in d["items"]], list(e["items"]))  # biggest steps_total first
        by = {i["id"]: i for i in d["items"]}
        for k, want in e["items"].items():
            self.assertEqual({f: by[k][f] for f in want}, want, k)
        for k, want in e["examples"].items():
            self.assertEqual(by[k]["examples"], want, k)
        for k in ("total_items", "total_steps", "per_month_total", "per_month_steps_total"):
            self.assertEqual(d[k], e[k], k)
        # the counts come from the other checks, never re-derived
        self.assertEqual(by["failed_new_attempt"]["count"], E["decode"]["by_category"]["new_attempt"]["count"])
        self.assertEqual(by["book_by_hand"]["count"], E["payments"]["by_hand"]["count"])
        code, out, err = self.box.cli("steps")
        lines = out.splitlines()
        self.assertEqual(lines[0], "Manual work in your bank statements, as of October 31, 2026.")
        self.assertEqual(lines[1], "77 incoming payments to book by hand (no valid structured communication): 77 × "
                                   "(find who paid · find what the payment is for · book it by hand) = 231 steps (6.4 a "
                                   "month over 12 months)")
        self.assertIn("9 failed collections worth a new attempt: 9 × (look up what the reason code means · tell the "
                      "customer · present the collection again in your bank tool · check whether it came through) = "
                      "36 steps (0.8 a month over 12 months)", lines)
        self.assertIn("Total: 94 items, 298 steps.", lines)
        self.assertIn("Per month: 7.8 items, 24.8 steps.", lines)
        self.assertIn("None in your bank statements: failed collections caused by your own file or setup.", lines)
        self.assertNotIn("0 ×", out)  # item types without items are named once, not counted

    def test_month(self):
        d, e = self.run_json("month"), E["month"]
        self.assertEqual(d["counts"], e["counts"])
        self.assertEqual(d["closed"], e["closed"])
        self.assertEqual([{k: a[k] for k in e["new_attempts"][0]} for a in d["new_attempts"]], e["new_attempts"])
        self.assertEqual({k: d["suggested_day"][k] for k in e["suggested_day"]}, e["suggested_day"])
        self.assertEqual([{k: m[k] for k in e["mails"][0]} for m in d["mails"]], e["mails"])
        self.assertEqual(len({m["customer"] for m in d["mails"]}), len(d["mails"]))  # one mail per customer
        # the fixed top-level keys
        for k in ("version", "check", "as_of", "since_days", "period", "language", "mail_language", "counts",
                  "new_attempts", "closed", "suggested_day", "day_statistics", "mails", "closing", "paths"):
            self.assertIn(k, d, k)
        self.assertEqual((d["check"], d["as_of"], d["since_days"]), ("month", "2026-10-31", 90))
        self.assertEqual(d["period"], {"from": "2025-11-05", "to": "2026-10-26"})
        self.assertEqual(set(d["paths"]), {"month_report"})
        self.assertEqual([t["id"] for t in d["closing"]["twikey"]], ["failure-decoder", "unmatched-payments"])
        self.assertEqual(d["closing"]["demo"]["id"], "demo")
        self.assertEqual(d["closing"]["text"], "Claude prepared this once, from your bank statements of November 2025 "
                                               "to October 2026. Nothing was sent and no bank file was written.")
        # the B2B mail lists both open collections and asks for the registration once
        b2b = d["mails"][3]
        self.assertEqual([(i["failure_date"], i["reason_code"]) for i in b2b["items"]],
                         [("2026-09-07", "MD01"), ("2026-10-05", "MD01")])
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
        self.assertNotRegex(text, r"(?<![A-Za-z0-9])(C0\d\d|M0\d\d)(?![A-Za-z0-9])")  # no code left
        self.assertNotIn("{", text)
        self.assertEqual(text.count("demo.html"), 1)
        self.assertEqual(text.count("Check each draft, then send it yourself."), 1)
        self.assertIn("## 1. Collections worth a new attempt", text)
        self.assertIn("## 2. Customer mail drafts", text)
        self.assertIn("Suggested day: day 26 of the month, next on November 26, 2026. Of the two collection days with "
                      "20 collections or more over two months or more in your statements, day 26 has the lowest "
                      "failure rate: 0.0% (84 collections over 12 months, none of them failed), against 10.1% for all "
                      "collections. At least 14 days from today, the usual SEPA pre-notification period. Check what "
                      "your mandate terms say.", text)
        self.assertIn("Left out because they are no longer owed: three (a later collection, or a payment by transfer "
                      "from that customer since).", text)
        self.assertIn("Made on November 3, 2026", text)  # today, injected: no test depends on the real date
        self.assertNotIn("€0.00", text)
        self.assertIn("Nothing was sent and no bank file was written.", text)
        self.assertNotIn("<?xml", text)
        code, out2, _ = self.box.cli("month")
        self.assertNotEqual(out2.strip(), path)  # a second work pack never overwrites the first

    def test_month_mails_in_every_language(self):
        for lang in ("en", "nl", "fr"):
            for mail_lang in ("en", "nl", "fr"):
                d = self.run_json("month", "--lang", lang, "--mail-lang", mail_lang)
                self.assertEqual((d["language"], d["mail_language"]), (lang, mail_lang))
                texts = [m["subject"] + m["body"] for m in d["mails"]]
                self.assertEqual(len(texts), 4)
                for t in texts:
                    self.assertNotIn("{", t)
                    self.assertNotIn("}", t)
                    self.assertNotIn("Twikey", t)
                    self.assertNotIn(";", t)
                    self.assertNotIn("—", t)
                company = {"en": "[your company name]", "nl": "[naam van je bedrijf]",
                           "fr": "[nom de votre entreprise]"}[mail_lang]
                self.assertTrue(all(company in t for t in texts))
                body = d["mails"][0]["body"]  # C003, a new attempt on the suggested day
                self.assertIn({"en": "November 26, 2026", "nl": "26 november 2026", "fr": "26 novembre 2026"}[mail_lang],
                              body)
                self.assertIn({"en": "€475.50", "nl": "€475,50", "fr": "€475,50"}[mail_lang], body)
                self.assertIn("C003", body)
                if mail_lang == "nl":
                    for t in texts:
                        self.assertNotRegex(t, r"(?i)\b(u|uw)\b")
                        self.assertNotRegex(t, r"(?i)herprobeerd|incasso")
                pack = read_text(d["paths"]["month_report"])  # the work pack, with names
                self.assertNotIn(";", pack)
                self.assertNotIn("—", pack)
                self.assertNotIn("{", pack)
                self.assertNotRegex(pack, r"\d{4}-\d{2}-\d{2}")  # dates written out
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
        for k, v in e.items():
            if k != "tools":
                self.assertEqual(d[k], v, k)
        d = self.run_json("golive", "--tool", "Exact")
        self.assertEqual(d["tool"]["partners_page"], "https://www.twikey.com/partners.html")
        self.assertNotIn("package", d["tool"])
        self.assertEqual(d["pricing_page"], "https://www.twikey.com/pricing.html")
        code, out, err = self.box.cli("golive", "--tool", "Exact")
        self.assertEqual(out.count("pricing.html"), 1)  # the pricing page is linked once
        self.assertIn("Listed on Twikey's partners page", out)
        self.assertIn("  Customers paying by direct debit: 14 (12 Core, two B2B), 14 mandates", out)

    def test_lang_before_or_after_the_command_and_local_number_format(self):
        for argv in (["--lang", "nl", "decode"], ["decode", "--lang", "nl"]):
            code, out, err = self.box.cli(*argv)
            self.assertEqual(code, 0, err)
            self.assertIn("Mislukte domiciliëringen: 17, €8.508,50 (5 november 2025 tot 5 oktober 2026, 12 maanden).",
                          out)
        code, out, err = self.box.cli("decode", "--lang", "fr")
        self.assertIn("20,2%", out)
        self.assertIn("€3.378,50", out)
        code, out, err = self.box.cli("decode")
        self.assertIn("20.2%", out)
        self.assertIn("€3,378.50", out)
        code, out, err = self.box.cli("steps", "--lang", "nl")
        self.assertIn("Totaal: 94 items, 298 stappen.", out)
        code, out, err = self.box.cli("--lang", "fr", "steps")
        self.assertIn("Total : 94 éléments, 298 étapes.", out)
        self.assertIn("(6,4 par mois sur 12 mois)", out)

    def test_dutch_and_french_output_is_fully_translated(self):
        from xray import reasons
        words = ("the|and|to|with|from|for|failed|collections?|payments?|invoices?|months?|none|days?|Rule|"
                 "Method|Customers?|Ledger|Workspace|Raw folder|Mandates|Facts|Accounting|Package|statements?")
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
            for argv in (["decode"], ["payments"], ["steps"], ["golive", "--tool", "Exact"], ["status"]):
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

    def test_french_twikey_labels_have_a_space_before_the_colon(self):
        code, out, err = self.box.cli("decode", "--lang", "fr")
        self.assertIn("Twikey : « Cela nous permet", out)
        self.assertIn(" Formule : « Gestion des échecs", out)
        self.assertNotRegex(out, r"Twikey:|Formule:")
        # the categories per reason code too
        self.assertIn("nouvelle présentation : 7", out)
        self.assertNotRegex(out, r"\w: \d")

    def test_status_never_mixes_periods(self):
        code, out, err = self.box.cli("status")
        self.assertEqual(code, 0, err)
        self.assertIn("Direct debit collections: 177 (November 5, 2025 to October 26, 2026)", out)
        self.assertIn("Failed collections: 17 (November 5, 2025 to October 5, 2026)", out)
        self.assertIn("Incoming payments: 291 (November 10, 2025 to October 19, 2026)", out)

    # ------------------------------------------------------------------ privacy

    def test_no_command_prints_a_name(self):
        runs = [["status"], ["intake"], ["decode"], ["decode", "--lang", "nl"], ["decode", "--lang", "fr"],
                ["payments"], ["steps"], ["steps", "--lang", "nl"], ["steps", "--lang", "fr"],
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
        with open(os.path.join(self.box.home, "findings.md"), "w", encoding="utf-8") as f:
            f.write("# Findings\n\nAs of October 31, 2026. Customers appear as codes. The report puts the names "
                    "back.\n\n## What we found\n\n- 17 failed collections, €8,508.50.\n- C001 is fine.\n"
                    "- Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-xray\n\n"
                    "## 1. Failed collections\n\nM004 was refunded twice.\n")
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
        self.assertNotIn("C001 is fine", text)
        # the named report never says customers appear as codes
        self.assertNotIn("appear as codes", text)
        self.assertNotIn("puts the names back", text)
        self.assertIn("Names and numbers were put back on your own computer. Claude saw amounts, dates, counts and "
                      "bank reason codes, with codes in place of names, account numbers, mandate references and "
                      "payment references.", text)
        self.assertIn("As of October 31, 2026.", text)
        # it opens with "What we found", right under the title
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(lines[1], "## What we found")
        self.assertTrue(lines[2].startswith("- 17 failed collections"))
        # one call to action, once, before the footer, with the plugin's UTM tags
        demo = ("Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin"
                "&utm_campaign=payment-xray")
        self.assertEqual(text.count("demo.html"), 1)
        self.assertLess(text.index(demo), text.index("---"))
        self.assertIn("- file 1: camt053-2025-11.xml", text)  # the report, on the user's computer, names the files
        self.assertTrue(text.rstrip().endswith("Twikey Payment X-ray 0.3.0. The numbers come from your own camt.053 "
                                               "bank statements."))
        code, out2, _ = self.box.cli("report")
        self.assertNotEqual(out2.strip(), path)  # a second report never overwrites the first

    def test_report_frame_in_dutch_and_french(self):
        with open(os.path.join(self.box.home, "findings.md"), "w", encoding="utf-8") as f:
            f.write("# Findings\n\n## 1. Mislukte domiciliëringen\n\nC007: B2B-mandaat M007.\n")
        for lang, files, label in (("nl", "Gelezen bestanden:", "- bestand 1: camt053-2025-11.xml"),
                                   ("fr", "Fichiers lus :", "- fichier 1 : camt053-2025-11.xml")):
            code, out, err = self.box.cli("report", "--lang", lang)
            self.assertEqual(code, 0, err)
            text = read_text(out.strip())
            self.assertIn(files, text)
            self.assertIn(label, text)
            self.assertIn("TRANSPORT DEMO NV: B2B-mandaat B2B-GF-0007.", text)
            self.assertNotRegex(text, r"\bfile \d")


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


NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"
# The elements a plain camt.053.001.02 statement uses here, and nothing else.
STANDARD = {"Document", "BkToCstmrStmt", "GrpHdr", "MsgId", "CreDtTm", "Stmt", "Id", "ElctrncSeqNb", "FrToDt",
            "FrDtTm", "ToDtTm", "Acct", "IBAN", "Ccy", "Ownr", "Nm", "Svcr", "FinInstnId", "BIC", "Bal", "Tp",
            "CdOrPrtry", "Cd", "Amt", "CdtDbtInd", "Dt", "Ntry", "Sts", "BookgDt", "ValDt", "AcctSvcrRef", "BkTxCd",
            "Domn", "Fmly", "SubFmlyCd", "NtryDtls", "Btch", "NbOfTxs", "TxDtls", "Refs", "EndToEndId", "MndtId",
            "AmtDtls", "TxAmt", "RltdPties", "Dbtr", "DbtrAcct", "Cdtr", "CdtrAcct", "RmtInf", "Ustrd", "Strd",
            "CdtrRefInf", "Issr", "Ref", "RtrInf", "Rsn"}


class DemoFilesTest(unittest.TestCase):
    def test_leak_detector_fires(self):
        for text in ("CAFÉ DEMO VOF paid", "Bakkerij Voorbeeld", "iban BE10999000100104", "VF-0421", "CORE-GF-0004",
                     "GF-20251105-0002", "Groothandel Fictief NV", "+++260/0000/11605+++", "RF18GF0115"):
            self.assertNotEqual(leaks(text), [], text)
        self.assertEqual(leaks("C001 paid €425.50 on 2026-10-05, M004, E0012"), [])

    def test_demo_files_are_rebuilt_from_the_spec(self):
        tmp = tempfile.mkdtemp(prefix="xray-demo-")
        try:
            names = make_demo.main(tmp)
            self.assertEqual(names, sorted(f for f in os.listdir(DEMO)))
            match, mismatch, errors = filecmp.cmpfiles(DEMO, tmp, names, shallow=False)
            self.assertEqual((mismatch, errors), ([], []))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_demo_file_is_a_plain_camt053_statement(self):
        names = sorted(os.listdir(DEMO))
        self.assertEqual(names, ["camt053-%s.xml" % m for m in
                                 ["2025-11", "2025-12"] + ["2026-%02d" % k for k in range(1, 11)]])
        for name in names:
            text = read_text(os.path.join(DEMO, name))
            self.assertTrue(text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="%s">' % NS), name)
            self.assertNotIn("<!--", text)
            self.assertNotRegex(text.lower(), r"twikey|addtl")
            root = ET.fromstring(text.encode())
            self.assertEqual(root.tag, "{%s}Document" % NS)
            self.assertEqual([c.tag for c in root], ["{%s}BkToCstmrStmt" % NS])
            tags = {el.tag for el in root.iter()}
            self.assertEqual({t.split("}")[0][1:] for t in tags}, {NS}, name)  # one namespace, no custom elements
            self.assertLessEqual({t.split("}")[1] for t in tags}, STANDARD, name)
        self.assertNotRegex(read_text(make_demo.__file__).lower(), r"twikey")

    def test_expected_file_was_written_for_this_spec(self):
        self.assertEqual(E["as_of"], make_demo.AS_OF.isoformat())


if __name__ == "__main__":
    unittest.main()
