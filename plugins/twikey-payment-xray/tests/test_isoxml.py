import datetime as dt
import unittest

from tests import helpers  # noqa: F401
from xray import isoxml

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
  <RmtInf><Ustrd>factuur 2026-0042</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
</Stmt></BkToCstmrStmt></Document>
"""

PAIN002 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.03"><CstmrPmtStsRpt>
<GrpHdr><MsgId>R</MsgId><CreDtTm>2026-08-03T08:00:00</CreDtTm></GrpHdr>
<OrgnlGrpInfAndSts><OrgnlMsgId>O</OrgnlMsgId><OrgnlMsgNmId>pain.008.001.02</OrgnlMsgNmId><GrpSts>PART</GrpSts></OrgnlGrpInfAndSts>
<OrgnlPmtInfAndSts><OrgnlPmtInfId>P1</OrgnlPmtInfId><PmtInfSts>PART</PmtInfSts>
 <TxInfAndSts><OrgnlEndToEndId>E9</OrgnlEndToEndId><TxSts>RJCT</TxSts><StsRsnInf><Rsn><Cd>MD01</Cd></Rsn></StsRsnInf>
  <OrgnlTxRef><Amt><InstdAmt Ccy="EUR">40.00</InstdAmt></Amt><ReqdColltnDt>2026-08-04</ReqdColltnDt>
   <PmtTpInf><LclInstrm><Cd>B2B</Cd></LclInstrm></PmtTpInf><MndtRltdInf><MndtId>MAN-9</MndtId></MndtRltdInf>
   <Dbtr><Nm>KLANT E</Nm></Dbtr><DbtrAcct><Id><IBAN>BE55</IBAN></Id></DbtrAcct></OrgnlTxRef></TxInfAndSts>
 <TxInfAndSts><OrgnlEndToEndId>E10</OrgnlEndToEndId><TxSts>ACCP</TxSts></TxInfAndSts>
</OrgnlPmtInfAndSts></CstmrPmtStsRpt></Document>
"""

PAIN002_GROUP_REJECT = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.03"><CstmrPmtStsRpt>
<GrpHdr><MsgId>R</MsgId><CreDtTm>2026-08-03T08:00:00</CreDtTm></GrpHdr>
<OrgnlGrpInfAndSts><OrgnlMsgId>O</OrgnlMsgId><OrgnlMsgNmId>pain.008.001.02</OrgnlMsgNmId><OrgnlNbOfTxs>12</OrgnlNbOfTxs>
 <OrgnlCtrlSum>1500.00</OrgnlCtrlSum><GrpSts>RJCT</GrpSts><StsRsnInf><Rsn><Cd>FF01</Cd></Rsn></StsRsnInf></OrgnlGrpInfAndSts>
</CstmrPmtStsRpt></Document>
"""


class CamtTest(unittest.TestCase):
    def test_camt053_split_by_transaction(self):
        r = isoxml.read_xml(CAMT053_V02.encode(), "s.xml")
        self.assertEqual((r["status"], r["format"], r["kind"]), ("ok", "camt.053", "bank"))
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

    def test_camt053_version_08_shapes(self):
        r = isoxml.read_xml(CAMT053_V08.encode(), "s8.xml")
        self.assertEqual(r["status"], "ok")
        line = r["bank_lines"][0]
        self.assertEqual((line["amount"], line["booking_date"], line["counterparty_name"]),
                         (75.5, dt.date(2026, 8, 10), "KLANT D"))
        self.assertEqual(line["communication"], "factuur 2026-0042")

    def test_camt054_is_collections(self):
        r = isoxml.read_xml(CAMT053_V02.replace("camt.053.001.02", "camt.054.001.02")
                            .replace("BkToCstmrStmt", "BkToCstmrDbtCdtNtfctn").replace("<Stmt>", "<Ntfctn>")
                            .replace("</Stmt>", "</Ntfctn>").encode(), "n.xml")
        self.assertEqual((r["format"], r["kind"]), ("camt.054", "collections"))
        self.assertEqual(len(r["failed"]), 1)


class Pain002Test(unittest.TestCase):
    def test_transaction_rejects(self):
        r = isoxml.read_xml(PAIN002.encode(), "p.xml")
        self.assertEqual((r["status"], r["format"], r["kind"]), ("ok", "pain.002", "collections"))
        self.assertEqual(len(r["failed"]), 1)
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["amount"], f["scheme"], f["date"], f["mandate_reference"]),
                         ("MD01", 40.0, "B2B", dt.date(2026, 8, 4), "MAN-9"))
        self.assertEqual(r["skipped"], {"status ACCP": 1})

    def test_whole_file_rejected(self):
        r = isoxml.read_xml(PAIN002_GROUP_REJECT.encode(), "g.xml")
        self.assertEqual(len(r["failed"]), 1)
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["amount"], f["batch_count"]), ("FF01", 1500.0, 12))


class ReasonsAndScopeTest(unittest.TestCase):
    def test_proprietary_reason_text_is_never_kept(self):
        doc = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>",
                                  "<Rsn><Prtry>TERUGBETALING GEVRAAGD DOOR JAN PEETERS, KERKSTRAAT 1 GENT</Prtry></Rsn>")
        r = isoxml.read_xml(doc.encode(), "s.xml")
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["reason_proprietary"]), (None, True))
        self.assertNotIn("PEETERS", repr(r).upper())
        ok = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><Prtry>ms02</Prtry></Rsn>")
        self.assertEqual(isoxml.read_xml(ok.encode(), "s.xml")["failed"][0]["reason_code"], "MS02")
        p = PAIN002.replace("<Rsn><Cd>MD01</Cd></Rsn>", "<Rsn><Prtry>Klant Jan Peeters weigert</Prtry></Rsn>")
        f = isoxml.read_xml(p.encode(), "p.xml")["failed"][0]
        self.assertEqual((f["reason_code"], f["reason_proprietary"]), (None, True))

    def test_four_letter_names_are_not_codes(self):
        # a first name in Prtry or Cd has four letters too: only the allow-list counts
        for name in ("EMMA", "ANNA", "LUC1"):
            for tag in ("Prtry", "Cd"):
                p = PAIN002.replace("<Rsn><Cd>MD01</Cd></Rsn>", "<Rsn><%s>%s</%s></Rsn>" % (tag, name, tag))
                r = isoxml.read_xml(p.encode(), "p.xml")
                self.assertEqual((r["failed"][0]["reason_code"], r["failed"][0]["reason_proprietary"]), (None, True))
                self.assertNotIn(name, repr(r["failed"][0]))
        c = CAMT053_V02.replace("<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><Prtry>ANNA</Prtry></Rsn>")
        self.assertNotIn("ANNA", repr(isoxml.read_xml(c.encode(), "s.xml")["failed"]))

    def test_iddt_debit_without_return_reason_counts(self):
        doc = CAMT053_V02.replace("<RtrInf><Rsn><Cd>AM04</Cd></Rsn></RtrInf>", "")
        r = isoxml.read_xml(doc.encode(), "s.xml")
        self.assertEqual(len(r["failed"]), 1)
        f = r["failed"][0]
        self.assertEqual((f["reason_code"], f["reason_missing"], f["mandate_reference"]), (None, True, "MAN-1"))
        self.assertNotIn("debit (payment out)", {k: v for k, v in r["skipped"].items() if v > 1})

    def test_group_status_applies_to_blocks_without_their_own(self):
        p = PAIN002.replace("<GrpSts>PART</GrpSts>", "<GrpSts>RJCT</GrpSts>").replace(
            "<PmtInfSts>PART</PmtInfSts>", "").replace("<TxSts>RJCT</TxSts>", "")
        r = isoxml.read_xml(p.encode(), "p.xml")
        # the first transaction has no status of its own and takes RJCT from the group, the second keeps its ACCP:
        # one failed, one counted as skipped, nothing dropped silently
        self.assertEqual((len(r["failed"]), r["skipped"]), (1, {"status ACCP": 1}))
        self.assertEqual(r["entries"], 2)

    def test_entries_are_counted(self):
        self.assertEqual(isoxml.read_xml(CAMT053_V02.encode(), "s.xml")["entries"], 5)
        self.assertEqual(isoxml.read_xml(PAIN002.encode(), "p.xml")["entries"], 2)

    def test_pain002_on_a_payment_file_is_not_counted(self):
        p = PAIN002.replace("pain.008.001.02", "pain.001.001.03")
        r = isoxml.read_xml(p.encode(), "p.xml")
        self.assertEqual(r["failed"], [])
        self.assertEqual(r["original_message"], "pain.001.001.03")
        g = isoxml.read_xml(PAIN002_GROUP_REJECT.replace("pain.008.001.02", "pain.001.001.09").encode(), "g.xml")
        self.assertEqual(g["failed"], [])

    def test_only_returned_collections_count(self):
        returned_transfer = CAMT053_V02.replace(
            "<Fmly><Cd>IDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>", "<Fmly><Cd>ICDT</Cd><SubFmlyCd>RRTN</SubFmlyCd>").replace(
            "<Rsn><Cd>AM04</Cd></Rsn>", "<Rsn><Cd>AC04</Cd></Rsn>")
        r = isoxml.read_xml(returned_transfer.encode(), "s.xml")
        self.assertEqual(r["failed"], [])
        self.assertIn("returned payment that is not a collection of yours (ICDT)", r["skipped"])
        received_dd = CAMT053_V02.replace("<Fmly><Cd>IDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>",
                                          "<Fmly><Cd>RDDT</Cd><SubFmlyCd>UPDD</SubFmlyCd>")
        self.assertEqual(isoxml.read_xml(received_dd.encode(), "s.xml")["failed"], [])
        self.assertEqual(len(isoxml.read_xml(CAMT053_V02.encode(), "s.xml")["failed"]), 1)  # IDDT/UPDD counts

    def test_batch_reject_amount(self):
        no_sum = PAIN002_GROUP_REJECT.replace("<OrgnlCtrlSum>1500.00</OrgnlCtrlSum>", "")
        f = isoxml.read_xml(no_sum.encode(), "g.xml")["failed"][0]
        self.assertIsNone(f["amount"])  # unknown, never 0.00
        self.assertEqual(f["batch_count"], 12)
        pmt = PAIN002.replace("<PmtInfSts>PART</PmtInfSts>", "<PmtInfSts>RJCT</PmtInfSts>")
        # a payment block rejected with transactions: each transaction counts with its own amount
        r = isoxml.read_xml(pmt.encode(), "p.xml")
        self.assertEqual([x["amount"] for x in r["failed"]], [40.0])


class RefusalTest(unittest.TestCase):
    def test_doctype_refused(self):
        evil = ('<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><Document xmlns="urn:iso:std:iso:20022:tech:'
                'xsd:camt.053.001.02"><BkToCstmrStmt/></Document>')
        r = isoxml.read_xml(evil.encode(), "e.xml")
        self.assertEqual(r["status"], "unsupported")
        self.assertIn("DOCTYPE", r["reason"])

    def test_utf16_refused(self):
        r = isoxml.read_xml(PAIN002.replace('encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16"), "u.xml")
        self.assertEqual(r["status"], "unsupported")

    def test_pain008_and_unknown_messages_not_read(self):
        doc = '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"><CstmrDrctDbtInitn/></Document>'
        self.assertIn("pain.008", isoxml.read_xml(doc.encode(), "c.xml")["reason"])
        self.assertEqual(isoxml.read_xml(b"<a>", "bad.xml")["status"], "unsupported")

    def test_coda_and_mt940_named_not_guessed(self):
        coda = b"0000001082620005        00000000  GROOTHANDEL FICTIEF NV    KREDBEBB   00000000000 00000                                       2\n1" + b" " * 127 + b"\n"
        self.assertIn("CODA", isoxml.sniff_unsupported(coda, "stmt.txt"))
        self.assertIn("CODA", isoxml.sniff_unsupported(b"anything", "x.cod"))
        mt940 = b":20:STARTUMS\n:25:BE00/123\n:28C:1\n:60F:C260801EUR100,00\n"
        self.assertIn("MT940", isoxml.sniff_unsupported(mt940, "stmt.txt"))
        self.assertIn("CSV", isoxml.sniff_unsupported(b"PK", "x.xlsx"))
        self.assertIsNone(isoxml.sniff_unsupported(b"Datum;Bedrag\n", "x.csv"))


if __name__ == "__main__":
    unittest.main()
