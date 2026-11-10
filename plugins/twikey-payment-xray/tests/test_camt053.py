import datetime as dt
import unittest

from tests import helpers  # noqa: F401
from xray import camt053

CAMT053_V02 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt>
<GrpHdr><MsgId>M</MsgId><CreDtTm>2026-09-01T06:00:00</CreDtTm></GrpHdr>
<Stmt><Id>S</Id><CreDtTm>2026-09-01T06:00:00</CreDtTm><Acct><Id><IBAN>BE00OWN</IBAN></Id></Acct>
<Ntry><Amt Ccy="EUR">121.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-08-03</Dt></BookgDt>
 <ValDt><Dt>2026-08-03</Dt></ValDt><BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>
 <NtryDtls><TxDtls><RltdPties><Dbtr><Nm>KLANT A NV</Nm></Dbtr><DbtrAcct><Id><IBAN>BE11</IBAN></Id></DbtrAcct></RltdPties>
 <RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry><Issr>BBA</Issr></Tp><Ref>090933755493</Ref></CdtrRefInf></Strd></RmtInf>
 </TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">300.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-08-04</Dt></BookgDt>
 <ValDt><Dt>2026-08-04</Dt></ValDt><BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>ESDD</SubFmlyCd></Fmly></Domn></BkTxCd>
 <NtryDtls><Btch><NbOfTxs>2</NbOfTxs></Btch>
  <TxDtls><Refs><EndToEndId>E1</EndToEndId><MndtId>MAN-1</MndtId></Refs><AmtDtls><TxAmt><Amt Ccy="EUR">100.00</Amt></TxAmt></AmtDtls>
   <RltdPties><Dbtr><Nm>KLANT B</Nm></Dbtr><DbtrAcct><Id><IBAN>BE22</IBAN></Id></DbtrAcct></RltdPties></TxDtls>
  <TxDtls><Refs><EndToEndId>E2</EndToEndId><MndtId>MAN-2</MndtId></Refs><AmtDtls><TxAmt><Amt Ccy="EUR">200.00</Amt></TxAmt></AmtDtls>
   <RltdPties><Dbtr><Nm>KLANT C</Nm></Dbtr><DbtrAcct><Id><IBAN>BE33</IBAN></Id></DbtrAcct></RltdPties></TxDtls>
 </NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">100.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-08-06</Dt></BookgDt>
 <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd></Fmly></Domn></BkTxCd>
 <NtryDtls><TxDtls><Refs><EndToEndId>E1</EndToEndId><MndtId>MAN-1</MndtId></Refs><AmtDtls><TxAmt><Amt Ccy="EUR">100.00</Amt></TxAmt></AmtDtls>
  <RltdPties><Dbtr><Nm>KLANT B</Nm></Dbtr></RltdPties><RtrInf><Rsn><Cd>AM04</Cd></Rsn></RtrInf></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">50.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-08-07</Dt></BookgDt>
 <NtryDtls><TxDtls><RltdPties><Cdtr><Nm>LEVERANCIER</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">10.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>PDNG</Sts><BookgDt><Dt>2026-08-08</Dt></BookgDt></Ntry>
</Stmt></BkToCstmrStmt></Document>
"""

CAMT053_V08 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"><BkToCstmrStmt>
<GrpHdr><MsgId>M</MsgId><CreDtTm>2026-09-01T06:00:00</CreDtTm></GrpHdr>
<Stmt><Id>S</Id><Acct><Id><IBAN>BE00OWN</IBAN></Id></Acct>
<Ntry><Amt Ccy="EUR">75.50</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts><BookgDt><DtTm>2026-08-10T09:00:00</DtTm></BookgDt>
 <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>RCDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>
 <NtryDtls><TxDtls><Amt Ccy="EUR">75.50</Amt><CdtDbtInd>CRDT</CdtDbtInd>
  <RltdPties><Dbtr><Pty><Nm>KLANT D</Nm></Pty></Dbtr><DbtrAcct><Id><IBAN>BE44</IBAN></Id></DbtrAcct></RltdPties>
  <RmtInf><Ustrd>invoice 2026-0042</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
</Stmt></BkToCstmrStmt></Document>
"""


def read(doc):
    return camt053.read_xml(doc.encode(), "s.xml")


class StatementTest(unittest.TestCase):
    def test_split_by_transaction(self):
        r = read(CAMT053_V02)
        self.assertEqual((r["status"], r["format"]), ("ok", "camt.053"))
        self.assertEqual(len(r["bank_lines"]), 1)
        line = r["bank_lines"][0]
        self.assertEqual((line["amount"], line["booking_date"]), (121.0, dt.date(2026, 8, 3)))
        self.assertEqual(line["structured_communication"], "090933755493")
        self.assertEqual(line["counterparty_name"], "KLANT A NV")
        self.assertEqual([c["amount"] for c in r["collected"]], [100.0, 200.0])
        self.assertEqual([c["mandate_reference"] for c in r["collected"]], ["MAN-1", "MAN-2"])
        self.assertEqual({c["scheme"] for c in r["collected"]}, {"CORE"})
        self.assertEqual(len(r["failed"]), 1)
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["amount"], f["end_to_end_id"], f["date_kind"]), ("AM04", 100.0, "E1", "booked"))
        self.assertEqual(r["skipped"], {"debit (payment out)": 1, "entry not booked": 1})
        self.assertEqual(r["own_accounts"], ["BE00OWN"])

    def test_version_08_shapes(self):
        r = read(CAMT053_V08)
        self.assertEqual(r["status"], "ok")
        line = r["bank_lines"][0]
        self.assertEqual((line["amount"], line["booking_date"], line["counterparty_name"]),
                         (75.5, dt.date(2026, 8, 10), "KLANT D"))
        self.assertEqual(line["communication"], "invoice 2026-0042")

    def test_entries_are_counted(self):
        self.assertEqual(read(CAMT053_V02)["entries"], 5)

    def test_a_batch_without_details_is_counted_not_guessed(self):
        start, end = CAMT053_V02.index("<Ntry>"), CAMT053_V02.index("</Stmt>")
        batch = ('<Ntry><Amt Ccy="EUR">300.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-08-04'
                 "</Dt></BookgDt><BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>IDDT</Cd><SubFmlyCd>ESDD</SubFmlyCd></Fmly>"
                 "</Domn></BkTxCd></Ntry>")
        r = read(CAMT053_V02[:start] + batch + CAMT053_V02[end:])
        self.assertEqual((r["collected"], r["bank_lines"]), ([], []))
        self.assertEqual(r["skipped"], {"direct debit batch without details": 1})


class ReasonsAndScopeTest(unittest.TestCase):
    def test_proprietary_reason_text_is_never_kept(self):
        doc = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>",
                                  "<Rsn><Prtry>TERUGBETALING GEVRAAGD DOOR JAN PEETERS, KERKSTRAAT 1 GENT</Prtry></Rsn>")
        f = read(doc)["failed"][0]
        self.assertEqual((f["reason_code"], f["reason_proprietary"]), (None, True))
        self.assertNotIn("PEETERS", repr(read(doc)).upper())
        ok = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><Prtry>ms02</Prtry></Rsn>")
        self.assertEqual(read(ok)["failed"][0]["reason_code"], "MS02")

    def test_four_letter_names_are_not_codes(self):
        # a first name in Prtry or Cd has four letters too: only the allow-list counts
        for name in ("EMMA", "ANNA", "LUC1"):
            for tag in ("Prtry", "Cd"):
                doc = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><%s>%s</%s></Rsn>" % (tag, name, tag))
                f = read(doc)["failed"][0]
                self.assertEqual((f["reason_code"], f["reason_proprietary"]), (None, True))
                self.assertNotIn(name, repr(f))

    def test_iddt_debit_without_return_reason_counts(self):
        doc = CAMT053_V02.replace("<RtrInf><Rsn><Cd>AM04</Cd></Rsn></RtrInf>", "")
        r = read(doc)
        self.assertEqual(len(r["failed"]), 1)
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["reason_missing"], f["mandate_reference"]), (None, True, "MAN-1"))

    def test_only_returned_collections_count(self):
        returned_transfer = CAMT053_V02.replace(
            "<Fmly><Cd>IDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>", "<Fmly><Cd>ICDT</Cd><SubFmlyCd>RRTN</SubFmlyCd>").replace(
            "<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><Cd>AC04</Cd></Rsn>")
        r = read(returned_transfer)
        self.assertEqual(r["failed"], [])
        self.assertIn("returned payment that is not a collection of yours (ICDT)", r["skipped"])
        received_dd = CAMT053_V02.replace("<Fmly><Cd>IDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>",
                                          "<Fmly><Cd>RDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>")
        self.assertEqual(read(received_dd)["failed"], [])
        self.assertEqual(len(read(CAMT053_V02)["failed"]), 1)  # IDDT/UPDD counts


class NotAStatementTest(unittest.TestCase):
    def test_doctype_refused(self):
        evil = ('<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><Document xmlns="urn:iso:std:iso:20022:tech:'
                'xsd:camt.053.001.02"><BkToCstmrStmt/></Document>')
        self.assertEqual(camt053.read_xml(evil.encode(), "e.xml"), {"status": "skipped", "file": "e.xml",
                                                                     "reason": camt053.DOCTYPE})

    def test_anything_else_is_not_a_camt053_statement(self):
        utf16 = CAMT053_V02.replace('encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16")
        other = '<Document xmlns="urn:example:other"><SomethingElse/></Document>'
        for data in (utf16, other.encode(), b"<a>", b"<Document/>", b"not xml at all"):
            r = camt053.read_xml(data, "x.xml")
            self.assertEqual((r["status"], r["reason"]), ("skipped", camt053.NOT_CAMT053), data[:40])
            self.assertEqual(set(r), {"status", "file", "reason"})  # no guess at what it is


if __name__ == "__main__":
    unittest.main()
