"""camt.053 bank statements (the BkToCstmrStmt message).

Namespace versions are ignored and element names are matched by local name, so camt.053.001.02 up to .001.13
read the same way. Documents that declare a DOCTYPE or an ENTITY are refused before parsing. Anything that is not
a camt.053 statement comes back as "not a camt.053 bank statement", without a guess at what it is.

Entries are split per transaction:
  - a transaction with a return reason (RtrInf/Rsn) in the issued direct debit family (IDDT), or without a bank
    transaction code but with a mandate ID on a debit, is a failed collection (return or refund). Returns of
    anything else (a returned outgoing transfer) are skipped,
  - a debit in the IDDT family with a mandate ID but no return reason is a failed collection with "reason not in
    file",
  - a booked credit in the direct debit family (IDDT) or with a mandate ID is a collected direct debit,
  - any other booked credit is an incoming payment,
  - any other debit is skipped and counted.
Reason codes are kept only when they are on the allow-list (xray/reasons.py). Anything else is "proprietary
reason (not shown)" and its text is dropped.
"""
import datetime as dt
import xml.etree.ElementTree as ET

from . import reasons

FORMAT = "camt.053"
# Why a file is not read. Intake prints "file 3 <reason>, skipped." and never guesses what the file is.
NOT_CAMT053 = "not_camt053"
DOCTYPE = "doctype"


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
    """Return (statement message element, None) for a camt.053 document, else (None, the reason it is not read).

    The plugin is standard library only, so defusedxml is not available. Entities can only be declared in a DTD,
    so a document is refused when it contains a DOCTYPE or ENTITY anywhere. That byte scan only works for
    ASCII-compatible encodings, so UTF-16 and UTF-32 are not read either (camt.053 files are UTF-8).
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:1024]:
        return None, NOT_CAMT053
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        return None, DOCTYPE
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None, NOT_CAMT053
    if local(root.tag) != "Document":
        return None, NOT_CAMT053
    children = list(root)
    if children and local(children[0].tag) == "BkToCstmrStmt":
        return children[0], None
    return None, NOT_CAMT053


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


# Bank transaction code families (BkTxCd/Domn/Fmly): IDDT is "Issued Direct Debits", the direct debits the account
# owner collected as creditor. RDDT ("Received Direct Debits"), ICDT ("Issued Credit Transfers", with RRTN
# "Reversal Due To Payment Return" for a returned outgoing transfer) and RCDT are not collections.
# Source: the external code sets of the camt.053 standard, bank transaction codes.
COLLECTION_FAMILY = "IDDT"


def read_statement(msg):
    out = {"bank_lines": [], "collected": [], "failed": [], "skipped": {}, "own_accounts": set()}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1

    out["entries"] = 0
    for blk in kids(msg, "Stmt"):
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
            txs = []
            for nd in kids(ntry, "NtryDtls"):
                txs.extend(kids(nd, "TxDtls"))
            if not txs:
                txs = [None]
            for tx in txs:
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
                    pties = kid(tx, "RltdPties")
                    dbtr, dbtr_iban = party_name(kid(pties, "Dbtr")), iban_of(kid(pties, "DbtrAcct"))
                    reason = _reason(kid(tx, "RtrInf"))
                    settled = date_of(kid(tx, "RltdDts", "IntrBkSttlmDt"))
                    strd, free = _structured_ref(tx), _free_text(tx)
                else:
                    t_amt, t_ccy, cdi, fmly, sub = e_amt, e_ccy, e_cdi, e_fmly, e_sub
                    e2e = mndt = dbtr = dbtr_iban = reason = settled = None
                    strd, free = None, text(ntry, "AddtlNtryInf") or ""
                if t_amt is None or cdi not in ("CRDT", "DBIT"):
                    skip("transaction without amount or direction")
                    continue
                e2e = None if (e2e or "").upper() in ("", "NOTPROVIDED", "NOT PROVIDED") else e2e
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
                        "date": booked, "date_kind": "booked", "amount": abs(t_amt), "currency": t_ccy or "EUR",
                        "reason_code": None if reason in (None, PROPRIETARY) else reason,
                        "reason_proprietary": reason == PROPRIETARY, "reason_missing": unexplained,
                        "mandate_reference": mndt, "debtor_name": dbtr, "debtor_iban": dbtr_iban,
                        "end_to_end_id": e2e, "scheme": _scheme_from_subfamily(sub)})
                elif cdi == "CRDT" and (fmly == COLLECTION_FAMILY or mndt):
                    if tx is None:
                        skip("direct debit batch without details")
                        continue
                    out["collected"].append({
                        "date": settled or value or booked, "amount": abs(t_amt), "currency": t_ccy or "EUR",
                        "mandate_reference": mndt, "debtor_name": dbtr, "debtor_iban": dbtr_iban,
                        "end_to_end_id": e2e, "scheme": _scheme_from_subfamily(sub)})
                elif cdi == "CRDT":
                    out["bank_lines"].append({
                        "booking_date": booked, "value_date": value, "amount": abs(t_amt), "currency": t_ccy or "EUR",
                        "counterparty_name": dbtr, "counterparty_iban": dbtr_iban,
                        "structured_communication": strd, "communication": free})
                else:
                    skip("debit (payment out)")
    out["own_accounts"] = sorted(out["own_accounts"])
    return out


def read_xml(data, filename):
    msg, why = detect(data)
    if why:
        return {"status": "skipped", "file": filename, "reason": why}
    parsed = read_statement(msg)
    parsed.update({"status": "ok", "file": filename, "format": FORMAT})
    return parsed
