"""ISO 20022 XML: camt.053 (statement), camt.054 (notification) and pain.002 (status report).

Namespace versions are ignored, element names are matched by local name, so camt.053.001.02 up to
.001.13 and pain.002.001.03 up to .001.14 read the same way. Documents that declare a DOCTYPE or an
ENTITY are refused before parsing.

camt entries are split per transaction:
  - a transaction with a return reason (RtrInf/Rsn) in the issued direct debit family (IDDT), or
    without a bank transaction code but with a mandate ID on a debit, is a failed collection (return
    or refund). Returns of anything else (a returned outgoing transfer, ICDT/RRTN) are skipped,
  - a debit in the IDDT family with a mandate ID but no return reason is a failed collection with
    "reason not in file",
  - a booked credit in the direct debit family (IDDT) or with a mandate ID is a collected direct debit,
  - any other booked credit is a bank payment line,
  - any other debit is skipped and counted.
pain.002: only a report on a collection file (OrgnlMsgNmId pain.008) counts. Transactions with status
RJCT are rejected collections. A block without its own status takes the group status. A group or
payment block rejected as a whole without transaction details becomes one batch record: its control
sum, else the sum of its transactions, else amount unknown (never zero). Nothing is dropped without
a skip count.
Reason codes are kept only when they are on the allow-list (xray/reasons.py). Anything else is
"proprietary reason (not shown)" and its text is dropped.
"""
import datetime as dt
import re
import xml.etree.ElementTree as ET

from . import reasons

_FORMATS = {
    "BkToCstmrStmt": "camt.053",
    "BkToCstmrDbtCdtNtfctn": "camt.054",
    "CstmrPmtStsRpt": "pain.002",
}
_NOT_READ = {
    "CstmrDrctDbtInitn": "pain.008 is the collection file you send to the bank, not a result. Not read in this release.",
    "BkToCstmrAcctRpt": "camt.052 (intraday report) is not read in this release. Use the camt.053 statement.",
    "CstmrCdtTrfInitn": "pain.001 is a payment file you send to the bank. Not read.",
}


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def kids(el, name):
    return [c for c in list(el) if local(c.tag) == name] if el is not None else []


def kid(el, *path):
    cur = el
    for name in path:
        if cur is None:
            return None
        nxt = None
        for c in list(cur):
            if local(c.tag) == name:
                nxt = c
                break
        cur = nxt
    return cur


def text(el, *path):
    node = kid(el, *path) if path else el
    if node is None or node.text is None:
        return None
    t = node.text.strip()
    return t or None


def date_of(el):
    """<X><Dt>2026-08-04</Dt></X> or <X><DtTm>2026-08-04T10:00:00</DtTm></X>."""
    if el is None:
        return None
    s = text(el, "Dt") or text(el, "DtTm") or text(el)
    if not s:
        return None
    try:
        return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def amount_of(el):
    if el is None or el.text is None:
        return None, None
    try:
        return float(el.text.strip()), el.get("Ccy")
    except ValueError:
        return None, None


def party_name(el):
    """camt v02 <Dbtr><Nm>, camt v08+ <Dbtr><Pty><Nm>."""
    return text(el, "Nm") or text(el, "Pty", "Nm")


def iban_of(acct):
    return text(acct, "Id", "IBAN")


def detect(data):
    """Return (format, message element, error) for an XML document.

    The plugin is standard library only, so defusedxml is not available. Entities can only be
    declared in a DTD, so a document is refused when it contains a DOCTYPE or ENTITY anywhere.
    That byte scan only works for ASCII-compatible encodings, so UTF-16 and UTF-32 are refused
    too (ISO 20022 files are UTF-8).
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:1024]:
        return None, None, "only UTF-8 XML is read"
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        return None, None, "document declares a DOCTYPE or ENTITY, refused"
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        return None, None, "not well-formed XML (%s)" % str(e).split(":")[0]
    if local(root.tag) != "Document":
        return None, None, "not an ISO 20022 document"
    for c in list(root):
        name = local(c.tag)
        if name in _FORMATS:
            return _FORMATS[name], c, None
        if name in _NOT_READ:
            return None, None, _NOT_READ[name]
        return None, None, "ISO 20022 message %s is not read in this release" % name
    return None, None, "empty ISO 20022 document"


def _bktxcd(el):
    b = kid(el, "BkTxCd")
    if b is None:
        return None, None
    return text(b, "Domn", "Fmly", "Cd"), text(b, "Domn", "Fmly", "SubFmlyCd")


def _scheme_from_subfamily(sub):
    return {"ESDD": "CORE", "BBDD": "B2B"}.get(sub or "")


def _structured_ref(tx):
    for strd in kids(kid(tx, "RmtInf"), "Strd"):
        ref = text(strd, "CdtrRefInf", "Ref")
        if ref:
            return ref
    return None


def _free_text(tx):
    return " ".join(t for t in (text(u) for u in kids(kid(tx, "RmtInf"), "Ustrd")) if t)


PROPRIETARY = "PRTRY"  # marker: a reason that is not on the allow-list, never shown


def _reason(el):
    """The reason code, checked against the allow-list (xray/reasons.py). Anything else, in Cd or in Prtry
    (some banks put the payer's own words or a first name there), comes back as PROPRIETARY and its text
    is dropped."""
    for path in (("Rsn", "Cd"), ("Rsn", "Prtry")):
        v = text(el, *path)
        if v is None:
            continue
        return v.strip().upper() if reasons.allowed(v) else PROPRIETARY
    return None


# Bank transaction code families (camt BkTxCd/Domn/Fmly): IDDT is "Issued Direct Debits", the direct debits
# the account owner collected as creditor. RDDT ("Received Direct Debits"), ICDT ("Issued Credit Transfers",
# with RRTN "Reversal Due To Payment Return" for a returned outgoing transfer) and RCDT are not collections.
# Source: ISO 20022 bank transaction codes as listed in the ING "Annex Transaction Codification and Reason
# Reversal Codes" (v11) and the Nordea camt.054 bank transaction code list.
COLLECTION_FAMILY = "IDDT"


def read_camt(msg, fmt):
    out = {"bank_lines": [], "collected": [], "failed": [], "skipped": {}, "own_accounts": set()}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1

    blocks = kids(msg, "Stmt") + kids(msg, "Ntfctn") + kids(msg, "Rpt")
    out["entries"] = 0
    for blk in blocks:
        own = iban_of(kid(blk, "Acct"))
        if own:
            out["own_accounts"].add(own)
        for ntry in kids(blk, "Ntry"):
            out["entries"] += 1
            sts = text(ntry, "Sts", "Cd") or text(ntry, "Sts")
            if sts and sts.upper() != "BOOK":
                skip("entry not booked")
                continue
            e_amt, e_ccy = amount_of(kid(ntry, "Amt"))
            e_cdi = text(ntry, "CdtDbtInd")
            booked = date_of(kid(ntry, "BookgDt")) or date_of(kid(ntry, "ValDt"))
            value = date_of(kid(ntry, "ValDt"))
            e_fmly, e_sub = _bktxcd(ntry)
            e_ref = text(ntry, "AcctSvcrRef") or text(ntry, "NtryRef")
            txs = []
            for nd in kids(ntry, "NtryDtls"):
                txs.extend(kids(nd, "TxDtls"))
            if not txs:
                txs = [None]
            for i, tx in enumerate(txs):
                if tx is not None:
                    t_amt, t_ccy = amount_of(kid(tx, "AmtDtls", "TxAmt", "Amt"))
                    if t_amt is None:
                        t_amt, t_ccy = amount_of(kid(tx, "Amt"))
                    if t_amt is None and len(txs) == 1:
                        t_amt, t_ccy = e_amt, e_ccy
                    cdi = text(tx, "CdtDbtInd") or e_cdi
                    fmly, sub = _bktxcd(tx)
                    fmly, sub = fmly or e_fmly, sub or e_sub
                    e2e = text(tx, "Refs", "EndToEndId")
                    mndt = text(tx, "Refs", "MndtId")
                    tx_ref = text(tx, "Refs", "AcctSvcrRef") or text(tx, "Refs", "TxId")
                    pties = kid(tx, "RltdPties")
                    dbtr, dbtr_iban = party_name(kid(pties, "Dbtr")), iban_of(kid(pties, "DbtrAcct"))
                    cdtr, cdtr_iban = party_name(kid(pties, "Cdtr")), iban_of(kid(pties, "CdtrAcct"))
                    reason = _reason(kid(tx, "RtrInf"))
                    settled = date_of(kid(tx, "RltdDts", "IntrBkSttlmDt"))
                    strd, free = _structured_ref(tx), _free_text(tx)
                else:
                    t_amt, t_ccy, cdi, fmly, sub = e_amt, e_ccy, e_cdi, e_fmly, e_sub
                    e2e = mndt = tx_ref = dbtr = dbtr_iban = cdtr = cdtr_iban = reason = settled = None
                    strd, free = None, text(ntry, "AddtlNtryInf") or ""
                if t_amt is None or cdi not in ("CRDT", "DBIT"):
                    skip("transaction without amount or direction")
                    continue
                e2e = None if (e2e or "").upper() in ("", "NOTPROVIDED", "NOT PROVIDED") else e2e
                ref = "%s/%s/%s" % (e_ref or "", tx_ref or "", i)
                # A debit in the issued direct debit family on a mandate is a collection coming back, even
                # when the bank leaves out the return reason: it counts with "reason not in file".
                unexplained = (not reason and cdi == "DBIT" and fmly == COLLECTION_FAMILY and bool(mndt))
                if reason or unexplained:
                    # Only a return or refund of a direct debit the company collected counts: bank family IDDT,
                    # or, without a bank transaction code, a debit that carries a mandate reference.
                    ours = fmly == COLLECTION_FAMILY if fmly else (cdi == "DBIT" and bool(mndt))
                    if not ours:
                        skip("returned payment that is not a collection of yours (%s)" % (fmly or "no bank code"))
                        continue
                    out["failed"].append({
                        "source": fmt, "date": booked, "date_kind": "booked", "amount": abs(t_amt),
                        "currency": t_ccy or "EUR",
                        "reason_code": None if reason in (None, PROPRIETARY) else reason,
                        "reason_proprietary": reason == PROPRIETARY, "reason_missing": unexplained,
                        "mandate_reference": mndt, "debtor_name": dbtr, "debtor_iban": dbtr_iban,
                        "end_to_end_id": e2e, "scheme": _scheme_from_subfamily(sub), "batch_count": 1})
                elif cdi == "CRDT" and (fmly == "IDDT" or mndt):
                    if mndt is None and dbtr is None and len(txs) == 1 and tx is None:
                        skip("direct debit batch without details")
                        continue
                    out["collected"].append({
                        "source": fmt, "date": settled or value or booked, "amount": abs(t_amt),
                        "currency": t_ccy or "EUR", "mandate_reference": mndt, "debtor_name": dbtr,
                        "debtor_iban": dbtr_iban, "end_to_end_id": e2e, "scheme": _scheme_from_subfamily(sub)})
                elif cdi == "CRDT":
                    out["bank_lines"].append({
                        "source": fmt, "booking_date": booked, "value_date": value, "amount": abs(t_amt),
                        "currency": t_ccy or "EUR", "counterparty_name": dbtr, "counterparty_iban": dbtr_iban,
                        "structured_communication": strd, "communication": free, "ref": ref,
                        "own_account": own})
                else:
                    skip("debit (payment out)")
    out["own_accounts"] = sorted(out["own_accounts"])
    return out


def _scheme_from_instrument(code):
    c = (code or "").upper()
    if c in ("CORE", "COR1"):
        return "CORE"
    if c == "B2B":
        return "B2B"
    return None


def read_pain002(msg):
    out = {"bank_lines": [], "collected": [], "failed": [], "skipped": {}, "own_accounts": []}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1

    grp = kid(msg, "OrgnlGrpInfAndSts")
    # Only a status report on a collection file (pain.008) holds failed collections. A report on a payment
    # file (pain.001) is about money going out and is not counted.
    original = (text(grp, "OrgnlMsgNmId") or "").lower()
    out["original_message"] = original or None
    if not original.startswith("pain.008"):
        n = len(kids(msg, "OrgnlPmtInfAndSts")) or 1
        skip("status report on %s, not on a collection file (pain.008)" % (original or "an unnamed file"))
        out["skipped_report"] = out["entries"] = n
        return out
    grp_sts = (text(grp, "GrpSts") or "").upper()
    grp_reason = _reason(kid(grp, "StsRsnInf"))
    pmts = kids(msg, "OrgnlPmtInfAndSts")
    n_tx = 0

    def reason_fields(reason):
        return {"reason_code": None if reason in (None, PROPRIETARY) else reason,
                "reason_proprietary": reason == PROPRIETARY}

    def tx_amount(tx):
        ref = kid(tx, "OrgnlTxRef")
        amt, ccy = amount_of(kid(ref, "Amt", "InstdAmt"))
        if amt is None:
            amt, ccy = amount_of(kid(ref, "IntrBkSttlmAmt"))
        return amt, ccy

    def batch(el, reason, txs=()):
        """A block rejected as a whole: its control sum, else the sum of its transactions, else unknown."""
        amt, _ = amount_of(kid(el, "OrgnlCtrlSum"))
        if amt is None and txs:
            amounts = [tx_amount(t)[0] for t in txs]
            amt = None if any(a is None for a in amounts) else round(sum(abs(a) for a in amounts), 2)
        n = int(text(el, "OrgnlNbOfTxs") or 0) or len(txs) or 1
        rec = {"source": "pain.002", "date": None, "date_kind": None, "amount": amt, "currency": "EUR",
               "mandate_reference": None, "debtor_name": None, "debtor_iban": None, "end_to_end_id": None,
               "scheme": None, "batch_count": n}
        rec.update(reason_fields(reason))
        out["failed"].append(rec)

    out["entries"] = 0
    for pmt in pmts:
        # Without its own status a payment block takes the group status (GrpSts), and a transaction without
        # its own status takes the block's.
        pmt_sts = (text(pmt, "PmtInfSts") or grp_sts).upper()
        pmt_reason = _reason(kid(pmt, "StsRsnInf")) or grp_reason
        txs = kids(pmt, "TxInfAndSts")
        n_tx += len(txs)
        out["entries"] += len(txs) or 1
        if not txs:
            if pmt_sts == "RJCT":
                batch(pmt, pmt_reason)
            else:
                skip("payment block with status %s and no transactions" % (pmt_sts or "missing"))
            continue
        for tx in txs:
            sts = (text(tx, "TxSts") or pmt_sts).upper()
            if sts != "RJCT":
                skip("status %s" % (sts or "missing"))
                continue
            ref = kid(tx, "OrgnlTxRef")
            amt, ccy = tx_amount(tx)
            reason = _reason(kid(tx, "StsRsnInf")) or pmt_reason
            rec = {
                "source": "pain.002", "date": date_of(kid(ref, "ReqdColltnDt")) or date_of(kid(ref, "IntrBkSttlmDt")),
                "date_kind": "collection", "amount": abs(amt) if amt is not None else None,
                "currency": ccy or "EUR",
                "mandate_reference": text(ref, "MndtRltdInf", "MndtId"),
                "debtor_name": party_name(kid(ref, "Dbtr")), "debtor_iban": iban_of(kid(ref, "DbtrAcct")),
                "end_to_end_id": text(tx, "OrgnlEndToEndId"),
                "scheme": _scheme_from_instrument(text(ref, "PmtTpInf", "LclInstrm", "Cd")), "batch_count": 1}
            rec.update(reason_fields(reason))
            out["failed"].append(rec)
    if not n_tx and not pmts:
        out["entries"] += 1
        if grp_sts == "RJCT":
            batch(grp, grp_reason, kids(grp, "TxInfAndSts"))
        else:
            skip("report with status %s and no transactions" % (grp_sts or "missing"))
    return out


def read_xml(data, filename):
    fmt, msg, err = detect(data)
    if err:
        return {"status": "unsupported", "file": filename, "reason": err}
    parsed = read_pain002(msg) if fmt == "pain.002" else read_camt(msg, fmt)
    parsed.update({"status": "ok", "file": filename, "format": fmt,
                   "kind": "collections" if fmt in ("pain.002", "camt.054") else "bank"})
    return parsed


_CODA_HEADER = re.compile(rb"^0000\d")
_MT940 = re.compile(rb"(^|\n):20:.*\n(.*\n)*?:25:", re.M)


def sniff_unsupported(data, filename):
    """Name formats we recognize but do not read yet, so intake never guesses."""
    low = filename.lower()
    head = data[:4096]
    if low.endswith((".cod", ".coda")) or (_CODA_HEADER.match(head) and b"\n1" in head):
        return "CODA is not supported yet. Export the statement as camt.053 (XML) or CSV."
    if low.endswith((".sta", ".mt940", ".940")) or (head.startswith((b":20:", b"{1:")) or _MT940.search(head)):
        return "MT940 is not supported yet. Export the statement as camt.053 (XML) or CSV."
    if low.endswith((".xlsx", ".xls", ".ods", ".numbers")):
        return "Spreadsheet files are not read. Save the sheet as CSV."
    if low.endswith((".pdf",)):
        return "PDF statements are not read. Export camt.053 (XML) or CSV from your bank."
    return None
