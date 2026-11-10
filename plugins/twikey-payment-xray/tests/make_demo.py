#!/usr/bin/env python3
"""
make_demo.py - builds the fictional demo statements in ../demo from one written-down spec.

The company is "Groothandel Fictief NV", a fictional Belgian wholesaler with one account at a fictional bank. The
demo is twelve monthly camt.053.001.02 bank statements, November 2025 to October 2026, and nothing else. Every
name and IBAN is made up. IBANs use bank codes 998 and 999 and valid check digits.

On the statements: 14 customers pay by direct debit (12 on Core mandates, two on B2B mandates), collected on two
days of the month. 25 customers pay by transfer, most with a Belgian structured communication. One landlord refunds
a deposit. The company pays a supplier and its bank charges.

The expected results in tests/expected_demo.json were written from the spec in this file (the FAILURES and the
transfer rules below). test_demo.py also rebuilds the demo into a temporary folder and checks that the files in
../demo are identical, so the spec and the shipped files cannot drift apart.

Usage: python3 make_demo.py [output folder]
"""
import datetime as dt
import os
import sys
from xml.sax.saxutils import escape

AS_OF = dt.date(2026, 10, 31)
COMPANY = "Groothandel Fictief NV"
BANK_BIC = "FICTBEBB"
NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"

NAMES = [
    None,
    # direct debit, Core, collected on the 5th
    "Bakkerij Voorbeeld BV", "Brasserie Fictief NV", "Slagerij Proefmans BV", "Café Demo VOF",
    "Boulangerie Exemple SRL",
    # direct debit, B2B, collected on the 5th
    "Bouwbedrijf Voorbeeld NV", "Transport Demo NV",
    # direct debit, Core, collected on the 26th
    "Garage Testmans BV", "Bloemen Fictief BV", "Restaurant Le Fictif SRL", "Apotheek Voorbeeld BV",
    "Drukkerij Demo NV", "Kapsalon Proef BV", "Hotel Fictief NV",
    # transfer customers
    "Logistique Fictive SA", "Frituur Testmans", "Superette Exemple SRL", "Kantoor Proefmans BV",
    "Fietsen Fictief BV", "Schoenen Demo BV", "Bistro Imaginaire SRL", "Wijnhandel Voorbeeld BV",
    "Traiteur Fictif SRL", "Drankhandel Testmans NV", "Elektro Demo BV", "Carrosserie Testmans BV",
    "Patisserie Exemple SRL", "Sportclub Fictief VZW", "Tuincentrum Voorbeeld NV", "Optiek Demo BV",
    "Boekhandel Proef BV", "Feestzaal Fictief BV", "IJssalon Voorbeeld BV", "Chocolatier Fictif SRL",
    "Viswinkel Demo BV", "Koffiebar Proefmans BV", "Meubelen Fictief NV", "Auberge Imaginaire SRL",
    "Speelgoed Voorbeeld BV",
]
LANDLORD = "Immo Fictief NV"
SUPPLIER = "Leverancier Fictief NV"

CORE_A = (1, 2, 3, 4, 5)   # Core mandates, collected on the 5th
B2B_A = (6, 7)             # B2B mandates, collected on the 5th
CORE_B = tuple(range(8, 15))  # Core mandates, collected on the 26th
DIRECT_DEBIT = CORE_A + B2B_A + CORE_B
TRANSFER = tuple(range(15, 40))

TARGET_HOLIDAYS = {dt.date(2025, 12, 25), dt.date(2025, 12, 26), dt.date(2026, 1, 1),
                   dt.date(2026, 4, 3), dt.date(2026, 4, 6), dt.date(2026, 5, 1)}


# --------------------------------------------------------------------------- helpers

def D(y, m, d):
    return dt.date(y, m, d)


def business_day(day):
    while day.weekday() >= 5 or day in TARGET_HOLIDAYS:
        day += dt.timedelta(days=1)
    return day


def month_start(k):
    """The first day of statement month k (k=0 is November 2025, k=11 is October 2026)."""
    return D(2025 + (10 + k) // 12, (10 + k) % 12 + 1, 1)


def month_end(k):
    return month_start(k + 1) - dt.timedelta(days=1) if k < 11 else D(2026, 10, 31)


def amount(n):
    """Monthly amount of customer n, in cents: EUR 400.50 + 25 per customer number."""
    return 40050 + 2500 * n


def eur(cents):
    return "%d.%02d" % divmod(cents, 100)


def be_iban(account7, bank="999"):
    bban10 = bank + "%07d" % account7
    chk = int(bban10) % 97 or 97
    bban = bban10 + "%02d" % chk
    cd = 98 - int(bban + "111400") % 97
    return "BE%02d%s" % (cd, bban)


def ogm(seq):
    base = "26%08d" % seq
    return base + "%02d" % (int(base) % 97 or 97)


def rf_reference(ref):
    """An RF creditor reference with valid check digits."""
    digits = "".join(str(int(c, 36)) for c in ref + "RF00")
    return "RF%02d%s" % (98 - int(digits) % 97, ref)


def iban_of(n, k=0):
    """The account a customer pays from in month k. C002 moves to a new account after its August return (AC04).
    C007 moves to another bank from September."""
    if n == 2 and k >= 10:
        return be_iban(2002)
    if n == 7 and k >= 10:
        return be_iban(5007, bank="998")
    return be_iban(1000 + n)


OWN_ACCOUNT = be_iban(9000001)
LANDLORD_IBAN = be_iban(3000001)
SUPPLIER_IBAN = be_iban(4000001)


def mandate_ref(n):
    return ("B2B-GF-%04d" if n in B2B_A else "CORE-GF-%04d") % n


def collection_date(n, k):
    day = 26 if n in CORE_B else 5
    return business_day(month_start(k).replace(day=day))


def e2e(n, day):
    return "GF-%s-%04d" % (day.strftime("%Y%m%d"), n)


# --------------------------------------------------------------------------- the spec

# Failed collections, by (customer, statement month k). Every one is a collection on the statement that comes back
# as a return or refund on a later day of the statement, with its reason code (None: the bank gives no reason).
#   retry: presented again 14 days after the collection date, and collected.
#   transfer: the customer paid the amount by transfer 15 days after the collection date.
#   booked: the day the return or refund is booked (default: three days after the collection date).
FAILURES = {
    (2, 0): {"code": "MS03", "retry": True},
    (3, 1): {"code": "MS03", "retry": True},
    (5, 2): {"code": "MS02", "transfer": True},
    (4, 3): {"code": "MS03", "retry": True},
    (5, 4): {"code": "MD06", "booked": D(2026, 4, 14)},  # a refund, eight weeks after a collection at most
    (3, 5): {"code": "AM04", "retry": True},
    (4, 6): {"code": "MS03", "retry": True},
    (2, 7): {"code": "MS03", "retry": True},
    (4, 8): {"code": None, "retry": True},  # returned without a reason on the statement
    (2, 9): {"code": "AC04", "retry": True},  # old account closed, collected again on the new one
    (5, 9): {"code": "MS02", "transfer": True},
    (3, 10): {"code": "MS03", "retry": True},
    (4, 10): {"code": "MD06", "booked": D(2026, 10, 20)},
    (7, 10): {"code": "MD01"},  # B2B mandate not registered at the customer's new bank
    (3, 11): {"code": "AM04"},
    (5, 11): {"code": "MS03"},
    (7, 11): {"code": "MD01"},
}

# Transfer customers: who pays how.
TYPO = {(29, 4), (30, 10)}             # a structured communication with wrong check digits
FREE_TEXT = (31, 32, 33, 34, 35)       # free text, no structured communication
RF_REF = (36, 37)                      # an RF creditor reference
EVERY_OTHER_MONTH = (38, 39)           # free text, every other month


def transfer_date(n, k):
    return business_day(month_start(k) + dt.timedelta(days=7 + (n - 15) // 2))


def build():
    collected, returns, transfers = [], [], []
    for n in DIRECT_DEBIT:
        scheme = "B2B" if n in B2B_A else "CORE"
        for k in range(12):
            c = collection_date(n, k)
            col = {"date": c, "n": n, "k": k, "cents": amount(n), "iban": iban_of(n, k), "scheme": scheme,
                   "e2e": e2e(n, c)}
            collected.append(col)
            fail = FAILURES.get((n, k))
            if not fail:
                continue
            booked = fail.get("booked") or business_day(c + dt.timedelta(days=3))
            returns.append(dict(col, code=fail["code"], booked=booked))
            if fail.get("retry"):
                r = business_day(c + dt.timedelta(days=14))
                collected.append({"date": r, "n": n, "k": k, "cents": amount(n), "iban": iban_of(n, k + 1),
                                  "scheme": scheme, "e2e": e2e(n, r)})
            if fail.get("transfer"):
                transfers.append({"date": business_day(c + dt.timedelta(days=15)), "n": n, "cents": amount(n),
                                  "ref": None, "text": "Betaling %s" % c.strftime("%m/%Y")})
    for n in TRANSFER:
        for k in range(12):
            if n in EVERY_OTHER_MONTH and k % 2:
                continue
            seq = (k + 1) * 100 + n
            t = {"date": transfer_date(n, k), "n": n, "cents": amount(n), "ref": None, "text": None}
            if n in FREE_TEXT or n in EVERY_OTHER_MONTH:
                t["text"] = "Betaling VF-%04d" % seq
            elif n in RF_REF:
                t["ref"] = ("ISO", rf_reference("GF%04d" % seq))
            else:
                digits = ogm(seq)
                if (n, k) in TYPO:
                    digits = digits[:10] + "%02d" % ((int(digits[10:]) + 1) % 100)
                t["ref"] = ("BBA", digits)
            transfers.append(t)
    transfers.append({"date": D(2026, 9, 30), "n": None, "cents": 250000, "ref": None,
                      "text": "Terugbetaling huurwaarborg"})
    return {"collected": collected, "returns": returns, "transfers": transfers}


# --------------------------------------------------------------------------- writers

def x(tag, text):
    return "<%s>%s</%s>" % (tag, escape(text), tag)


def amt(cents):
    return '<Amt Ccy="EUR">%s</Amt>' % eur(cents)


def bktxcd(domain, fmly, sub):
    return ("<BkTxCd><Domn><Cd>%s</Cd><Fmly><Cd>%s</Cd><SubFmlyCd>%s</SubFmlyCd></Fmly></Domn></BkTxCd>"
            % (domain, fmly, sub))


def debtor(name, iban):
    return "<RltdPties><Dbtr>%s</Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct></RltdPties>" % (x("Nm", name),
                                                                                                    iban)


def tx_collection(c, reason=False):
    """A collected direct debit, or (reason not False) its return: the same references, with RtrInf when the bank
    gives a reason."""
    ret = ("<RtrInf><Rsn><Cd>%s</Cd></Rsn></RtrInf>" % c["code"]) if reason and c.get("code") else ""
    return ("<TxDtls><Refs><EndToEndId>%s</EndToEndId><MndtId>%s</MndtId></Refs>"
            "<AmtDtls><TxAmt>%s</TxAmt></AmtDtls>%s<RmtInf>%s</RmtInf>%s</TxDtls>"
            % (c["e2e"], mandate_ref(c["n"]), amt(c["cents"]), debtor(NAMES[c["n"]].upper(), c["iban"]),
               x("Ustrd", "VF-%04d" % ((c["k"] + 1) * 100 + c["n"])), ret))


def tx_transfer(t):
    if t["n"] is None:
        name, iban = LANDLORD.upper(), LANDLORD_IBAN
    else:
        name, iban = NAMES[t["n"]].upper(), iban_of(t["n"])
    if t["ref"]:
        issuer, ref = t["ref"]
        rmt = ("<RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry><Issr>%s</Issr></Tp>"
               "<Ref>%s</Ref></CdtrRefInf></Strd></RmtInf>" % (issuer, ref))
    else:
        rmt = "<RmtInf>%s</RmtInf>" % x("Ustrd", t["text"])
    return ("<TxDtls><Refs><EndToEndId>NOTPROVIDED</EndToEndId></Refs><AmtDtls><TxAmt>%s</TxAmt></AmtDtls>%s%s"
            "</TxDtls>" % (amt(t["cents"]), debtor(name, iban), rmt))


def tx_supplier(cents):
    return ("<TxDtls><Refs><EndToEndId>NOTPROVIDED</EndToEndId></Refs><AmtDtls><TxAmt>%s</TxAmt></AmtDtls>"
            "<RltdPties><Cdtr>%s</Cdtr><CdtrAcct><Id><IBAN>%s</IBAN></Id></CdtrAcct></RltdPties>"
            "<RmtInf>%s</RmtInf></TxDtls>" % (amt(cents), x("Nm", SUPPLIER.upper()), SUPPLIER_IBAN,
                                              x("Ustrd", "Aankoop goederen")))


def entry(cents, cdi, day, bk, txs, ref):
    btch = "<Btch><NbOfTxs>%d</NbOfTxs></Btch>" % len(txs) if len(txs) > 1 else ""
    details = "<NtryDtls>%s%s</NtryDtls>" % (btch, "".join(txs)) if txs else ""
    return ("<Ntry>%s<CdtDbtInd>%s</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>%s</Dt></BookgDt>"
            "<ValDt><Dt>%s</Dt></ValDt><AcctSvcrRef>%s</AcctSvcrRef>%s%s</Ntry>"
            % (amt(cents), cdi, day.isoformat(), day.isoformat(), ref, bk, details))


def statement_entries(data, k):
    """The entries of statement month k: (date, order, cents, CRDT or DBIT, bank code, transactions)."""
    first, last = month_start(k), month_end(k)
    ents = []
    batches = {}
    for c in data["collected"]:
        if first <= c["date"] <= last:
            batches.setdefault((c["date"], c["scheme"]), []).append(c)
    for (day, scheme), cs in batches.items():
        cs.sort(key=lambda c: c["n"])
        ents.append((day, 0 if scheme == "CORE" else 1, sum(c["cents"] for c in cs), "CRDT",
                     bktxcd("PMNT", "IDDT", "ESDD" if scheme == "CORE" else "BBDD"), [tx_collection(c) for c in cs]))
    for t in data["transfers"]:
        if first <= t["date"] <= last:
            ents.append((t["date"], 2 + (t["n"] or 99) / 100.0, t["cents"], "CRDT", bktxcd("PMNT", "RCDT", "ESCT"),
                         [tx_transfer(t)]))
    for r in data["returns"]:
        if first <= r["booked"] <= last:
            ents.append((r["booked"], 4, r["cents"], "DBIT", bktxcd("PMNT", "IDDT", "UPDD"),
                         [tx_collection(r, reason=True)]))
    ents.append((business_day(first.replace(day=20)), 5, 845200, "DBIT", bktxcd("PMNT", "ICDT", "ESCT"),
                 [tx_supplier(845200)]))
    fee_day = last
    while fee_day.weekday() >= 5 or fee_day in TARGET_HOLIDAYS:
        fee_day -= dt.timedelta(days=1)
    ents.append((fee_day, 6, 1250, "DBIT", bktxcd("ACMT", "MDOP", "CHRG"), []))
    ents.sort(key=lambda e: (e[0], e[1]))
    return ents


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def write_statements(out, data):
    opening = 5000000
    names = []
    for k in range(12):
        first, last = month_start(k), month_end(k)
        ents = statement_entries(data, k)
        closing = opening + sum(e[2] if e[3] == "CRDT" else -e[2] for e in ents)
        body = "".join(entry(e[2], e[3], e[0], e[4], e[5], "%s%04d" % (first.strftime("%Y%m"), i))
                       for i, e in enumerate(ents, 1))
        created = (last + dt.timedelta(days=1)).isoformat() + "T06:00:00"
        stmt_id = "%s-%s" % (OWN_ACCOUNT[-6:], first.strftime("%Y%m"))
        doc = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Document xmlns="%s"><BkToCstmrStmt>'
               "<GrpHdr><MsgId>%s</MsgId><CreDtTm>%s</CreDtTm></GrpHdr>"
               "<Stmt><Id>%s</Id><ElctrncSeqNb>%d</ElctrncSeqNb><CreDtTm>%s</CreDtTm>"
               "<FrToDt><FrDtTm>%sT00:00:00</FrDtTm><ToDtTm>%sT23:59:59</ToDtTm></FrToDt>"
               "<Acct><Id><IBAN>%s</IBAN></Id><Ccy>EUR</Ccy><Ownr>%s</Ownr>"
               "<Svcr><FinInstnId><BIC>%s</BIC></FinInstnId></Svcr></Acct>"
               "<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>%s<CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>%s</Dt></Dt></Bal>"
               "<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>%s<CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>%s</Dt></Dt></Bal>"
               "%s</Stmt></BkToCstmrStmt></Document>\n"
               % (NS, stmt_id, created, stmt_id, k + 1, created, first.isoformat(), last.isoformat(), OWN_ACCOUNT,
                  x("Nm", COMPANY.upper()), BANK_BIC, amt(opening), first.isoformat(), amt(closing), last.isoformat(),
                  body))
        name = "camt053-%s.xml" % first.strftime("%Y-%m")
        write(os.path.join(out, name), doc)
        names.append(name)
        opening = closing
    return names


def main(out):
    os.makedirs(out, exist_ok=True)
    write_statements(out, build())
    return sorted(os.listdir(out))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo")
    for name in main(target):
        print(name)
