#!/usr/bin/env python3
"""
make_demo.py - builds the fictional demo exports in ../demo from one written-down spec.

The company is "Groothandel Fictief NV", a fictional Belgian wholesaler with 41 fictional
customers and one fictional landlord. Every name, address, e-mail address and IBAN is made
up. IBANs use bank code 999 and valid check digits. E-mail addresses use the reserved
.example domain.

The expected results in tests/expected_demo.json were written by hand from the spec in
this file (the CASES below), not by running the checks. test_demo.py also rebuilds the
demo into a temporary folder and checks that the files in ../demo are identical, so the
spec and the shipped files cannot drift apart.

Usage: python3 make_demo.py [output folder]
"""
import datetime as dt
import os
import sys
from xml.sax.saxutils import escape

AS_OF = dt.date(2026, 10, 31)
COMPANY = "Groothandel Fictief NV"

NAMES = [
    None,
    "Bakkerij Voorbeeld BV", "Brasserie Fictief NV", "Slagerij Proefmans BV", "Café Demo VOF",
    "Boulangerie Exemple SRL", "Garage Testmans BV", "Bloemen Fictief BV", "Restaurant Le Fictif SRL",
    "Apotheek Voorbeeld BV", "Drukkerij Demo NV", "Kapsalon Proef BV", "Hotel Fictief NV",
    "Bouwbedrijf Voorbeeld NV", "Transport Demo NV", "Logistique Fictive SA", "Frituur Testmans",
    "Superette Exemple SRL", "Kantoor Proefmans BV", "Fietsen Fictief BV", "Schoenen Demo BV",
    "Bistro Imaginaire SRL", "Wijnhandel Voorbeeld BV", "Traiteur Fictif SRL", "Drankhandel Testmans NV",
    "Elektro Demo BV", "Carrosserie Testmans BV", "Patisserie Exemple SRL", "Sportclub Fictief VZW",
    "Tuincentrum Voorbeeld NV", "Optiek Demo BV", "Boekhandel Proef BV", "Feestzaal Fictief BV",
    "IJssalon Voorbeeld BV", "Chocolatier Fictif SRL", "Viswinkel Demo BV", "Koffiebar Proefmans BV",
    "Meubelen Fictief NV", "Auberge Imaginaire SRL", "Speelgoed Voorbeeld BV", "Drankencentrale Demo NV",
    "Kermis Fictief VOF",
]
LANDLORD = "Immo Fictief NV"
SUPPLIERS = ["Leverancier Fictief NV", "Energie Fictief NV", "Verzekering Fictief NV"]

TARGET_HOLIDAYS = {dt.date(2025, 12, 25), dt.date(2025, 12, 26), dt.date(2026, 1, 1),
                   dt.date(2026, 4, 3), dt.date(2026, 4, 6), dt.date(2026, 5, 1)}


# --------------------------------------------------------------------------- helpers

def D(y, m, d):
    return dt.date(y, m, d)


def next_target_day(day):
    while day.weekday() >= 5 or day in TARGET_HOLIDAYS:
        day += dt.timedelta(days=1)
    return day


def amount(n):
    """Monthly invoice amount of customer n, in cents: EUR 400.50 + 25 per customer number."""
    return 40050 + 2500 * n


def eur_be(cents):
    """Belgian notation: 1.025,50 (used by the Dutch and French CSV exports)."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, frac = divmod(cents, 100)
    s = "{:,}".format(whole).replace(",", ".")
    return "%s%s,%02d" % (sign, s, frac)


def eur_xml(cents):
    return "%d.%02d" % divmod(cents, 100)


def be_iban(account7, bank="999"):
    bban10 = bank + "%07d" % account7
    chk = int(bban10) % 97 or 97
    bban = bban10 + "%02d" % chk
    cd = 98 - int(bban + "111400") % 97
    return "BE%02d%s" % (cd, bban)


def ogm(seq):
    base = "26%08d" % seq
    chk = int(base) % 97 or 97
    digits = base + "%02d" % chk
    return digits


def ogm_fmt(digits):
    return "+++%s/%s/%s+++" % (digits[0:3], digits[3:7], digits[7:12])


def ddmmyyyy(day):
    return day.strftime("%d/%m/%Y") if day else ""


def month_date(k):
    """The 5th of invoice month k (k=0 is November 2025, k=11 is October 2026)."""
    y, m = 2025 + (10 + k) // 12, (10 + k) % 12 + 1
    return D(y, m, 5)


# Seven direct debit customers without failures are invoiced on the 26th. With 30 days of terms they are collected
# on the 25th (August 25, September 25, and October 26 because October 25 is a Sunday): a second collection day next
# to the 4th, with 21 collections over three months, so the month work can compare two days.
LATE_RUN = (2, 3, 5, 7, 8, 11, 12)


def invoice_date(n, k):
    """Invoice date of customer n in invoice month k: the 5th, or the 26th for the LATE_RUN customers."""
    d = month_date(k)
    return d.replace(day=26) if n in LATE_RUN else d


def customer_number(n):
    return "K%04d" % (1000 + n)


def iban_of(n):
    return be_iban(1000 + n)


OLD_IBAN_C004 = be_iban(2004)
OWN_ACCOUNT_1 = be_iban(9000001)
OWN_ACCOUNT_2 = be_iban(9000002)
LANDLORD_IBAN = be_iban(3000001)
SUPPLIER_IBANS = [be_iban(4000001), be_iban(4000002), be_iban(4000003)]


def terms(n):
    return 14 if 16 <= n <= 20 else 30


def invoiced(n, k):
    if n == 15:
        return k >= 8
    if n == 41:
        return k == 8
    return True


def invoice_seq(n, k):
    if k <= 7:
        return 39 * k + (n if n <= 14 else n - 1)
    if k == 8:
        return 312 + n
    return 353 + 40 * (k - 9) + n


def due_date(n, k):
    return invoice_date(n, k) + dt.timedelta(days=terms(n))


def collection_date(n, k):
    return next_target_day(due_date(n, k))


# --------------------------------------------------------------------------- the spec

# Direct debit customers and their exceptions. Key: (customer, invoice month k).
# "reject": rejected before settlement (pain.002 or the bank's failed-collections CSV).
# "return": collected, then returned or refunded after settlement (camt.053 and camt.054).
DD_CORE = range(1, 13)
DD_B2B = (13, 14)
# Failures touch only four of the 14 direct debit customers (C004, C006, C009, C010). The most common code is
# MS03 ("reason not specified", what many banks send instead of AM04).
DD_EXCEPTIONS = {
    (4, 0): {"code": "MS03", "via": "csv", "retry": D(2025, 12, 19)},
    (6, 1): {"code": "MS03", "via": "csv", "retry": D(2026, 1, 19)},
    (10, 2): {"code": "MS02", "via": "csv", "transfer": D(2026, 2, 20)},
    (9, 3): {"code": "MS03", "via": "csv", "retry": D(2026, 3, 20)},
    (10, 4): {"code": "MD06", "via": "csv", "returned": D(2026, 5, 12)},  # refund, invoice stays open
    (6, 5): {"code": "ED05", "via": "csv", "retry": D(2026, 5, 19)},  # settlement failed (EPC code, not Twikey's)
    (9, 6): {"code": "MS03", "via": "csv", "retry": D(2026, 6, 18)},
    (4, 7): {"code": "MS03", "via": "csv", "retry": D(2026, 7, 20)},
    # old IBAN, retried on the new one on the 18th: with the September retry on the 18th, day 18 has two months
    (4, 8): {"code": "AC04", "via": "pain002", "retry": D(2026, 8, 18)},
    (10, 8): {"code": "MS02", "via": "pain002"},  # refused, invoice stays open
    (6, 9): {"code": "MS03", "via": "camt", "returned": D(2026, 9, 8), "retry": D(2026, 9, 18)},
    (9, 9): {"code": "MD06", "via": "camt", "returned": D(2026, 10, 20)},  # refund, invoice stays open
    (6, 10): {"code": "AM04", "via": "camt", "returned": D(2026, 10, 7)},  # not retried yet
    (10, 10): {"code": "MS03", "via": "camt", "returned": D(2026, 10, 9)},  # not retried yet
}
# A failure on an October 2025 invoice, before the invoice history starts.
PRE_HISTORY_FAILURE = {"n": 6, "date": D(2025, 11, 5), "returned": D(2025, 11, 7), "code": "MS03",
                       "amount": amount(6), "e2e": "E2E-20251105-0006"}

REASON_TEXT_FR = {"AM04": "Provision insuffisante", "MS02": "Refus du débiteur", "MD06": "Remboursement demandé",
                  "MS03": "Raison non spécifiée", "ED05": "Échec du règlement", "AC04": "Compte clôturé",
                  "MD01": "Mandat inexistant"}

# Mandate list rows, in file order. sig=None means the date is missing. signed False means no
# signature on file. ref "" means the reference is missing.
MANDATES = (
    [{"ref": "FICT-M-%04d" % n, "n": n, "scheme": "CORE", "sig": D(2024, 1, 15), "signed": True,
      "last": D(2026, 10, 5), "confirmed": None} for n in DD_CORE]
    + [{"ref": "FICT-M-0009B", "n": 9, "scheme": "CORE", "sig": D(2025, 6, 1), "signed": True, "last": None,
        "confirmed": None}]
    + [{"ref": "FICT-B-%04d" % n, "n": n, "scheme": "B2B", "sig": D(2024, 3, 1), "signed": True,
        "last": D(2026, 10, 5), "confirmed": True} for n in DD_B2B]
    + [{"ref": "FICT-B-0015", "n": 15, "scheme": "B2B", "sig": D(2026, 7, 10), "signed": True, "last": None,
        "confirmed": False}]
    + [{"ref": "FICT-M-0122", "n": 22, "scheme": "CORE", "sig": D(2019, 5, 1), "signed": True,
        "last": D(2022, 11, 30), "confirmed": None},
       {"ref": "FICT-M-0127", "n": 27, "scheme": "CORE", "sig": D(2020, 2, 1), "signed": True,
        "last": D(2023, 8, 31), "confirmed": None},
       {"ref": "FICT-M-0133", "n": 33, "scheme": "CORE", "sig": D(2020, 9, 1), "signed": True,
        "last": D(2023, 12, 20), "confirmed": None},
       {"ref": "FICT-M-0141", "n": 41, "scheme": "CORE", "sig": D(2019, 3, 1), "signed": True,
        "last": D(2023, 4, 20), "confirmed": None},
       {"ref": "", "n": 18, "scheme": "CORE", "sig": D(2021, 5, 12), "signed": True, "last": None,
        "confirmed": None},
       {"ref": "FICT-M-0003", "n": 19, "scheme": "CORE", "sig": D(2023, 2, 10), "signed": True, "last": None,
        "confirmed": None}]
)
MANDATES[4]["sig"] = None      # C005: signature date missing
MANDATES[6]["signed"] = False  # C007: no signature on file
for _m in MANDATES:
    if _m["n"] in LATE_RUN and _m["last"]:
        _m["last"] = D(2026, 10, 26)  # the October run of the LATE_RUN customers


def mandate_ref(n):
    for m in MANDATES:
        if m["n"] == n and m["ref"]:
            return m["ref"]
    return None


# --------------------------------------------------------------------------- invoices and payments

def build():
    invoices = []          # dicts per invoice
    collected = []         # successful presentations: date, n, k, cents, iban, scheme, e2e
    rejects = []           # pain.002 rejects
    csv_failures = []      # failed-collections CSV rows
    returns = []           # camt returns
    transfers = []         # incoming credit transfers: date, n or None, cents, ogm, text, account

    def e2e(n, k, when):
        return "E2E-%s-%04d" % (when.strftime("%Y%m%d"), invoice_seq(n, k))

    for n in range(1, 42):
        for k in range(12):
            if not invoiced(n, k):
                continue
            seq = invoice_seq(n, k)
            inv = {"n": n, "k": k, "seq": seq, "number": "VF-%04d" % seq, "date": invoice_date(n, k),
                   "due": due_date(n, k), "cents": amount(n), "open": amount(n), "paid": None,
                   "method": "", "ogm": ogm(seq), "status": "Open"}
            invoices.append(inv)

    by_key = {(i["n"], i["k"]): i for i in invoices}

    def pay(inv, when, method):
        inv["paid"], inv["method"], inv["open"], inv["status"] = when, method, 0, "Betaald"

    # Direct debit customers C001-C014.
    for n in list(DD_CORE) + list(DD_B2B):
        scheme = "B2B" if n in DD_B2B else "CORE"
        for k in range(12):
            inv = by_key[(n, k)]
            c = collection_date(n, k)
            if c > AS_OF:
                continue
            ex = DD_EXCEPTIONS.get((n, k))
            iban = OLD_IBAN_C004 if (n, k) == (4, 8) else iban_of(n)
            if not ex:
                pay(inv, c, "Domiciliëring")
                collected.append({"date": c, "n": n, "k": k, "cents": inv["cents"], "iban": iban,
                                  "scheme": scheme, "e2e": e2e(n, k, c)})
                continue
            fail = {"date": c, "n": n, "k": k, "cents": inv["cents"], "iban": iban, "scheme": scheme,
                    "code": ex["code"], "e2e": e2e(n, k, c), "returned": ex.get("returned", c)}
            if ex["via"] == "csv":
                csv_failures.append(fail)
            elif ex["via"] == "pain002":
                rejects.append(fail)
            else:
                collected.append({"date": c, "n": n, "k": k, "cents": inv["cents"], "iban": iban,
                                  "scheme": scheme, "e2e": fail["e2e"]})
                returns.append(fail)
            if "retry" in ex:
                pay(inv, ex["retry"], "Domiciliëring")
                if ex["retry"] >= D(2026, 8, 1):
                    collected.append({"date": ex["retry"], "n": n, "k": k, "cents": inv["cents"],
                                      "iban": iban_of(n), "scheme": scheme, "e2e": e2e(n, k, ex["retry"])})
            elif "transfer" in ex:
                pay(inv, ex["transfer"], "Overschrijving")

    # C015: new B2B customer, mandate never confirmed at the customer's bank.
    for k in (8, 9, 10):
        inv = by_key[(15, k)]
        rejects.append({"date": collection_date(15, k), "n": 15, "k": k, "cents": inv["cents"],
                        "iban": iban_of(15), "scheme": "B2B", "code": "MD01",
                        "e2e": e2e(15, k, collection_date(15, k)), "returned": collection_date(15, k)})
    # C041: seasonal customer, collected on a mandate that expired in April 2026.
    rejects.append({"date": collection_date(41, 8), "n": 41, "k": 8, "cents": amount(41), "iban": iban_of(41),
                    "scheme": "CORE", "code": "MD01", "e2e": e2e(41, 8, collection_date(41, 8)),
                    "returned": collection_date(41, 8)})

    # Transfer customers.
    for n in range(16, 41):
        for k in range(12):
            inv = by_key[(n, k)]
            if 16 <= n <= 25:
                when = inv["due"] - dt.timedelta(days=1)
            elif 26 <= n <= 31:
                when = inv["due"] + dt.timedelta(days=12)
            elif 32 <= n <= 36:
                when = inv["due"] + dt.timedelta(days=3 * k)
            else:
                when = inv["due"] + dt.timedelta(days=45) if k <= 5 else None
            if when is None or when > AS_OF:
                continue
            if n == 23 and k in (9, 10):
                when = D(2026, 9, 10)  # C023 pays August and September in one transfer
            if (n, k) == (28, 10):
                # Paid at the bank, still open in the books.
                transfers.append({"date": when, "n": n, "cents": inv["cents"], "ogm": inv["ogm"], "text": ""})
                continue
            if (n, k) == (31, 9):
                # Partial payment, the books show the rest as open.
                transfers.append({"date": when, "n": n, "cents": 60000, "ogm": inv["ogm"], "text": ""})
                inv["open"], inv["status"] = inv["cents"] - 60000, "Gedeeltelijk betaald"
                continue
            pay(inv, when, "Overschrijving")
            if when < D(2026, 8, 1):
                continue
            if n == 23 and k == 10:
                continue  # covered by the bundled transfer added below
            if n == 23 and k == 9:
                transfers.append({"date": when, "n": n, "cents": 2 * inv["cents"], "ogm": None,
                                  "text": "Facturen %s en %s" % (inv["number"], by_key[(23, 10)]["number"])})
                continue
            if 32 <= n <= 36:
                transfers.append({"date": when, "n": n, "cents": inv["cents"], "ogm": None,
                                  "text": "Factuur %s" % inv["number"]})
                continue
            digits = inv["ogm"]
            if (n, k) == (19, 9):
                digits = digits[:10] + "%02d" % ((int(digits[10:]) + 1) % 100)  # typo in the check digits
            transfers.append({"date": when, "n": n, "cents": inv["cents"], "ogm": digits, "text": ""})
            if (n, k) == (17, 10):
                transfers.append({"date": D(2026, 9, 25), "n": n, "cents": inv["cents"], "ogm": inv["ogm"],
                                  "text": ""})  # paid twice

    transfers.append({"date": D(2026, 10, 12), "n": 24, "cents": 30000, "ogm": None, "text": "Voorschot bestelling"})
    # C024 pays the October invoice of C026, a company of the same family, with its invoice number in the text.
    transfers.append({"date": D(2026, 10, 28), "n": 24, "cents": amount(26), "ogm": None,
                      "text": "Factuur %s" % by_key[(26, 11)]["number"]})
    transfers.append({"date": D(2026, 9, 30), "n": None, "cents": 250000, "ogm": None,
                      "text": "Terugbetaling huurwaarborg"})
    transfers.append({"date": D(2026, 10, 20), "n": 38, "cents": 50000, "ogm": None,
                      "text": "Deel betaling %s" % by_key[(38, 6)]["number"]})

    for t in transfers:
        t["account"] = 2 if (t["n"] is None or 16 <= t["n"] <= 25) else 1

    return {"invoices": invoices, "by_key": by_key, "collected": collected, "rejects": rejects,
            "csv_failures": csv_failures, "returns": returns, "transfers": transfers}


# --------------------------------------------------------------------------- writers

def address(n):
    return "Voorbeeldstraat %d, 9000 Gent" % n


def email(n):
    return "boekhouding@klant%02d.example" % n


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def write_invoice_history(out, data):
    head = ("Factuurnummer;Klantnummer;Klant;Adres;E-mail;Factuurdatum;Vervaldatum;Bedrag;Openstaand;Status;"
            "Betaaldatum;Betaalwijze;Gestructureerde mededeling")
    rows = [head]
    for inv in sorted(data["invoices"], key=lambda i: (i["n"], i["k"])):
        n = inv["n"]
        rows.append(";".join([
            inv["number"], customer_number(n), NAMES[n], address(n), email(n), ddmmyyyy(inv["date"]),
            ddmmyyyy(inv["due"]), eur_be(inv["cents"]), eur_be(inv["open"]), inv["status"],
            ddmmyyyy(inv["paid"]), inv["method"], ogm_fmt(inv["ogm"])]))
    write(os.path.join(out, "factuurhistoriek.csv"), "\r\n".join(rows) + "\r\n")


def write_mandates(out):
    head = ("Mandate reference,Customer number,Debtor name,Debtor address,IBAN,Scheme,Signature date,Signed,"
            "Status,Last collection,Confirmed by debtor bank")
    rows = [head]
    for m in MANDATES:
        n = m["n"]
        name = NAMES[n].rsplit(" ", 1)[0] if NAMES[n].split()[-1] in ("BV", "NV", "SRL", "SA", "VOF", "VZW") \
            else NAMES[n]
        conf = "" if m["confirmed"] is None else ("yes" if m["confirmed"] else "no")
        rows.append(",".join([
            m["ref"], customer_number(n), '"%s"' % name, '"%s"' % address(n), iban_of(n), m["scheme"],
            m["sig"].isoformat() if m["sig"] else "", "yes" if m["signed"] else "no", "active",
            m["last"].isoformat() if m["last"] else "", conf]))
    write(os.path.join(out, "mandates-export.csv"), "\n".join(rows) + "\n")


def write_failed_csv(out, data):
    head = ("Date d'encaissement;Date du retour;Montant;Débiteur;IBAN débiteur;Référence du mandat;Code motif;"
            "Libellé motif;Schéma;Référence de bout en bout")
    rows = [head]
    pre = PRE_HISTORY_FAILURE
    items = [dict(pre, iban=iban_of(pre["n"]), scheme="CORE", cents=pre["amount"])] + data["csv_failures"]
    for f in sorted(items, key=lambda x: x["date"]):
        n = f["n"]
        rows.append(";".join([
            ddmmyyyy(f["date"]), ddmmyyyy(f["returned"]), eur_be(f["cents"]), NAMES[n].upper(), f["iban"],
            mandate_ref(n), f["code"], REASON_TEXT_FR[f["code"]], f["scheme"], f["e2e"]]))
    write(os.path.join(out, "impayes-2025-11_2026-07.csv"), "\r\n".join(rows) + "\r\n")


def write_bank_csv(out, data):
    head = ("Rekening;Boekingsdatum;Valutadatum;Bedrag;Munt;Rekening tegenpartij;Naam tegenpartij;Adres tegenpartij;"
            "Gestructureerde mededeling;Vrije mededeling")
    rows = ["Rekeningoverzicht %s %s" % (OWN_ACCOUNT_2, COMPANY), "Periode 01/08/2026 - 31/10/2026", head]
    lines = []
    for t in data["transfers"]:
        if t["account"] != 2:
            continue
        if t["n"] is None:
            name, iban, adr = LANDLORD, LANDLORD_IBAN, "Huurlaan 1, 1000 Brussel"
        else:
            name, iban, adr = NAMES[t["n"]].upper(), iban_of(t["n"]), address(t["n"])
        lines.append((t["date"], t["cents"], iban, name, adr, ogm_fmt(t["ogm"]) if t["ogm"] else "", t["text"]))
    for day, cents, idx in ((D(2026, 8, 20), -84520, 1), (D(2026, 9, 15), -120000, 2), (D(2026, 10, 20), -84520, 1)):
        lines.append((day, cents, SUPPLIER_IBANS[idx], SUPPLIERS[idx].upper(), "Leverancierslaan 5, 2000 Antwerpen",
                      "", "Factuur leverancier"))
    for day, cents, iban, name, adr, struct, text in sorted(lines, key=lambda x: (x[0], x[2], x[1])):
        rows.append(";".join([OWN_ACCOUNT_2, ddmmyyyy(day), ddmmyyyy(day), eur_be(cents), "EUR", iban, name, adr,
                              struct, text]))
    write(os.path.join(out, "rekening2-aug-okt-2026.csv"), "\r\n".join(rows) + "\r\n")


NS053 = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"
NS054 = "urn:iso:std:iso:20022:tech:xsd:camt.054.001.02"
NS002 = "urn:iso:std:iso:20022:tech:xsd:pain.002.001.03"


def x(tag, text):
    return "<%s>%s</%s>" % (tag, escape(text), tag)


def amt(cents):
    return '<Amt Ccy="EUR">%s</Amt>' % eur_xml(cents)


def bktxcd(fmly, sub):
    return ("<BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>%s</Cd><SubFmlyCd>%s</SubFmlyCd></Fmly></Domn></BkTxCd>"
            % (fmly, sub))


def tx_transfer(t):
    if t["n"] is None:
        name, iban = LANDLORD, LANDLORD_IBAN
    else:
        name, iban = NAMES[t["n"]].upper(), iban_of(t["n"])
    if t["ogm"]:
        rmt = ("<RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry><Issr>BBA</Issr></Tp>"
               "<Ref>%s</Ref></CdtrRefInf></Strd></RmtInf>" % t["ogm"])
    else:
        rmt = "<RmtInf>%s</RmtInf>" % x("Ustrd", t["text"])
    return ("<TxDtls><Refs><EndToEndId>NOTPROVIDED</EndToEndId></Refs><AmtDtls><TxAmt>%s</TxAmt></AmtDtls>"
            "<RltdPties><Dbtr>%s</Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct></RltdPties>%s</TxDtls>"
            % (amt(t["cents"]), x("Nm", name), iban, rmt))


def tx_collection(c, data, with_return_code=None):
    n = c["n"]
    inv = data["by_key"][(n, c["k"])]
    ret = ("<RtrInf><Rsn><Cd>%s</Cd></Rsn></RtrInf>" % with_return_code) if with_return_code else ""
    return ("<TxDtls><Refs><EndToEndId>%s</EndToEndId><MndtId>%s</MndtId></Refs><AmtDtls><TxAmt>%s</TxAmt>"
            "</AmtDtls><RltdPties><Dbtr>%s</Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct></RltdPties>"
            "<RmtInf>%s</RmtInf>%s</TxDtls>"
            % (c["e2e"], mandate_ref(n), amt(c["cents"]), x("Nm", NAMES[n].upper()), c["iban"],
               x("Ustrd", "Factuur %s" % inv["number"]), ret))


def entry(cents, cdi, day, bk, txs, ref):
    btch = "<Btch><NbOfTxs>%d</NbOfTxs></Btch>" % len(txs) if len(txs) > 1 else ""
    return ("<Ntry><NtryRef>%s</NtryRef>%s<CdtDbtInd>%s</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>%s</Dt></BookgDt>"
            "<ValDt><Dt>%s</Dt></ValDt><AcctSvcrRef>%s</AcctSvcrRef>%s<NtryDtls>%s%s</NtryDtls></Ntry>"
            % (ref, amt(cents), cdi, day.isoformat(), day.isoformat(), ref, bk, btch, "".join(txs)))


def statement_entries(data, first, last):
    ents = []
    for t in data["transfers"]:
        if t["account"] == 1 and first <= t["date"] <= last:
            ents.append((t["date"], 1, t["cents"], "CRDT", bktxcd("RCDT", "ESCT"), [tx_transfer(t)]))
    batches = {}
    for c in data["collected"]:
        if first <= c["date"] <= last:
            batches.setdefault((c["date"], c["scheme"]), []).append(c)
    for (day, scheme), cs in sorted(batches.items()):
        cs.sort(key=lambda c: c["n"])
        ents.append((day, 0, sum(c["cents"] for c in cs), "CRDT", bktxcd("IDDT", "ESDD" if scheme == "CORE" else "BBDD"),
                     [tx_collection(c, data) for c in cs]))
    for r in data["returns"]:
        if first <= r["returned"] <= last:
            ents.append((r["returned"], 2, r["cents"], "DBIT", bktxcd("IDDT", "UPDD"),
                         [tx_collection(r, data, r["code"])]))
    for day, cents in ((D(2026, 8, 25), 1250000), (D(2026, 9, 25), 1180000), (D(2026, 10, 26), 1320000)):
        if first <= day <= last:
            tx = ("<TxDtls><Refs><EndToEndId>NOTPROVIDED</EndToEndId></Refs><AmtDtls><TxAmt>%s</TxAmt></AmtDtls>"
                  "<RltdPties><Cdtr>%s</Cdtr><CdtrAcct><Id><IBAN>%s</IBAN></Id></CdtrAcct></RltdPties>"
                  "<RmtInf>%s</RmtInf></TxDtls>" % (amt(cents), x("Nm", SUPPLIERS[0].upper()), SUPPLIER_IBANS[0],
                                                    x("Ustrd", "Aankoop goederen")))
            ents.append((day, 3, cents, "DBIT", bktxcd("ICDT", "ESCT"), [tx]))
    ents.sort(key=lambda e: (e[0], e[1], e[2]))
    return ents


def write_camt053(out, data):
    opening = 5000000
    for (y, m, last_day) in ((2026, 8, 31), (2026, 9, 30), (2026, 10, 31)):
        first, last = D(y, m, 1), D(y, m, last_day)
        ents = statement_entries(data, first, last)
        closing = opening + sum(e[2] if e[3] == "CRDT" else -e[2] for e in ents)
        body = []
        for i, e in enumerate(ents, 1):
            body.append(entry(e[2], e[3], e[0], e[4], e[5], "GF%02d%02d%04d" % (y % 100, m, i)))
        doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="%s"><BkToCstmrStmt>'
               "<GrpHdr><MsgId>GF-STMT-%d-%02d</MsgId><CreDtTm>%sT06:00:00</CreDtTm></GrpHdr>"
               "<Stmt><Id>GF-STMT-%d-%02d</Id><ElctrncSeqNb>%d</ElctrncSeqNb><CreDtTm>%sT06:00:00</CreDtTm>"
               "<FrToDt><FrDtTm>%sT00:00:00</FrDtTm><ToDtTm>%sT23:59:59</ToDtTm></FrToDt>"
               "<Acct><Id><IBAN>%s</IBAN></Id><Ccy>EUR</Ccy></Acct>"
               '<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>%s<CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>%s</Dt></Dt></Bal>'
               '<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>%s<CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>%s</Dt></Dt></Bal>'
               "%s</Stmt></BkToCstmrStmt></Document>\n"
               % (NS053, y, m, (last + dt.timedelta(days=1)).isoformat(), y, m, m, (last + dt.timedelta(days=1)).isoformat(),
                  first.isoformat(), last.isoformat(), OWN_ACCOUNT_1, amt(opening), first.isoformat(), amt(closing),
                  last.isoformat(), "".join(body)))
        write(os.path.join(out, "camt053-%d-%02d.xml" % (y, m)), doc)
        opening = closing


def write_camt054(out, data):
    blocks = []
    for i, r in enumerate(sorted(data["returns"], key=lambda r: r["returned"]), 1):
        ref = "GF54%04d" % i
        e = entry(r["cents"], "DBIT", r["returned"], bktxcd("IDDT", "UPDD"), [tx_collection(r, data, r["code"])], ref)
        blocks.append("<Ntfctn><Id>GF-NTF-%04d</Id><CreDtTm>%sT07:00:00</CreDtTm>"
                      "<Acct><Id><IBAN>%s</IBAN></Id><Ccy>EUR</Ccy></Acct>%s</Ntfctn>"
                      % (i, r["returned"].isoformat(), OWN_ACCOUNT_1, e))
    doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="%s"><BkToCstmrDbtCdtNtfctn>'
           "<GrpHdr><MsgId>GF-NTF-2026</MsgId><CreDtTm>2026-10-21T07:00:00</CreDtTm></GrpHdr>%s"
           "</BkToCstmrDbtCdtNtfctn></Document>\n" % (NS054, "".join(blocks)))
    write(os.path.join(out, "camt054-returns-2026.xml"), doc)


def tx_reject(r):
    n = r["n"]
    return ("<TxInfAndSts><StsId>ST-%s</StsId><OrgnlEndToEndId>%s</OrgnlEndToEndId><TxSts>RJCT</TxSts>"
            "<StsRsnInf><Rsn><Cd>%s</Cd></Rsn></StsRsnInf><OrgnlTxRef>"
            '<Amt><InstdAmt Ccy="EUR">%s</InstdAmt></Amt><ReqdColltnDt>%s</ReqdColltnDt>'
            "<PmtTpInf><SvcLvl><Cd>SEPA</Cd></SvcLvl><LclInstrm><Cd>%s</Cd></LclInstrm><SeqTp>RCUR</SeqTp></PmtTpInf>"
            "<MndtRltdInf><MndtId>%s</MndtId></MndtRltdInf>"
            "<Dbtr>%s</Dbtr><DbtrAcct><Id><IBAN>%s</IBAN></Id></DbtrAcct></OrgnlTxRef></TxInfAndSts>"
            % (r["e2e"], r["e2e"], r["code"], eur_xml(r["cents"]), r["date"].isoformat(), r["scheme"],
               mandate_ref(n), x("Nm", NAMES[n].upper()), r["iban"]))


def write_pain002(out, data):
    by_month = {}
    for r in data["rejects"]:
        by_month.setdefault((r["date"].year, r["date"].month), []).append(r)
    for (y, m), items in sorted(by_month.items()):
        groups = {}
        for r in sorted(items, key=lambda r: (r["scheme"], r["n"])):
            groups.setdefault((r["date"], r["scheme"]), []).append(r)
        day = items[0]["date"]
        pmt = []
        for (gday, scheme), rs in sorted(groups.items(), key=lambda g: (g[0][0], g[0][1] != "CORE")):
            pmt.append("<OrgnlPmtInfAndSts><OrgnlPmtInfId>GF-SDD-%s-%s</OrgnlPmtInfId><PmtInfSts>PART</PmtInfSts>%s"
                       "</OrgnlPmtInfAndSts>" % (gday.strftime("%Y%m%d"), scheme, "".join(tx_reject(r) for r in rs)))
        doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="%s"><CstmrPmtStsRpt>'
               "<GrpHdr><MsgId>GF-PSR-%s</MsgId><CreDtTm>%sT08:00:00</CreDtTm></GrpHdr>"
               "<OrgnlGrpInfAndSts><OrgnlMsgId>GF-SDD-%s</OrgnlMsgId><OrgnlMsgNmId>pain.008.001.02</OrgnlMsgNmId>"
               "<GrpSts>PART</GrpSts></OrgnlGrpInfAndSts>%s</CstmrPmtStsRpt></Document>\n"
               % (NS002, day.strftime("%Y%m%d"), (day - dt.timedelta(days=1)).isoformat(), day.strftime("%Y%m%d"),
                  "".join(pmt)))
        write(os.path.join(out, "pain002-%d-%02d.xml" % (y, m)), doc)


def main(out):
    os.makedirs(out, exist_ok=True)
    data = build()
    write_invoice_history(out, data)
    write_mandates(out)
    write_failed_csv(out, data)
    write_bank_csv(out, data)
    write_camt053(out, data)
    write_camt054(out, data)
    write_pain002(out, data)
    return sorted(os.listdir(out))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo")
    for name in main(target):
        print(name)
