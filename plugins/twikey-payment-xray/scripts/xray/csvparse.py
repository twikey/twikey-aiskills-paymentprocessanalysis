"""CSV exports: header detection in English, Dutch and French, value parsing, fail closed.

A file is read only when its header row is recognized and every field its kind needs is mapped.
Otherwise the result has status "needs_mapping" and describes the columns without a single cell
value: per column its position, its header only when the header is a column name this module knows
(or the user named), and the shape of its values ("date", "amount", "IBAN-like", "text, 12 chars").
A row is taken for the header row only when it has two known column names and no cell that looks
like a value (a date, an amount, a number, an IBAN, an e-mail address), so a preamble line such as
"Rekening;BE68...;Naam;Jan Peeters" is never shown as headers. Columns that are not on the allowlist
of the detected kind are dropped and reported by a safe label.
"""
import csv
import datetime as dt
import io
import re

from . import reasons
from .common import norm_text, num

# --------------------------------------------------------------------------- column names

# (header as written in an export) -> canonical field. Matching is exact after norm_text().
_SYN = {
    "invoice_number": [
        "invoice number", "invoice no", "invoice nr", "invoice", "invoice id", "invoice reference", "document number",
        "doc number", "factuurnummer", "factuurnr", "factuur nr", "factuur", "nummer factuur", "documentnummer",
        "boekstuknummer", "numero de facture", "n facture", "no facture", "numero facture", "facture",
        "n de facture", "n de la facture"],
    "customer_number": [
        "customer number", "customer no", "customer nr", "customer id", "customer code", "client number", "client id",
        "client code", "debtor number", "debtor id", "klantnummer", "klantnr", "klant nr", "klantcode",
        "debiteurnummer", "debiteurnr", "relatienummer", "relatiecode", "numero client", "numero de client", "n client",
        "code client", "reference client"],
    "customer_name": [
        "customer", "customer name", "client", "client name", "company", "company name", "klant", "klantnaam",
        "naam klant", "bedrijf", "bedrijfsnaam", "nom du client", "nom client", "raison sociale", "societe"],
    "debtor_name": [
        "debtor", "debtor name", "payer", "payer name", "debiteur", "naam debiteur", "debiteurnaam", "nom du debiteur",
        "nom debiteur"],
    "name": ["name", "naam", "nom", "account holder", "rekeninghouder", "titulaire"],
    "date": ["date", "datum"],
    "invoice_date": [
        "invoice date", "date of invoice", "issue date", "document date", "factuurdatum", "datum factuur",
        "documentdatum", "date de facture", "date facture", "date d emission"],
    "due_date": [
        "due date", "payment due date", "vervaldatum", "vervaldag", "verval datum", "uiterste betaaldatum",
        "date d echeance", "echeance", "date echeance", "date limite de paiement"],
    "paid_date": [
        "paid date", "payment date", "date paid", "paid on", "betaaldatum", "datum betaling", "betaald op",
        "datum betaald", "date de paiement", "date paiement", "paye le", "date de reglement"],
    "amount": [
        "amount", "total", "total amount", "amount incl vat", "invoice amount", "gross amount", "bedrag", "totaal",
        "bedrag incl btw", "totaalbedrag", "factuurbedrag", "montant", "montant ttc", "total ttc", "montant total",
        "montant de la facture"],
    "open_amount": [
        "open amount", "outstanding", "outstanding amount", "balance due", "amount due", "remaining", "openstaand",
        "openstaand bedrag", "open bedrag", "nog te betalen", "montant ouvert", "reste a payer", "solde du",
        "montant du"],
    "currency": ["currency", "ccy", "munt", "munteenheid", "devies", "devise", "monnaie"],
    "status": ["status", "state", "invoice status", "payment status", "staat", "betaalstatus", "statut", "etat"],
    "method": [
        "payment method", "method", "payment type", "betaalwijze", "betaalmethode", "betalingswijze",
        "mode de paiement", "moyen de paiement", "methode de paiement"],
    "structured_communication": [
        "structured communication", "structured reference", "ogm", "vcs", "gestructureerde mededeling",
        "gestruct mededeling", "communication structuree", "reference structuree"],
    "terms_days": [
        "payment terms", "terms", "payment term", "terms days", "betalingstermijn", "betaaltermijn", "termijn",
        "betalingsvoorwaarden", "delai de paiement", "conditions de paiement"],
    "booking_date": [
        "booking date", "transaction date", "posting date", "execution date", "boekingsdatum", "uitvoeringsdatum",
        "verrichtingsdatum", "transactiedatum", "date de comptabilisation", "date d execution",
        "date de l operation", "date operation", "date de transaction"],
    "value_date": ["value date", "valutadatum", "valuta datum", "datum valuta", "date valeur", "date de valeur"],
    "counterparty_name": [
        "counterparty name", "name counterparty", "counterparty", "beneficiary", "naam tegenpartij",
        "naam van de tegenpartij", "naam tegenrekening", "naam begunstigde", "naam tegenpartij bevat",
        "nom de la contrepartie", "nom contrepartie", "nom du donneur d ordre"],
    "counterparty_iban": [
        "counterparty account", "counterparty iban", "account counterparty", "iban counterparty", "beneficiary account",
        "rekening tegenpartij", "rekeningnummer tegenpartij", "tegenrekening", "iban tegenpartij",
        "rekening van de tegenpartij", "compte contrepartie", "compte de la contrepartie", "iban contrepartie",
        "numero de compte de la contrepartie"],
    "iban": ["iban", "debtor iban", "iban debiteur", "iban du debiteur", "rekeningnummer debiteur",
             "compte du debiteur", "debtor account"],
    "own_account": ["account", "account number", "own account", "rekening", "rekeningnummer", "eigen rekening",
                    "compte", "numero de compte", "votre compte"],
    "communication": [
        "communication", "description", "details", "remittance information", "remittance", "message",
        "mededeling", "mededelingen", "vrije mededeling", "omschrijving", "detail van de omzet", "bericht",
        "communication libre", "libelle", "description de l operation"],
    "direction": ["credit debit", "debit credit", "d c", "c d", "dc", "cd", "af bij", "bij af", "debet credit",
                  "credit debet", "sens"],
    "credit_amount": ["credit", "credit amount", "bij", "montant credit"],
    "debit_amount": ["debit", "debit amount", "debet", "af", "montant debit"],
    "collection_date": [
        "collection date", "requested collection date", "inningsdatum", "incassodatum", "datum inning",
        "date d encaissement", "date de prelevement", "date du prelevement"],
    "return_date": [
        "return date", "reject date", "rejection date", "date returned", "datum terugboeking", "terugboekingsdatum",
        "datum storno", "stornodatum", "weigeringsdatum", "date du retour", "date de retour", "date du rejet",
        "date de rejet"],
    "mandate_reference": [
        "mandate", "mandate reference", "mandate id", "mandate ref", "mandate number", "umr", "mandaat",
        "mandaatreferentie", "mandaatnummer", "mandaat id", "referentie mandaat", "machtigingskenmerk",
        "kenmerk machtiging", "mandat", "reference du mandat", "reference mandat", "numero de mandat", "id mandat"],
    "reason_code": [
        "reason code", "reason", "return code", "return reason", "reject code", "reject reason", "r code",
        "error code", "redencode", "reden", "reden code", "retourcode", "foutcode", "weigeringscode", "code motif",
        "motif", "code retour", "code de retour", "code rejet", "code du motif"],
    "scheme": ["scheme", "sdd scheme", "mandate type", "local instrument", "type", "schema", "type mandaat",
               "type de mandat"],
    "end_to_end_id": [
        "end to end id", "end to end reference", "endtoendid", "e2e", "e2e id", "end to end referentie",
        "eind tot eind referentie", "reference de bout en bout", "reference bout en bout"],
    "signature_date": [
        "signature date", "date signed", "signed on", "date of signature", "signing date", "ondertekeningsdatum",
        "datum ondertekening", "handtekeningdatum", "getekend op", "datum handtekening", "date de signature",
        "signe le", "date signature"],
    "signed": ["signed", "signature", "signature present", "has signature", "getekend", "ondertekend",
               "handtekening", "signe"],
    "last_collection_date": [
        "last collection", "last collection date", "last used", "last debit", "date of last collection",
        "laatste inning", "laatste incasso", "datum laatste inning", "laatst gebruikt", "laatste domiciliering",
        "dernier encaissement", "dernier prelevement", "date du dernier prelevement", "derniere utilisation"],
    "bank_confirmed": [
        "confirmed by debtor bank", "bank confirmed", "registered at bank", "registered", "confirmed",
        "debtor bank confirmation", "bevestigd door bank", "geregistreerd", "geregistreerd bij bank", "bevestigd",
        "confirme par la banque", "enregistre", "enregistre aupres de la banque", "confirme"],
}

SYNONYMS = {}
for _field, _names in _SYN.items():
    for _n in _names:
        key = norm_text(_n)
        if key in SYNONYMS and SYNONYMS[key] != _field:
            raise RuntimeError("header %r maps to two fields" % _n)
        SYNONYMS[key] = _field

GENERIC = {"date", "name", "iban", "status", "due_date", "customer_name", "debtor_name"}

# Column names that are known and always dropped (addresses, contact data, bank texts). Known names may be
# printed. Any other header is shown as "column N" because it might be a value, not a name.
DROP_KNOWN = {norm_text(n) for n in [
    "address", "adres", "adresse", "street", "straat", "rue", "city", "gemeente", "ville", "postal code", "postcode",
    "code postal", "zip", "country", "land", "pays", "e-mail", "email", "mail", "courriel", "e-mailadres",
    "phone", "telephone", "telefoon", "tel", "gsm", "mobile", "debtor address", "adres tegenpartij",
    "adres debiteur", "adresse du debiteur", "adresse contrepartie", "libelle motif", "reason text",
    "reason description", "omschrijving reden", "reden omschrijving", "vat number", "btw nummer", "btw-nummer",
    "numero de tva", "contact", "contactpersoon", "note", "notes", "opmerking", "remarque", "bic", "bic code"]}
SAFE_HEADERS = set(SYNONYMS) | DROP_KNOWN

# --------------------------------------------------------------------------- shapes (never values)

_IBAN_SHAPE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{8,30}$")
_EMAIL_SHAPE = re.compile(r"\S+@\S+\.\S+")
_OGM_SHAPE = re.compile(r"^[+*]{3}.*[+*]{3}$|^\d{3}/\d{4}/\d{5}$")
_NUMBER_SHAPE = re.compile(r"^[+-]?\(?(€|EUR)?[\d.,'  ]*\d[\d.,'  ]*(€|EUR)?\)?[+-]?$", re.I)
_CODE_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.\-]{0,19}$")


def cell_shape(value):
    """The kind of a cell, never its content: None for empty."""
    s = (value or "").strip()
    if not s:
        return None
    if _IBAN_SHAPE.match(re.sub(r"\s+", "", s).upper()):
        return "IBAN-like"
    if _EMAIL_SHAPE.search(s):
        return "e-mail-like"
    if _OGM_SHAPE.match(s):
        return "structured communication"
    for _name, rx in _DATE_PATTERNS:
        if rx.match(s):
            return "date"
    if _NUMBER_SHAPE.match(s):
        return "amount" if re.search(r"[.,]\d{1,2}\)?[+-]?$|[.,]\d{1,2}\s*(€|EUR)", s, re.I) else "number"
    if _CODE_SHAPE.match(s) and re.search(r"\d", s):
        return "code"
    return "text"


def column_shape(values):
    """Shape of a column from its values: "date", "amount", "IBAN-like", "text, 12 chars" and so on."""
    shapes = [(cell_shape(v), (v or "").strip()) for v in values[:60]]
    shapes = [(sh, v) for sh, v in shapes if sh]
    if not shapes:
        return "empty"
    kinds = [sh for sh, _ in shapes]
    top = max(sorted(set(kinds)), key=kinds.count)
    if top == "text":
        lengths = sorted(len(v) for sh, v in shapes if sh == "text")
        return "text, %d chars" % lengths[len(lengths) // 2]
    return top


def looks_like_value(cell):
    return cell_shape(cell) in ("IBAN-like", "e-mail-like", "structured communication", "date", "amount", "number")

# Generic and kind-dependent fields resolve per kind. Anything not listed is dropped.
RESOLVE = {
    "invoices": {"date": "invoice_date", "name": "customer_name", "debtor_name": "customer_name"},
    "bank": {"date": "booking_date", "name": "counterparty_name", "customer_name": "counterparty_name",
             "debtor_name": "counterparty_name"},
    "failed_collections": {"date": "collection_date", "due_date": "collection_date", "name": "debtor_name",
                           "customer_name": "debtor_name", "iban": "debtor_iban"},
    "mandates": {"name": "debtor_name", "customer_name": "debtor_name", "iban": "debtor_iban",
                 "status": "mandate_status"},
}

ALLOWED = {
    "invoices": ["invoice_number", "customer_number", "customer_name", "invoice_date", "due_date", "paid_date",
                 "amount", "open_amount", "currency", "status", "method", "structured_communication", "terms_days"],
    "bank": ["booking_date", "value_date", "amount", "credit_amount", "debit_amount", "direction", "currency",
             "counterparty_name", "counterparty_iban", "structured_communication", "communication", "own_account"],
    "failed_collections": ["collection_date", "return_date", "amount", "currency", "debtor_name", "customer_number",
                           "debtor_iban", "mandate_reference", "reason_code", "scheme", "end_to_end_id"],
    "mandates": ["mandate_reference", "customer_number", "debtor_name", "debtor_iban", "scheme", "signature_date",
                 "signed", "mandate_status", "last_collection_date", "bank_confirmed"],
}
# Read for one check only, never stored: the payer's text (does it name an open invoice) and the company's own
# account (to leave out transfers between its own accounts and to link a CSV and a camt.053 of one account).
READ_NOT_STORED = {"communication", "own_account"}

KINDS = sorted(ALLOWED)
MAP_TARGETS = sorted(set(f for fs in ALLOWED.values() for f in fs) | {"ignore"})

DATE_FIELDS = {"invoice_date", "due_date", "paid_date", "booking_date", "value_date", "collection_date",
               "return_date", "signature_date", "last_collection_date"}
AMOUNT_FIELDS = {"amount", "open_amount", "credit_amount", "debit_amount"}


def required_ok(kind, fields):
    f = set(fields)
    if kind == "invoices":
        missing = [x for x in ("invoice_number", "amount") if x not in f]
        if not f & {"invoice_date", "due_date"}:
            missing.append("invoice_date or due_date")
        if not f & {"customer_name", "customer_number"}:
            missing.append("customer_name or customer_number")
        # Without one of these X-ray cannot tell a paid invoice from an open one, and would count every
        # invoice as open and overdue.
        if not f & {"status", "paid_date", "open_amount"}:
            missing.append("status, paid_date or open_amount (to tell paid invoices from open ones)")
    elif kind == "bank":
        missing = []
        if not f & {"booking_date", "value_date"}:
            missing.append("booking_date")
        if "amount" not in f and not f & {"credit_amount", "debit_amount"}:
            missing.append("amount")
    elif kind == "failed_collections":
        missing = [x for x in ("amount", "reason_code") if x not in f]
        if not f & {"collection_date", "return_date"}:
            missing.append("collection_date or return_date")
    else:
        missing = [] if "mandate_reference" in f else ["mandate_reference"]
        if not f & {"debtor_name", "customer_number"}:
            missing.append("debtor_name or customer_number")
    return missing


def guess_kind(raw_fields):
    f = set(raw_fields)
    if "reason_code" in f:
        return "failed_collections"
    if "mandate_reference" in f and "amount" not in f and "invoice_number" not in f:
        return "mandates"
    if "invoice_number" in f:
        return "invoices"
    # A bank export needs a column that only bank exports have. A bare date and amount is not enough.
    if f & {"booking_date", "value_date", "counterparty_name", "counterparty_iban"} and \
            f & {"amount", "credit_amount", "debit_amount"}:
        return "bank"
    return None


# --------------------------------------------------------------------------- reading the file

def decode_bytes(data):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1"), "latin-1"


def sniff_delimiter(lines):
    best, best_score = ";", -1
    for d in (";", ",", "\t", "|"):
        rows = list(csv.reader(lines, delimiter=d))
        counts = [len(r) for r in rows if any(c.strip() for c in r)]
        counts = [c for c in counts if c >= 2]
        if not counts:
            continue
        mode = max(set(counts), key=counts.count)
        score = counts.count(mode) * 100 + mode
        if score > best_score:
            best, best_score = d, score
    return best


# --------------------------------------------------------------------------- values

_DATE_PATTERNS = [
    ("iso", re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ].*)?$")),
    ("ymd", re.compile(r"^(\d{4})(\d{2})(\d{2})$")),
    ("dmy", re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})(?:[ T].*)?$")),
]


def detect_date_format(values):
    """Return ('iso'|'ymd'|'dmy'|'mdy', assumption or None) for a column, or (None, reason)."""
    vals = [v.strip() for v in values if v and v.strip()]
    if not vals:
        return "iso", None
    kinds = set()
    first_big = second_big = False
    for v in vals:
        for name, rx in _DATE_PATTERNS:
            m = rx.match(v)
            if m:
                kinds.add(name)
                if name == "dmy":
                    a, b = int(m.group(1)), int(m.group(2))
                    first_big = first_big or a > 12
                    second_big = second_big or b > 12
                break
        else:
            kinds.add("bad")
    good = kinds - {"bad"}
    if len(good) != 1:
        return None, "mixed or unreadable date formats"
    k = good.pop()
    if k != "dmy":
        return k, None
    if first_big and second_big:
        return None, "day and month cannot be told apart"
    if second_big:
        return "mdy", None
    if not first_big:
        return "dmy", "dates read as day/month/year"
    return "dmy", None


def parse_date(value, fmt):
    v = (value or "").strip()
    if not v:
        return None
    try:
        if fmt == "iso":
            m = _DATE_PATTERNS[0][1].match(v)
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
        if fmt == "ymd":
            m = _DATE_PATTERNS[1][1].match(v)
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
        m = _DATE_PATTERNS[2][1].match(v)
        if not m:
            return None
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        return dt.date(y, b, a) if fmt == "dmy" else dt.date(y, a, b)
    except ValueError:
        return None


_CLEAN_AMOUNT = re.compile(r"[\s  €]|EUR|eur")


def detect_decimal_mark(values, delimiter):
    comma = dot = 0
    for v in values:
        s = _CLEAN_AMOUNT.sub("", v or "").strip("+-()")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                comma += 1
            else:
                dot += 1
        elif re.search(r"\d,\d{1,2}$", s):
            comma += 1
        elif re.search(r"\d\.\d{1,2}$", s):
            dot += 1
    if comma and dot:
        return None, "amounts use both a decimal comma and a decimal point"
    if comma:
        return ",", None
    if dot:
        return ".", None
    mark = "," if delimiter == ";" else "."
    return mark, "amounts have no decimals, read with a decimal %s" % ("comma" if mark == "," else "point")


def parse_amount(value, mark):
    s = _CLEAN_AMOUNT.sub("", value or "").replace("'", "")
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    s = s.lstrip("+")
    if mark == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    if not re.match(r"^\d+(\.\d+)?$", s):
        return None
    a = float(s)
    return -a if neg else a


_WORDS = {
    "status": {
        "paid": ["paid", "betaald", "voldaan", "paye", "payee", "regle", "reglee", "settled", "fully paid",
                 "volledig betaald", "afgehandeld"],
        "open": ["open", "openstaand", "unpaid", "onbetaald", "impaye", "impayee", "overdue", "vervallen", "due",
                 "outstanding", "ouvert", "ouverte", "en attente", "pending", "partially paid", "gedeeltelijk betaald",
                 "deels betaald", "partiellement paye", "partiellement payee", "te betalen", "a payer", "late",
                 "booked", "sent", "verzonden", "envoye"],
        "closed": ["cancelled", "canceled", "geannuleerd", "annule", "annulee", "credited", "gecrediteerd", "credite",
                   "void", "archived", "gearchiveerd", "written off", "afgeboekt", "oninbaar"],
    },
    "method": {
        "sdd": ["domiciliering", "direct debit", "sdd", "incasso", "automatische incasso", "domiciliation",
                "prelevement", "prelevement sepa", "sepa direct debit", "dd", "europese domiciliering"],
        "transfer": ["overschrijving", "transfer", "bank transfer", "credit transfer", "virement", "sct", "wire",
                     "virement bancaire"],
    },
    "scheme": {
        "CORE": ["core", "sdd core", "cor1", "sepa core", "core sdd"],
        "B2B": ["b2b", "sdd b2b", "sepa b2b", "business", "b2b sdd"],
    },
    "yesno": {
        True: ["yes", "y", "ja", "j", "oui", "o", "true", "1", "x", "ok", "signed", "getekend", "ondertekend", "signe",
               "confirmed", "bevestigd", "confirme", "registered", "geregistreerd", "enregistre"],
        False: ["no", "n", "nee", "non", "false", "0", "not signed", "niet getekend", "unsigned", "not confirmed",
                "niet bevestigd", "non confirme", "not registered", "niet geregistreerd", "non enregistre",
                "non signe"],
    },
    "mandate_status": {
        "active": ["active", "actief", "actif", "valid", "geldig", "ok", "signed", "getekend", "in use"],
        "cancelled": ["cancelled", "canceled", "geannuleerd", "annule", "revoked", "ingetrokken", "revoque",
                      "inactive", "inactief", "inactif", "closed", "gesloten", "expired", "vervallen", "expire",
                      "suspended", "opgeschort", "suspendu", "terminated", "beeindigd"],
    },
    "direction": {
        "credit": ["c", "cr", "crdt", "credit", "bij", "+", "in", "incoming"],
        "debit": ["d", "db", "dr", "dbit", "debit", "debet", "af", "-", "out", "outgoing"],
    },
}
_LOOKUP = {}
for _group, _vals in _WORDS.items():
    _LOOKUP[_group] = {}
    for _value, _words in _vals.items():
        for _w in _words:
            _LOOKUP[_group][norm_text(_w) or _w] = _value


def word(group, value):
    """Map a cell to a known value of the group. Returns (value, recognized)."""
    v = (value or "").strip()
    if not v:
        return None, True
    key = norm_text(v) or v
    if key in _LOOKUP[group]:
        return _LOOKUP[group][key], True
    return None, False


_CODE = re.compile(r"^\s*([A-Za-z0-9]{4})(?![A-Za-z0-9])")


def reason_code(value):
    """A reason cell -> (code, status). status: "ok", "empty" or "proprietary".

    Only a code on the allow-list (xray/reasons.py) is kept. Anything else, a first name such as
    "Anna" included, is a proprietary reason: its text is dropped and never shown.
    """
    v = (value or "").strip()
    if not v:
        return None, "empty"
    m = _CODE.match(v)
    if m and reasons.allowed(m.group(1)):
        return m.group(1).upper(), "ok"
    return None, "proprietary"


def terms_days(value):
    m = re.search(r"\d+", value or "")
    if not m:
        return None
    n = int(m.group(0))
    return n if 0 <= n <= 365 else None


# --------------------------------------------------------------------------- main entry

STATUS_UNKNOWN = "status unknown"

def read_csv(data, filename, user_map=None):
    """Parse one CSV export.

    user_map: {header text or "#N" (column position): field or "ignore", "@kind": kind} from
    `intake --map`. Returns a dict. status "ok" carries kind, rows (canonical fields with parsed
    values) and a column report. status "needs_mapping" carries "columns": position, a header only
    when it is a known column name, and the shape of the values. Never a cell value.
    """
    user_map = dict(user_map or {})
    text, encoding = decode_bytes(data)
    lines = [ln for ln in text.splitlines()]
    probe = [ln for ln in lines[:40] if ln.strip()]
    if not probe:
        return {"status": "empty", "file": filename}
    delim = sniff_delimiter(probe[:30])
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    nonempty = [r for r in rows if any(c.strip() for c in r)]

    forced_kind = user_map.pop("@kind", None)
    pos_map = {}
    for k in list(user_map):
        m = re.match(r"^\s*(?:#|column\s*)(\d+)\s*$", k, re.I)
        if m:
            pos_map[int(m.group(1)) - 1] = user_map.pop(k)
    umap = {norm_text(k): v for k, v in user_map.items()}

    def known(cell):
        return norm_text(cell) in umap or norm_text(cell) in SYNONYMS

    # Header row: the first of the first 30 rows with at least two known column names and no cell that
    # looks like a value. A preamble line ("Rekening;BE68...;Naam;...") or a data row is never a header.
    header_idx = None
    for i, r in enumerate(rows[:30]):
        if sum(1 for c in r if known(c)) >= 2 and not any(looks_like_value(c) for c in r):
            header_idx = i
            break
    if header_idx is None and pos_map:
        header_idx = -1  # no header row: the user mapped the columns by position
    if header_idx is None:
        width = max(set(len(r) for r in nonempty), key=[len(r) for r in nonempty].count)
        return {"status": "needs_mapping", "file": filename, "has_header": False,
                "columns": [{"position": i + 1, "header": None,
                             "values": column_shape([r[i] for r in nonempty[:60] if i < len(r)])}
                            for i in range(width)],
                "reason": "no header row with known column names in the first 30 lines"}
    if header_idx == -1:
        width = max(set(len(r) for r in nonempty), key=[len(r) for r in nonempty].count)
        headers = [""] * width
        body = nonempty
    else:
        headers = [c.strip() for c in rows[header_idx]]
        body = [r for r in rows[header_idx + 1:] if any(c.strip() for c in r)]

    def safe(i):
        h = headers[i] if i < len(headers) else ""
        return bool(h) and (norm_text(h) in SAFE_HEADERS or norm_text(h) in umap)

    def label(i):
        return headers[i] if safe(i) else "column %d" % (i + 1)

    def columns():
        return [{"position": i + 1, "header": headers[i] if safe(i) else None,
                 "values": column_shape([r[i] for r in body[:60] if i < len(r)])} for i in range(len(headers))]

    def blocked(reason, **extra):
        out = {"status": "needs_mapping", "file": filename, "has_header": header_idx != -1, "columns": columns(),
               "reason": reason}
        out.update(extra)
        return out

    raw = {}  # column index -> (raw field, priority)
    for idx, h in enumerate(headers):
        k = norm_text(h)
        if idx in pos_map:
            raw[idx] = (pos_map[idx], 4)
        elif k in umap:
            raw[idx] = (umap[k], 3)
        elif k in SYNONYMS:
            raw[idx] = (SYNONYMS[k], 1 if SYNONYMS[k] in GENERIC else 2)

    kind = forced_kind or guess_kind(f for f, _ in raw.values())
    if kind not in ALLOWED:
        return blocked("cannot tell what kind of export this is (invoices, bank, failed collections or mandates)")

    allowed = set(ALLOWED[kind])
    candidates = {}  # field -> [(priority, column index)]
    for idx, (f, prio) in raw.items():
        if f == "ignore":
            continue
        f = RESOLVE.get(kind, {}).get(f, f)
        if f in allowed:
            candidates.setdefault(f, []).append((prio, idx))
    chosen = {}
    for f, cands in candidates.items():
        top = max(p for p, _ in cands)
        best = [i for p, i in cands if p == top]
        if len(best) > 1:
            return blocked("more than one column could be %s: %s" % (f, ", ".join(label(i) for i in best)),
                           kind=kind)
        chosen[f] = (best[0], top)
    missing = required_ok(kind, chosen)
    if missing:
        return blocked("missing: %s" % ", ".join(missing), kind=kind)

    col = {f: idx for f, (idx, _) in chosen.items()}
    if header_idx == -1:  # no header row: only rows as wide as the file's usual row count are data
        data_rows = [r for r in body if len(r) == len(headers)]
    else:
        data_rows = body

    def cells(field):
        i = col[field]
        return [r[i] if i < len(r) else "" for r in data_rows]

    assumptions = []
    date_fmt = {}
    for f in DATE_FIELDS & set(col):
        fmt, note = detect_date_format(cells(f))
        if fmt is None:
            return blocked("%s: %s" % (label(col[f]), note), kind=kind)
        date_fmt[f] = fmt
        if note:
            assumptions.append("%s: %s" % (label(col[f]), note))
    marks = {}
    for f in AMOUNT_FIELDS & set(col):
        mark, note = detect_decimal_mark(cells(f), delim)
        if mark is None:
            return blocked("%s: %s" % (label(col[f]), note), kind=kind)
        marks[f] = mark
        if note:
            assumptions.append("%s: %s" % (label(col[f]), note))

    out, skipped, unknown_values = [], {}, {}

    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1

    for r in data_rows:
        def cell(field):
            i = col.get(field)
            return r[i].strip() if i is not None and i < len(r) else ""

        rec = {}
        bad = None
        for f in col:
            v = cell(f)
            if f in DATE_FIELDS:
                rec[f] = parse_date(v, date_fmt[f])
                if v and rec[f] is None:
                    bad = "date not readable"
            elif f in AMOUNT_FIELDS:
                rec[f] = parse_amount(v, marks[f])
                if v and rec[f] is None:
                    bad = "amount not readable"
            elif f in ("status", "method", "scheme", "signed", "bank_confirmed", "mandate_status", "direction"):
                group = {"signed": "yesno", "bank_confirmed": "yesno"}.get(f, f)
                rec[f], ok = word(group, v)
                if not ok:
                    unknown_values.setdefault(f, set()).add(v[:40])
            elif f == "reason_code":
                rec[f], rstatus = reason_code(v)
                rec["reason_proprietary"] = rstatus == "proprietary"
            elif f == "terms_days":
                rec[f] = terms_days(v)
            else:
                rec[f] = v or None
        if bad:
            skip(bad)
            continue
        if kind == "bank":
            if rec.get("amount") is None and ("credit_amount" in rec or "debit_amount" in rec):
                rec["amount"] = (rec.get("credit_amount") or 0) - abs(rec.get("debit_amount") or 0)
            if rec.get("direction") == "debit" and rec.get("amount") is not None:
                rec["amount"] = -abs(rec["amount"])
            if rec.get("amount") is None or not (rec.get("booking_date") or rec.get("value_date")):
                skip("no amount or date")
                continue
        elif kind == "invoices":
            if not rec.get("invoice_number") or rec.get("amount") is None:
                skip("no invoice number or amount")
                continue
            if not (rec.get("invoice_date") or rec.get("due_date")):
                skip("no invoice or due date")
                continue
            if not (rec.get("customer_name") or rec.get("customer_number")):
                skip("no customer")
                continue
            if not any(cell(f) for f in ("status", "paid_date", "open_amount")):
                # Nothing tells whether this invoice is paid: leave it out rather than count it as open.
                skip(STATUS_UNKNOWN)
                continue
        elif kind == "failed_collections":
            if rec.get("amount") is None or not (rec.get("collection_date") or rec.get("return_date")):
                skip("no amount or date")
                continue
        else:
            if not (rec.get("debtor_name") or rec.get("customer_number")):
                skip("no debtor")
                continue
        out.append(rec)

    total = len(data_rows)
    # Every row that could be read lacks all three. Rows left out for another reason get their own message below.
    if kind == "invoices" and skipped.get(STATUS_UNKNOWN, 0) and not out:
        return blocked("no row has a status, a paid date or an open amount, so paid invoices cannot be told from "
                       "open ones", kind=kind)
    n_skipped = sum(v for k, v in skipped.items() if k != STATUS_UNKNOWN)  # left out on purpose, shown apart
    if total and n_skipped >= 3 and n_skipped > total * 0.10:
        return blocked("%s of %s rows could not be read (%s)" % (
            num(n_skipped), num(total), ", ".join("%s: %s" % (k, num(v)) for k, v in sorted(skipped.items()))),
            kind=kind)
    if kind == "invoices" and "status" in unknown_values and not ({"paid_date", "open_amount"} & set(col)):
        return blocked("%s status values in %s are not recognized, and there is no paid date or open amount "
                       "column to tell paid from open" % (num(len(unknown_values["status"])), label(col["status"])),
                       kind=kind)
    if kind == "bank" and "direction" in unknown_values:
        # An unknown word in a debit/credit column could turn a payment out into a payment in.
        return blocked("%s values in %s are not recognized as money in or out (known: C, D, credit, debit, bij, af, "
                       "+, -)" % (num(len(unknown_values["direction"])), label(col["direction"])), kind=kind)

    used = {label(i): f for f, i in col.items()}
    return {
        "status": "ok", "file": filename, "format": "csv", "kind": kind, "encoding": encoding, "delimiter": delim,
        "rows": out, "rows_total": total, "skipped": skipped,
        "columns_kept": {h: f for h, f in used.items() if f not in READ_NOT_STORED},
        "read_not_stored": sorted(h for h, f in used.items() if f in READ_NOT_STORED),
        "columns_dropped": [label(i) for i, h in enumerate(headers) if (h or header_idx == -1)
                            and i not in col.values()],
        "assumptions": assumptions,
        "unknown_values": {f: len(v) for f, v in unknown_values.items()},
    }
