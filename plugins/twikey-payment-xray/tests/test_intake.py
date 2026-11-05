import csv
import io
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

from tests.helpers import DEMO, Sandbox, load, read_text
from xray import checks, csvparse, reasons
from xray.common import KEY_FILE, norm_text

INVOICES = ("Factuurnummer;Klantnummer;Klant;Adres;E-mail;Factuurdatum;Vervaldatum;Bedrag;Status;Betaaldatum\n"
            "FAC-0001;K9;Firma Geheimnaam BV;Geheimstraat 9, 1000 Brussel;geheim@firma.example;01/08/2026;31/08/2026;"
            "121,00;Betaald;30/08/2026\n"
            "FAC-0002;K9;Firma Geheimnaam BV;Geheimstraat 9, 1000 Brussel;geheim@firma.example;01/09/2026;01/10/2026;"
            "50,00;Open;\n")
BANK = ("Boekingsdatum;Bedrag;Naam tegenpartij;Rekening tegenpartij;Vrije mededeling\n"
        "30/08/2026;121,00;FIRMA GEHEIMNAAM;BE68539007547034;betaling FAC-0001 met dank, Jan Geheim\n"
        "15/09/2026;20,00;FIRMA GEHEIMNAAM;BE68539007547034;voorschot fac-0002\n")
SECRETS = ["Geheimnaam", "GEHEIMNAAM", "Geheimstraat", "geheim@firma", "BE68539007547034", "Jan Geheim", "K9",
           "FAC-0001", "FAC-0002", "met dank", "voorschot"]


class IntakeTest(unittest.TestCase):
    def test_codes_key_and_clean_workspace(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw("bank.csv", BANK)
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
            bank = load(os.path.join(s.home, "bank.json"))
            self.assertEqual([b["customer"] for b in bank], ["C001", "C001"])
            # FAC-0002 is open, FAC-0001 is paid: only the second text names an open invoice (case does not matter)
            self.assertEqual([b["mentions_open_invoice"] for b in bank], [False, True])
            store = load(os.path.join(s.home, "store.json"))
            self.assertEqual(sorted(i["state"] for i in store["invoices"].values()), ["BOOKED", "PAID"])
            self.assertEqual(sorted(store["invoices"]), ["I0001", "I0002"])

    def test_codes_are_stable_across_runs(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.cli("init", "--raw", s.raw)
            s.cli("intake")
            first = load(os.path.join(s.raw, KEY_FILE))
            s.write_raw("bank.csv", BANK.replace("FIRMA GEHEIMNAAM", "NIEUWE KLANT").replace("BE68539007547034",
                                                                                            "BE71096123456769"))
            s.cli("intake")
            second = load(os.path.join(s.raw, KEY_FILE))
            self.assertEqual(second["parties"]["C001"], first["parties"]["C001"])
            self.assertEqual(second["invoices"], first["invoices"])
            self.assertIn("C002", second["parties"])

    def test_fail_closed_writes_nothing_and_shows_headers_only(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw("export.csv", "Doc;Rel;Dat;Bedr;Rest\nX1;Firma Geheimnaam;01/08/2026;10,00;10,00\n")
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 2)
            self.assertIn("file 1 (CSV, 2 lines)", out)  # by number, never by name
            self.assertNotIn("export.csv", out)
            self.assertNotIn("Geheimnaam", out)
            self.assertFalse(os.path.exists(os.path.join(s.home, "store.json")))
            self.assertFalse(os.path.exists(os.path.join(s.raw, KEY_FILE)))
            code, data = s.cli_json("intake", "--map", "1:Doc=invoice_number", "file 1:Rel=customer_name",
                                    "export.csv:Dat=invoice_date", "1:Bedr=amount", "1:#5=open_amount")
            self.assertEqual(code, 0, data)
            self.assertEqual(data["totals"]["invoices"], 3)
            cfg_text = read_text(os.path.join(s.home, "config.json"))
            self.assertNotIn("export.csv", cfg_text)  # the workspace holds a file id, not the name
            cfg = load(os.path.join(s.home, "config.json"))
            self.assertEqual(list(cfg["column_maps"].values())[0]["Doc"], "invoice_number")

    def test_headerless_file_mapped_by_position(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw("zonder-kop.csv", "X1;Firma Geheimnaam;01/08/2026;10,00;Open\n"
                                          "X2;Firma Geheimnaam;02/08/2026;20,00;Open\n")
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 2)
            self.assertIn("#2  header not shown  (text, 16 chars)", out)
            self.assertNotIn("Geheimnaam", out)
            code, data = s.cli_json("intake", "--map", "2:#1=invoice_number", "2:#2=customer_name",
                                    "2:#3=invoice_date", "2:#4=amount", "2:#5=status")
            self.assertEqual(code, 0, data)
            self.assertEqual(data["totals"]["invoices"], 4)

    def test_invoices_without_paid_information_stop_intake(self):
        rows = "".join("F%02d%02d;Klant %d BV;15/%02d/2026;1.000,00\n" % (m, c, c, m)
                       for m in range(1, 13) for c in range(1, 6))
        with Sandbox() as s:
            s.write_raw("facturen.csv", "Factuurnummer;Klant;Factuurdatum;Bedrag\n" + rows)
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual((code, data["status"]), (2, "blocked"))
            self.assertIn("status, paid_date or open_amount", data["blocked"][0]["reason"])
            self.assertFalse(os.path.exists(os.path.join(s.home, "store.json")))

    def test_rows_without_status_are_shown_as_status_unknown(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", "Factuurnummer;Klant;Factuurdatum;Bedrag;Status\n"
                                        "F1;A;15/01/2026;1,00;Betaald\nF2;B;15/01/2026;2,00;\nF3;C;15/01/2026;3,00;\n")
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 0, err)
            self.assertIn("status unknown: two invoices", out)

    def test_random_bytes_are_not_a_csv(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            with open(os.path.join(s.raw, "random.csv"), "wb") as f:
                f.write(bytes(range(256)) * 12)
            s.cli("init", "--raw", s.raw)
            code, out, err = s.cli("intake")
            self.assertEqual(code, 2, err)
            self.assertIn("could not be read as a CSV", out)
            self.assertNotIn("Unexpected error", out + err)

    def test_unreadable_file_never_shows_its_name(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw("Janssens Peter - wanbetaler facturen.csv", INVOICES)
            os.chmod(os.path.join(s.raw, "Janssens Peter - wanbetaler facturen.csv"), 0)
            try:
                s.cli("init", "--raw", s.raw)
                for argv in (["intake"], ["intake", "--json"]):
                    code, out, err = s.cli(*argv)
                    self.assertIn(code, (1, 2))
                    self.assertNotIn("Janssens", out + err)
                    self.assertNotIn("wanbetaler", out + err)
                if os.geteuid() != 0:
                    self.assertIn("could not be opened", out + err)
            finally:
                os.chmod(os.path.join(s.raw, "Janssens Peter - wanbetaler facturen.csv"), 0o644)

    def test_unexpected_errors_show_only_their_type(self):
        import twikey_xray
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.cli("init", "--raw", s.raw)
            original = twikey_xray.intake.run

            def boom(*a, **k):
                raise OSError("[Errno 13] Permission denied: '/x/Janssens Peter - wanbetaler.csv'")
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
            self.assertIn("macOS and Linux. Windows is not supported yet.", err)

    # ------------------------------------------------------------------ cell values and file names never shown

    def test_preamble_and_file_names_never_printed(self):
        with Sandbox() as s:
            s.write_raw("Rekening Jan Peeters.csv",
                        "Rekening;BE68539007547034;Naam;Jan Peeters\nDatum;Bedrag;Omschrijving;Tegenpartij\n"
                        "01/02/2026;10,00;jan@mail.example;Jan Peeters\n")
            s.cli("init", "--raw", s.raw)
            for argv in (["intake"], ["intake", "--json"]):
                code, out, err = s.cli(*argv)
                self.assertEqual(code, 2)
                for secret in ("Jan Peeters", "BE68539007547034", "jan@mail.example", "Peeters"):
                    self.assertNotIn(secret, out + err, argv)

    def test_key_file_and_reports_are_skipped_whatever_their_case(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw(KEY_FILE.upper(), "{}")
            s.write_raw("Twikey-Xray-Report-2026-10-01.md", "# report")
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual(code, 0, data)
            self.assertEqual([f["file"] for f in data["files"]], ["file 1"])

    # ------------------------------------------------------------------ one account, two formats

    def test_same_account_as_csv_and_camt053_counts_once(self):
        own = "BE68539007547034"
        csv_text = ("Rekening;Boekingsdatum;Bedrag;Naam tegenpartij;Rekening tegenpartij;Gestructureerde mededeling\n"
                    "%s;03/08/2026;121,00;KLANT A;BE71096123456769;+++090/9337/55493+++\n"
                    "%s;04/08/2026;500,00;EIGEN BEDRIJF;BE43068999999501;\n" % (own, own))
        camt = ('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">'
                "<BkToCstmrStmt><GrpHdr><MsgId>M</MsgId></GrpHdr><Stmt><Id>S</Id><Acct><Id><IBAN>%s</IBAN></Id></Acct>"
                '<Ntry><Amt Ccy="EUR">121.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts>'
                "<BookgDt><Dt>2026-08-03</Dt></BookgDt><BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd>"
                "<SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd><NtryDtls><TxDtls><RltdPties><Dbtr><Nm>Klant A NV</Nm>"
                "</Dbtr><DbtrAcct><Id><IBAN>BE71096123456769</IBAN></Id></DbtrAcct></RltdPties><RmtInf><Strd><CdtrRefInf>"
                "<Ref>090933755493</Ref></CdtrRefInf></Strd></RmtInf></TxDtls></NtryDtls></Ntry>"
                "</Stmt></BkToCstmrStmt></Document>\n" % own)
        with Sandbox() as s:
            s.write_raw("bank.csv", csv_text)
            s.write_raw("bank.xml", camt)
            s.write_raw("eigen.xml", camt.replace(own, "BE43068999999501").replace("121.00", "1.00")
                        .replace("2026-08-03", "2026-07-01"))
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual(code, 0, data)
            t = data["totals"]
            self.assertEqual(t["bank_credit_lines"], 2)  # the 121.00 once, plus the 1.00 on the second account
            self.assertEqual(t["duplicates_removed"], 1)
            self.assertEqual(t["own_transfers_skipped"], 1)  # 500.00 from the company's other account

    def test_bad_map_is_refused(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.cli("init", "--raw", s.raw)
            self.assertEqual(s.cli("intake", "--map", "facturen.csv:Klant=name_of_ceo")[0], 1)
            self.assertEqual(s.cli("intake", "--map", "facturen.csv-Klant")[0], 1)

    def test_unsupported_format_blocks_until_skipped(self):
        with Sandbox() as s:
            s.write_raw("facturen.csv", INVOICES)
            s.write_raw("rekening.cod", "0000001082620005        00000000  FIRMA\n")
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual((code, data["status"]), (2, "blocked"))
            self.assertIn("CODA", data["blocked"][0]["reason"])
            code, data = s.cli_json("intake", "--skip", "2")
            self.assertEqual((code, data["status"]), (0, "ok"))
            self.assertEqual(data["skipped_files"], ["file 2"])

    def test_same_return_in_two_files_counts_once(self):
        with Sandbox() as s:
            s.copy_demo(["camt053-2026-09.xml", "camt054-returns-2026.xml", "factuurhistoriek.csv"])
            s.cli("init", "--raw", s.raw)
            code, data = s.cli_json("intake")
            self.assertEqual(code, 0)
            self.assertEqual(data["totals"]["duplicates_removed"], 1)
            failed = [c for c in load(os.path.join(s.home, "collections.json")) if c["status"] == "failed"]
            self.assertEqual(len(failed), 4)  # the four returns of the camt.054, the September one once
            # the September return takes the date of the collection it returns
            self.assertIn(("2026-09-04", "collection"), [(f["date"], f["date_kind"]) for f in failed])

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
            s.write_raw("facturen.csv", INVOICES)
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
    """Every cell of the demo's CSV exports and every text and attribute of its XML exports."""
    values, bics = set(), set()
    for name in sorted(os.listdir(DEMO)):
        path = os.path.join(DEMO, name)
        if name.endswith(".csv"):
            text = read_text(path).lstrip("﻿")
            delim = ";" if text.count(";") > text.count(",") else ","
            for row in csv.reader(io.StringIO(text), delimiter=delim):
                values |= {c.strip() for c in row if c.strip()}
        elif name.endswith(".xml"):
            for el in ET.parse(path).iter():
                if el.text and el.text.strip():
                    values.add(el.text.strip())
                    if el.tag.split("}")[-1] in ("BIC", "BICFI", "BICOrBEI", "AnyBIC"):
                        bics.add(el.text.strip())
                values |= set(el.attrib.values())
    return values, bics


# What the workspace may hold besides our own codes: amounts (numbers), dates, counts, currency, Core/B2B,
# reason codes from the allow-list, statuses from a fixed list, file numbers and known column names.
OUR_CODE = re.compile(r"^(?:[CAM]\d{3,}|[IREBK]\d{4,}|file \d+|f[0-9a-f]{12})$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[\d:]+)?$")
LISTS = {"columns_kept", "columns_dropped", "read_not_stored"}


class WorkspaceHoldsNoRawValuesTest(unittest.TestCase):
    """After a demo intake, every file Claude can read holds codes and the allowed values only."""

    def test_no_raw_value_in_the_workspace(self):
        raw, bics = demo_raw_values()
        words = {v for group in csvparse._WORDS.values() for v in group if isinstance(v, str)}
        words |= {"PAID", "BOOKED", "ARCHIVED", "CANCELLED", "CREDITED", "CORE", "B2B", "EUR"}
        # Twikey's published reason-code texts, shipped in data/: month.json gives the meaning of a reason code from
        # them. The demo's French failed-collections export happens to use the same words for MS03.
        words |= {checks._clean(r["DESC"]) for lang in ("en", "nl", "fr") for r in checks.rcodes(lang).values()}
        with Sandbox() as s:
            self.assertEqual(s.cli("demo", "--raw", s.raw)[0], 0)
            texts = {}
            # month.json (this month's work, with mail drafts) in every language, plus the ledger
            for lang, mail_lang in (("en", "en"), ("nl", "nl"), ("fr", "fr"), ("en", "fr")):
                self.assertEqual(s.cli("month", "--lang", lang, "--mail-lang", mail_lang)[0], 0)
                texts["month.json (%s, mails %s)" % (lang, mail_lang)] = read_text(os.path.join(s.home, "month.json"))
            for name in sorted(os.listdir(s.home)):
                texts[name] = read_text(os.path.join(s.home, name))
            self.assertIn("store.json", texts)
            self.assertIn("bank.json", texts)
            self.assertIn("month.json", texts)

            def allowed(value, path):
                if OUR_CODE.match(value) or ISO_DATE.match(value) or value in words or reasons.allowed(value):
                    return True
                # a column name intake knows, in intake.json's column lists and assumptions
                if path.split(".")[-1].rstrip("[]") in LISTS or "assumptions" in path:
                    return norm_text(value) in csvparse.SAFE_HEADERS
                return False

            def walk(v, path, out):
                if isinstance(v, dict):
                    for k, x in v.items():
                        walk(k, path + ".<key>", out)
                        walk(x, path + "." + k, out)
                elif isinstance(v, list):
                    for x in v:
                        walk(x, path + "[]", out)
                elif isinstance(v, str) and v in raw and not allowed(v, path):
                    out.append((path, v))

            for name, text in texts.items():
                where = "workspace/" + name
                self.assertNotRegex(text, r"\+\+\+|\*\*\*|\b\d{3}/\d{4}/\d{5}\b|\b\d{12}\b", where)  # OGM
                self.assertNotRegex(text, r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,30}\b", where)  # IBAN
                self.assertNotRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+", where)  # e-mail
                self.assertNotRegex(text, r"\b[A-Z]{4}(?:BE|NL|LU|FR|DE)[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", where)  # BIC
                for bic in bics:
                    self.assertNotIn(bic, text, where)
                found = []
                walk(json.loads(text), name, found)
                self.assertEqual(found, [], where)
                # nor as a word inside a longer string: names, references, free text
                for v in raw:
                    if len(v) >= 5 and not re.match(r"^[\d\s./:,+\-T]+$", v) and not allowed(v, "") \
                            and norm_text(v) not in csvparse.SAFE_HEADERS:
                        self.assertNotRegex(text, r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(v),
                                            "%s holds %r" % (where, v))

    def test_references_are_checked_then_coded(self):
        with Sandbox() as s:
            s.cli("demo", "--raw", s.raw)
            store = load(os.path.join(s.home, "store.json"))["invoices"]
            bank = load(os.path.join(s.home, "bank.json"))
            key = load(os.path.join(s.raw, KEY_FILE))
            inv = store["I0001"]["xray"]
            self.assertRegex(inv["ogm"], r"^R\d{4}$")
            self.assertEqual(inv["ogm_status"], "valid")
            self.assertEqual(key["refs"][inv["ogm"]], "+++260/0000/00170+++")  # the number stays in the key
            # a bank line keeps the check's result and the invoices that carry the same communication
            line = next(b for b in bank if b["ogm"])
            self.assertEqual(line["ogm_status"], "valid")
            self.assertTrue(line["ogm_invoices"])
            for code in line["ogm_invoices"]:
                self.assertEqual(store[code]["xray"]["ogm"], line["ogm"])
            self.assertEqual(sum(b["ogm_status"] == "invalid" for b in bank), 1)
            self.assertTrue(all(b["ogm"] is None and b["ogm_invoices"] == [] for b in bank
                                if b["ogm_status"] != "valid"))
            # end-to-end references are coded too
            coll = load(os.path.join(s.home, "collections.json"))
            e2e = [c["e2e"] for c in coll if c.get("e2e")]
            self.assertTrue(e2e)
            self.assertTrue(all(re.match(r"^E\d{4}$", e) for e in e2e))
            self.assertTrue(all(key["e2e"][e].startswith("E2E-") for e in e2e))


if __name__ == "__main__":
    unittest.main()
