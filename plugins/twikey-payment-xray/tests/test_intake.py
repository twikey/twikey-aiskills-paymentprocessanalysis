import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

from tests.helpers import DEMO, Sandbox, load, read_text
from xray import checks, reasons
from xray.common import KEY_FILE

OWN = "BE68539007547034"
SECRET_IBAN = "BE71096123456769"


def statement(entries, own=OWN):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">'
            "<BkToCstmrStmt><GrpHdr><MsgId>M</MsgId><CreDtTm>2026-09-01T06:00:00</CreDtTm></GrpHdr><Stmt><Id>S</Id>"
            "<CreDtTm>2026-09-01T06:00:00</CreDtTm><Acct><Id><IBAN>%s</IBAN></Id></Acct>%s</Stmt></BkToCstmrStmt>"
            "</Document>\n" % (own, "".join(entries)))


def transfer(day, amount, name, iban, ref=None, text=None):
    rmt = ("<RmtInf><Strd><CdtrRefInf><Ref>%s</Ref></CdtrRefInf></Strd></RmtInf>" % ref if ref else
           "<RmtInf><Ustrd>%s</Ustrd></RmtInf>" % text if text else "")
    return ('<Ntry><Amt Ccy="EUR">%s</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>%s</Dt></BookgDt>'
            "<BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>"
            "<NtryDtls><TxDtls><RltdPties><Dbtr><Nm>%s</Nm></Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct>"
            "</RltdPties>%s</TxDtls></NtryDtls></Ntry>" % (amount, day, name, iban, rmt))


def collection(day, amount, name, iban, mandate, e2e, scheme="ESDD", debit=False, reason=None):
    ret = "<RtrInf><Rsn><Cd>%s</Cd></Rsn></RtrInf>" % reason if reason else ""
    return ('<Ntry><Amt Ccy="EUR">%s</Amt><CdtDbtInd>%s</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>%s</Dt></BookgDt>'
            "<BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>%s</SubFmlyCd></Fmly></Domn></BkTxCd>"
            "<NtryDtls><TxDtls><Refs><EndToEndId>%s</EndToEndId><MndtId>%s</MndtId></Refs>"
            "<RltdPties><Dbtr><Nm>%s</Nm></Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct></RltdPties>%s</TxDtls>"
            "</NtryDtls></Ntry>" % (amount, "DBIT" if debit else "CRDT", day, "UPDD" if debit else scheme, e2e,
                                    mandate, name, iban, ret))


STATEMENT = statement([
    collection("2026-08-04", "121.00", "Firma Geheimnaam BV", SECRET_IBAN, "MANDAAT-GEHEIM-9", "E2E-GEHEIM-1"),
    collection("2026-08-07", "121.00", "Firma Geheimnaam BV", SECRET_IBAN, "MANDAAT-GEHEIM-9", "E2E-GEHEIM-1",
               debit=True, reason="AM04"),
    transfer("2026-08-10", "50.00", "Jan Geheim", "BE43068999999501", text="voorschot met dank, Jan Geheim"),
    transfer("2026-08-11", "60.00", "Firma Geheimnaam", SECRET_IBAN, ref="090933755493"),
])
SECRETS = ["Geheimnaam", "GEHEIMNAAM", SECRET_IBAN, "BE43068999999501", "Jan Geheim", "MANDAAT-GEHEIM-9",
           "E2E-GEHEIM-1", "met dank", "voorschot", "090933755493", OWN]


class IntakeTest(unittest.TestCase):
    def test_codes_key_and_clean_workspace(self):
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            self.assertEqual(s.cli("init", "--raw", s.raw)[0], 0)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 0, err)
            for secret in SECRETS:
                self.assertNotIn(secret, out)
            self.assertTrue(os.path.exists(os.path.join(s.raw, KEY_FILE)))
            self.assertFalse(os.path.exists(os.path.join(s.home, KEY_FILE)))
            for name in os.listdir(s.home):
                text = read_text(os.path.join(s.home, name))
                for secret in SECRETS:
                    self.assertNotIn(secret, text, "%s leaked into %s" % (secret, name))
            coll = load(os.path.join(s.home, "collections.json"))
            self.assertEqual(sorted((c["status"], c["customer"], c["mandate"]) for c in coll),
                             [("collected", "C001", "M001"), ("failed", "C001", "M001")])
            failed = [c for c in coll if c["status"] == "failed"][0]
            # the return takes the date of the collection it returns, and Core from that collection
            self.assertEqual((failed["date"], failed["date_kind"], failed["scheme"]), ("2026-08-04", "collection",
                                                                                       "CORE"))
            bank = load(os.path.join(s.home, "bank.json"))
            # the transfer from the same account is the same customer, the other payer gets the next code
            self.assertEqual([(b["customer"], b["ogm_status"]) for b in bank], [("C002", "absent"), ("C001", "valid")])
            key = load(os.path.join(s.raw, KEY_FILE))
            self.assertEqual(key["parties"]["C001"]["name"], "Firma Geheimnaam BV")
            self.assertEqual(key["mandates"]["M001"], "MANDAAT-GEHEIM-9")
            self.assertEqual(key["refs"]["R0001"], "+++090/9337/55493+++")

    def test_codes_are_stable_across_runs(self):
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            s.cli("init", "--raw", s.raw)
            s.cli("intake")
            first = load(os.path.join(s.raw, KEY_FILE))
            s.write_raw("september.xml", statement([transfer("2026-09-10", "70.00", "Nieuwe Klant", "BE09999000001")]))
            s.cli("intake")
            second = load(os.path.join(s.raw, KEY_FILE))
            self.assertEqual(second["parties"]["C001"], first["parties"]["C001"])
            self.assertEqual(second["mandates"], first["mandates"])
            self.assertIn("C003", second["parties"])

    def test_a_file_that_is_not_a_camt053_statement_is_skipped(self):
        with Sandbox() as s:
            s.write_raw("1-statement.xml", STATEMENT)
            s.write_raw("2-other.xml", '<Document xmlns="urn:example:other"><SomethingElse/></Document>')
            s.write_raw("3-list.txt", "Naam;Bedrag\nFirma Geheimnaam;10,00\n")
            with open(os.path.join(s.raw, "4-random.bin"), "wb") as f:
                f.write(bytes(range(256)) * 12)
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 0, err)
            for n in (2, 3, 4):
                self.assertIn("  file %d is not a camt.053 bank statement, skipped." % n, out)
            self.assertIn("Intake: one statement read from the raw folder.", out)
            self.assertNotIn("Geheimnaam", out)
            self.assertNotIn("other.xml", out)
            code, data = s.cli_json("intake")
            self.assertEqual(data["skipped_files"], [{"file": "file %d" % n, "reason": "not_camt053"} for n in (2, 3, 4)])
            self.assertEqual(read_text(os.path.join(s.home, "intake.json")).count("not_camt053"), 0)
            self.assertEqual(load(os.path.join(s.home, "intake.json"))["skipped_files"], ["file 2", "file 3", "file 4"])
            code, out, err = s.cli("intake", "--lang", "nl")
            self.assertIn("  bestand 3 is geen camt.053-bankafschrift, overgeslagen.", out)
            code, out, err = s.cli("intake", "--lang", "fr")
            self.assertIn("  fichier 3 n'est pas un relevé bancaire camt.053, ignoré.", out)

    def test_no_camt053_statement_at_all_writes_nothing(self):
        with Sandbox() as s:
            s.write_raw("list.txt", "a;b\n1;2\n")
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 1)
            self.assertIn("No camt.053 bank statement in the raw folder.", err)
            self.assertFalse(os.path.exists(os.path.join(s.raw, KEY_FILE)))
            self.assertFalse(os.path.exists(os.path.join(s.home, "collections.json")))

    def test_unreadable_file_never_shows_its_name(self):
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            s.write_raw("Janssens Peter - wanbetaler.xml", STATEMENT)
            os.chmod(os.path.join(s.raw, "Janssens Peter - wanbetaler.xml"), 0)
            try:
                s.cli("init", "--raw", s.raw)
                for argv in (["intake"], ["intake", "--json"]):
                    code, out, err = s.cli(*argv)
                    self.assertEqual(code, 0)
                    self.assertNotIn("Janssens", out + err)
                    self.assertNotIn("wanbetaler", out + err)
                if os.geteuid() != 0:
                    self.assertIn("file 2 could not be opened", s.cli("intake")[1])
            finally:
                os.chmod(os.path.join(s.raw, "Janssens Peter - wanbetaler.xml"), 0o644)

    def test_unexpected_errors_show_only_their_type(self):
        import twikey_xray
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            s.cli("init", "--raw", s.raw)
            original = twikey_xray.intake.run

            def boom(*a, **k):
                raise OSError("[Errno 13] Permission denied: '/x/Janssens Peter - wanbetaler.xml'")
            twikey_xray.intake.run = boom
            try:
                code, out, err = s.cli("intake")
            finally:
                twikey_xray.intake.run = original
            self.assertEqual(code, 1)
            self.assertIn("Unexpected error (OSError)", err)
            self.assertNotIn("Janssens", out + err)

    def test_corrupt_config_names_the_file(self):
        with Sandbox() as s:
            os.makedirs(s.home)
            with open(os.path.join(s.home, "config.json"), "w") as f:
                f.write("{broken")
            code, out, err = s.cli("status")
            self.assertEqual(code, 1)
            self.assertIn(os.path.join(s.home, "config.json"), err)
            self.assertIn("not valid JSON", err)

    def test_start_folder_and_platform_checks(self):
        import twikey_xray
        with Sandbox() as s:
            os.chdir(s.root)  # a folder above the exports
            code, out, err = s.cli("init", "--raw", s.raw)
            self.assertEqual(code, 1)
            self.assertIn("Start Claude in a new, empty folder", err)
            os.chdir(s.work)
            original = twikey_xray.os.name
            twikey_xray.os.name = "nt"
            try:
                code, out, err = s.cli("init", "--raw", s.raw)
            finally:
                twikey_xray.os.name = original
            self.assertEqual(code, 1)
            self.assertIn("X-ray runs on macOS and Linux. Windows is not supported.", err)

    def test_file_names_are_never_printed(self):
        with Sandbox() as s:
            s.write_raw("Rekening Jan Peeters.xml", STATEMENT)
            s.write_raw("Lijst Jan Peeters.txt", "Jan Peeters;10,00\n")
            s.cli("init", "--raw", s.raw)
            for argv in (["intake"], ["intake", "--json"], ["status"], ["decode"]):
                code, out, err = s.cli(*argv)
                self.assertEqual(code, 0, err)
                self.assertNotIn("Peeters", out + err, argv)

    def test_key_file_and_reports_are_skipped_whatever_their_case(self):
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            s.write_raw(KEY_FILE.upper(), "{}")
            s.write_raw("Twikey-Xray-Report-2026-10-01.md", "# report")
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual(code, 0, data)
            self.assertEqual([f["file"] for f in data["files"]], ["file 1"])
            self.assertEqual(data["skipped_files"], [])

    def test_the_same_statement_twice_counts_once_and_own_transfers_are_left_out(self):
        second = statement([transfer("2026-08-12", "500.00", "Eigen Bedrijf", OWN),
                            transfer("2026-07-01", "1.00", "Klant Z", "BE09999000002")], own="BE43068999999501")
        with Sandbox() as s:
            s.write_raw("a.xml", STATEMENT)
            s.write_raw("b.xml", STATEMENT)  # the same export saved twice
            s.write_raw("c.xml", second)
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual(code, 0, data)
            t = data["totals"]
            self.assertEqual((t["collections_collected"], t["failed_collections"], t["bank_credit_lines"]), (1, 1, 2))
            self.assertEqual(t["duplicates_removed"], 3)  # the collection, its return and the transfer of b.xml
            # 500.00 from the company's other account, and the 50.00 in a.xml and b.xml: that payer's account is the
            # second statement's own account
            self.assertEqual(t["own_transfers_skipped"], 3)

    def test_init_refuses_raw_folder_inside_working_folder(self):
        with Sandbox() as s:
            inside = os.path.join(s.work, "exports")
            os.makedirs(inside)
            code, out, err = s.cli("init", "--raw", inside)
            self.assertEqual(code, 1)
            self.assertIn("Start Claude in a new, empty folder", err)
            code, out, err = s.cli("init", "--raw", s.root)
            self.assertEqual(code, 1)
            self.assertIn("contains the folder Claude works in", err)

    def test_report_needs_a_key_and_findings(self):
        with Sandbox() as s:
            s.write_raw("augustus.xml", STATEMENT)
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("report")
            self.assertEqual(code, 1)
            self.assertIn("intake", err)
            s.cli("intake")
            code, out, err = s.cli("report")
            self.assertEqual(code, 1)
            self.assertIn("findings.md", err)

    def test_init_registers_the_raw_folder_for_the_guard(self):
        with Sandbox() as s:
            s.cli("init", "--raw", s.raw)
            reg = load(os.path.join(s.state, "raw-folders.json"))
            self.assertEqual(reg["raw_dirs"], [s.raw])
            # the X-ray folder, where the guard lets the shell run only X-ray's own commands
            self.assertEqual(reg["work_dirs"], [s.work])


def demo_raw_values():
    """Every text and attribute of the demo statements."""
    values, bics = set(), set()
    for name in sorted(os.listdir(DEMO)):
        for el in ET.parse(os.path.join(DEMO, name)).iter():
            if el.text and el.text.strip():
                values.add(el.text.strip())
                if el.tag.split("}")[-1] in ("BIC", "BICFI", "AnyBIC"):
                    bics.add(el.text.strip())
            values |= set(el.attrib.values())
    return values, bics


# What the workspace may hold besides our own codes: amounts (numbers), dates, counts, currency, Core/B2B, reason
# codes from the allow-list, structured communication statuses and file numbers.
OUR_CODE = re.compile(r"^(?:[CAM]\d{3,}|[REBK]\d{4,}|file \d+)$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[\d:]+)?$")
WORDS = {"CORE", "B2B", "EUR", "BOOK", "CRDT", "DBIT", "valid", "invalid", "other", "absent", "camt.053"}


class WorkspaceHoldsNoRawValuesTest(unittest.TestCase):
    """After a demo intake, every file Claude can read holds codes and the allowed values only."""

    def test_no_raw_value_in_the_workspace(self):
        raw, bics = demo_raw_values()
        # Twikey's published reason-code texts, shipped in data/: month.json gives the meaning of a reason code from
        # them.
        words = WORDS | {checks._clean(r["DESC"]) for lang in ("en", "nl", "fr") for r in checks.rcodes(lang).values()}
        with Sandbox() as s:
            self.assertEqual(s.cli("demo", "--raw", s.raw)[0], 0)
            texts = {}
            # month.json (this month's work, with mail drafts) in every language, plus the ledger
            for lang, mail_lang in (("en", "en"), ("nl", "nl"), ("fr", "fr"), ("en", "fr")):
                self.assertEqual(s.cli("month", "--lang", lang, "--mail-lang", mail_lang)[0], 0)
                texts["month.json (%s, mails %s)" % (lang, mail_lang)] = read_text(os.path.join(s.home, "month.json"))
            for name in sorted(os.listdir(s.home)):
                texts[name] = read_text(os.path.join(s.home, name))
            for want in ("collections.json", "bank.json", "intake.json", "month.json"):
                self.assertIn(want, texts)

            def allowed(value):
                return bool(OUR_CODE.match(value) or ISO_DATE.match(value) or value in words
                            or reasons.allowed(value))

            def walk(v, path, out):
                if isinstance(v, dict):
                    for k, x in v.items():
                        walk(k, path + ".<key>", out)
                        walk(x, path + "." + k, out)
                elif isinstance(v, list):
                    for x in v:
                        walk(x, path + "[]", out)
                elif isinstance(v, str) and v in raw and not allowed(v):
                    out.append((path, v))

            for name, text in texts.items():
                where = "workspace/" + name
                self.assertNotRegex(text, r"\+\+\+|\*\*\*|\b\d{3}/\d{4}/\d{5}\b|\b\d{12}\b", where)  # OGM
                self.assertNotRegex(text, r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,30}\b", where)  # IBAN or RF reference
                self.assertNotRegex(text, r"\b[A-Z]{4}(?:BE|NL|LU|FR|DE)[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", where)  # BIC
                for bic in bics:
                    self.assertNotIn(bic, text, where)
                found = []
                walk(json.loads(text), name, found)
                self.assertEqual(found, [], where)
                # nor as a word inside a longer string: names, references, free text
                for v in raw:
                    if len(v) >= 5 and not re.match(r"^[\d\s./:,+\-T]+$", v) and not allowed(v):
                        self.assertNotRegex(text, r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(v),
                                            "%s holds %r" % (where, v))

    def test_references_are_checked_then_coded(self):
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw)
            bank = load(os.path.join(s.home, "bank.json"))
            key = load(os.path.join(s.raw, KEY_FILE))
            line = next(b for b in bank if b["ogm"])
            self.assertRegex(line["ogm"], r"^R\d{4}$")
            self.assertEqual(line["ogm_status"], "valid")
            self.assertRegex(key["refs"][line["ogm"]], r"^\+\+\+\d{3}/\d{4}/\d{5}\+\+\+$")  # the number stays in the key
            self.assertEqual(sum(b["ogm_status"] == "invalid" for b in bank), 2)
            self.assertTrue(all(b["ogm"] is None for b in bank if b["ogm_status"] != "valid"))
            # end-to-end references and mandate references are coded too
            coll = load(os.path.join(s.home, "collections.json"))
            e2e = [c["e2e"] for c in coll if c.get("e2e")]
            self.assertTrue(e2e)
            self.assertTrue(all(re.match(r"^E\d{4}$", e) for e in e2e))
            self.assertTrue(all(re.match(r"^M\d{3}$", c["mandate"]) for c in coll))
            self.assertEqual(key["mandates"]["M001"], "CORE-GF-0001")


if __name__ == "__main__":
    unittest.main()
