"""Intake: the only code that opens the raw exports.

It keeps a fixed list of fields per kind of export, drops payer free text, addresses, e-mail
addresses and phone numbers, and replaces names, customer numbers, IBANs, mandate references,
invoice numbers and payment references with stable codes:

  C001  customer or other party      M001  mandate reference
  A001  bank account (IBAN)          I0001 invoice number
  R0001 structured communication     E0001 end-to-end reference of a collection

The key that turns codes back into values is written next to the raw files, never into the
workspace. A structured communication's check digits are checked here, before it is coded: the
workspace keeps the result (ogm_status) and, for a bank line, the invoices that carry the same
communication (ogm_invoices). Free text is read for two things only (a valid structured
communication in it, and whether it names an open invoice number) and then dropped.

What the workspace holds besides codes: amounts, dates, counts, currency codes, Core or B2B,
reason codes from the allow-list, statuses from a fixed list (paid, open, active ...), file
numbers and known column names.

File names can hold names too, so files are shown as "file 1", "file 2" (in name order) and never
by name. The key keeps which file is which, for the report on the user's own computer.

Fail closed: when one file cannot be read with certainty, nothing is written and the result
describes that file's columns without a single cell value.
"""
import datetime as dt
import hashlib
import os
import re

from . import VERSION, csvparse, isoxml, ogm
from .common import (KEY_FILE, REPORT_PREFIX, XrayError, cents, cents_known, iso, natural_key, norm_name,
                     read_json, write_json)

MAX_FILE_BYTES = 200 * 1024 * 1024
PHASE = {"invoices": 1, "mandates": 2, "failed_collections": 3, "camt.054": 3, "pain.002": 3, "camt.053": 4,
         "bank": 4}


# --------------------------------------------------------------------------- the key

class Key:
    """Codes <-> values. Lives in the raw folder only."""

    def __init__(self, data=None):
        data = data or {}
        self.parties = data.get("parties", {})
        self.accounts = data.get("accounts", {})
        self.mandates = data.get("mandates", {})
        self.invoices = data.get("invoices", {})
        self.account_party = data.get("account_party", {})
        self.files = data.get("files", {})
        self.refs = data.get("refs", {})  # R0001: a structured communication (OGM), checked before it is coded
        self.e2e_ids = data.get("e2e", {})  # E0001: a collection's end-to-end reference
        self.by_number, self.by_name = {}, {}
        for code, p in self.parties.items():
            for n in p.get("numbers", []):
                self.by_number.setdefault(n, code)
            for n in p.get("norms", []):
                self.by_name.setdefault(n, code)
        self.by_iban = {v: k for k, v in self.accounts.items()}
        self.by_ref = {v: k for k, v in self.mandates.items() if v}
        self.by_invoice = {v: k for k, v in self.invoices.items()}
        self.by_value = {"R": {v: k for k, v in self.refs.items()}, "E": {v: k for k, v in self.e2e_ids.items()}}

    def to_json(self):
        return {"version": 1, "warning": "Twikey Payment X-ray key: turns codes back into names. Keep it next to "
                "your raw exports. Never share it or move it into the folder Claude works in.",
                "parties": self.parties, "accounts": self.accounts, "mandates": self.mandates,
                "invoices": self.invoices, "account_party": self.account_party, "files": self.files,
                "refs": self.refs, "e2e": self.e2e_ids}

    def _token(self, prefix, table, value):
        v = (value or "").strip()
        if not v:
            return None
        if v not in self.by_value[prefix]:
            code = self._next(prefix, table, 4)
            table[code] = v
            self.by_value[prefix][v] = code
        return self.by_value[prefix][v]

    def ref(self, value):
        """A payment reference -> R0001."""
        return self._token("R", self.refs, value)

    def e2e(self, value):
        """An end-to-end reference -> E0001."""
        return self._token("E", self.e2e_ids, value)

    @staticmethod
    def _next(prefix, used, width):
        n = len(used) + 1
        while "%s%0*d" % (prefix, width, n) in used:
            n += 1
        return "%s%0*d" % (prefix, width, n)

    def account(self, iban):
        v = re.sub(r"\s+", "", iban or "").upper()
        if not v:
            return None
        if v not in self.by_iban:
            code = self._next("A", self.accounts, 3)
            self.accounts[code] = v
            self.by_iban[v] = code
        return self.by_iban[v]

    def party(self, name=None, number=None, iban=None):
        number = (number or "").strip() or None
        norm = norm_name(name) if name else ""
        acct = self.account(iban) if iban else None
        code = None
        if number and number in self.by_number:
            code = self.by_number[number]
        elif acct and acct in self.account_party:
            code = self.account_party[acct]
        elif norm and norm in self.by_name:
            code = self.by_name[norm]
        if code is None:
            if not (number or norm or acct):
                return None
            code = self._next("C", self.parties, 3)
            self.parties[code] = {"name": (name or "").strip() or None, "numbers": [], "norms": []}
        p = self.parties[code]
        if not p.get("name") and name:
            p["name"] = name.strip()
        if number and number not in p["numbers"]:
            p["numbers"].append(number)
            self.by_number.setdefault(number, code)
        if norm and norm not in p["norms"]:
            p["norms"].append(norm)
            self.by_name.setdefault(norm, code)
        if acct and acct not in self.account_party:
            self.account_party[acct] = code
        return code

    def mandate(self, ref):
        r = (ref or "").strip()
        if not r:
            code = self._next("M", self.mandates, 3)
            self.mandates[code] = ""
            return code, True
        if r not in self.by_ref:
            code = self._next("M", self.mandates, 3)
            self.mandates[code] = r
            self.by_ref[r] = code
        return self.by_ref[r], False

    def invoice(self, number):
        v = (number or "").strip()
        if v not in self.by_invoice:
            code = self._next("I", self.invoices, 4)
            self.invoices[code] = v
            self.by_invoice[v] = code
        return self.by_invoice[v]


def load_key(raw_dir):
    return Key(read_json(os.path.join(raw_dir, KEY_FILE), {}))


def save_key(raw_dir, key):
    path = os.path.join(raw_dir, KEY_FILE)
    write_json(path, key.to_json())
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _ccy(value):
    """A currency code (three letters), or EUR. Nothing else from the cell is kept."""
    v = (value or "").strip().upper()
    return v if re.fullmatch(r"[A-Z]{3}", v) else "EUR"


# --------------------------------------------------------------------------- reading the folder

def is_ours(name):
    """The key, the reports and notes the plugin writes next to the exports. Case does not matter."""
    low = name.lower()
    return (low == KEY_FILE.lower() or low.startswith(REPORT_PREFIX.lower())
            or (low.endswith(".md") and low.startswith("twikey-xray")))


def raw_files(raw_dir):
    out = []
    for name in sorted(os.listdir(raw_dir), key=natural_key):
        path = os.path.join(raw_dir, name)
        if name.startswith(".") or is_ours(name) or not os.path.isfile(path):
            continue
        out.append(name)
    return out


def file_id(name):
    """A stable id for a file, so config.json never holds a file name."""
    return "f" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def resolve_file(raw_dir, ref):
    """'1', 'file 1', '#1' or the file's own name -> the file's id."""
    names = raw_files(raw_dir)
    s = (ref or "").strip()
    m = re.match(r"^(?:file\s*|#)?(\d+)$", s, re.I)
    if m:
        i = int(m.group(1))
        if 1 <= i <= len(names):
            return file_id(names[i - 1])
        raise XrayError("There is no file %d. The raw folder has %d files, numbered in name order." % (i, len(names)))
    for n in names:
        if n == s or n.lower() == s.lower():
            return file_id(n)
    if re.match(r"^f[0-9a-f]{12}$", s):
        return s
    raise XrayError("That file is not in the raw folder. Name the file by its number, for example 1 or \"file 1\".")


def parse_file(raw_dir, name, user_map):
    path = os.path.join(raw_dir, name)
    try:
        size = os.path.getsize(path)
        if size > MAX_FILE_BYTES:
            return {"status": "unsupported", "file": name, "reason": "file is larger than 200 MB", "lines": None}
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        # The error message would carry the file name, and file names can hold names.
        return {"status": "unsupported", "file": name, "reason": "could not be opened (check that it is not open in "
                "another program and that you may read it)", "lines": None}
    lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    why = isoxml.sniff_unsupported(data, name)
    low = name.lower()
    if why:
        res = {"status": "unsupported", "file": name, "reason": why}
    elif low.endswith(".xml") or data.lstrip()[:5] == b"<?xml":
        try:
            res = isoxml.read_xml(data, name)
        except Exception:  # noqa: BLE001 - never a traceback: it could show the name or a value
            res = {"status": "unsupported", "file": name, "reason": "could not be read as ISO 20022 XML"}
    elif low.endswith((".csv", ".txt", ".tsv")):
        try:
            res = csvparse.read_csv(data, name, user_map)
        except Exception:  # noqa: BLE001 - random bytes, NUL characters and the like
            res = {"status": "unsupported", "file": name, "reason": "could not be read as a CSV"}
    else:
        res = {"status": "unsupported", "file": name, "reason": "file type not read (use CSV or ISO 20022 XML)"}
    res["lines"] = lines
    return res


def describe(res):
    """'file 1 (camt.053, 312 lines)'. Never the file name."""
    fmt = res.get("format")
    if fmt == "csv" or (not fmt and res.get("status") == "needs_mapping"):
        what = "CSV" + (" %s" % res["kind"].replace("_", " ") if res.get("kind") else "")
        n = res.get("lines")
        count = "%d lines" % n if n is not None else ""
    else:
        what = fmt or ""
        n = res.get("entries")  # XML: entries (camt) or transactions (pain.002), not text lines
        count = ("%d %s" % (n, "entry" if n == 1 else "entries")) if n is not None else ""
    parts = [p for p in (what, count) if p]
    return "%s (%s)" % (res["file"], ", ".join(parts)) if parts else res["file"]


def phase_of(res):
    return PHASE.get(res.get("format") if res.get("format") != "csv" else res.get("kind"), 9)


# --------------------------------------------------------------------------- building the ledger

def _invoice_state(row):
    amount = row.get("amount") or 0.0
    if amount < 0:
        return "CREDITED", 0.0
    open_amt = row.get("open_amount")
    status = row.get("status")
    if status == "closed":
        return "CANCELLED", 0.0
    if open_amt is not None:
        return ("PAID", 0.0) if abs(open_amt) < 0.005 else ("BOOKED", open_amt)
    if status == "paid":
        return "PAID", 0.0
    if status == "open":
        return "BOOKED", amount
    if row.get("paid_date"):
        return "PAID", 0.0
    return "BOOKED", amount


def _iban(v):
    return re.sub(r"\s+", "", v or "").upper()


def run(raw_dir, cfg, maps=None, skip=None):
    """Read every file in the raw folder. Returns the summary; writes nothing when blocked."""
    if not raw_dir or not os.path.isdir(raw_dir):
        raise XrayError("Raw folder not found. Run `init --raw <folder>` first.")
    maps = maps or {}
    skip = set(skip or [])
    results, blocked, names = [], [], {}
    for i, name in enumerate(raw_files(raw_dir), 1):
        label, fid = "file %d" % i, file_id(name)
        names[label] = name
        if fid in skip:
            results.append({"status": "skipped", "file": label, "description": label})
            continue
        res = parse_file(raw_dir, name, maps.get(fid))
        res["file"] = label
        res["description"] = describe(res)
        results.append(res)
        if res["status"] in ("needs_mapping", "unsupported"):
            blocked.append(res)
    files = [{k: r.get(k) for k in ("file", "description", "status", "format", "kind", "reason", "columns",
                                    "has_header")} for r in results]
    if blocked:
        return {"status": "blocked", "files": files, "blocked": blocked, "version": VERSION}
    ok = sorted([r for r in results if r["status"] == "ok"], key=lambda r: (phase_of(r), natural_key(r["file"])))
    if not ok:
        raise XrayError("No readable exports in the raw folder.")

    key = load_key(raw_dir)
    key.files = names
    report = {"files": [], "totals": {}, "assumptions": []}
    invoices, inv_rows = {}, {}
    mandates, failed, collected, bank = [], [], [], []
    counts = {"debit_lines_skipped": 0, "duplicates_removed": 0, "invalid_structured_communications": 0,
              "other_references": 0, "own_transfers_skipped": 0}

    # The company's own accounts: from the camt statements and from the account column of bank CSVs.
    own = set()
    for res in ok:
        own |= {_iban(a) for a in res.get("own_accounts") or []}
        if res.get("format") == "csv" and res["kind"] == "bank":
            own |= {_iban(r.get("own_account")) for r in res["rows"] if r.get("own_account")}
    own.discard("")

    for res in ok:
        entry = {"file": res["file"], "description": res["description"], "format": res.get("format"),
                 "kind": res.get("kind"), "kept": 0, "skipped": dict(res.get("skipped") or {})}
        if res.get("format") == "csv":
            entry.update({"columns_kept": sorted(res["columns_kept"]), "columns_dropped": res["columns_dropped"],
                          "read_not_stored": res["read_not_stored"], "assumptions": res["assumptions"],
                          "encoding": res["encoding"], "delimiter": res["delimiter"]})
            kind = res["kind"]
            rows = res["rows"]
            if kind == "invoices":
                for row in rows:
                    code = key.invoice(row["invoice_number"])
                    cust = key.party(row.get("customer_name"), row.get("customer_number"))
                    inv_rows[code] = (row, res["file"], cust)
                    entry["kept"] += 1
            elif kind == "mandates":
                for row in rows:
                    mcode, missing = key.mandate(row.get("mandate_reference"))
                    mandates.append({
                        "mandate": mcode, "ref_missing": missing,
                        "customer": key.party(row.get("debtor_name"), row.get("customer_number"),
                                              row.get("debtor_iban")),
                        "account": key.account(row.get("debtor_iban")), "scheme": row.get("scheme"),
                        "signed_date": iso(row.get("signature_date")), "signed": row.get("signed"),
                        "status": row.get("mandate_status"),
                        "last_collection_date": iso(row.get("last_collection_date")),
                        "bank_confirmed": row.get("bank_confirmed"), "file": res["file"]})
                    entry["kept"] += 1
            elif kind == "failed_collections":
                for row in rows:
                    mcode = key.mandate(row["mandate_reference"])[0] if row.get("mandate_reference") else None
                    when = row.get("collection_date") or row.get("return_date")
                    failed.append({
                        "status": "failed", "date": when,
                        "date_kind": "collection" if row.get("collection_date") else "returned",
                        "amount": abs(row["amount"]), "currency": _ccy(row.get("currency")),
                        "customer": key.party(row.get("debtor_name"), row.get("customer_number"),
                                              row.get("debtor_iban")),
                        "mandate": mcode, "account": key.account(row.get("debtor_iban")),
                        "scheme": row.get("scheme"), "reason_code": row.get("reason_code"),
                        "reason_proprietary": bool(row.get("reason_proprietary")), "reason_missing": False,
                        "batch_count": 1, "e2e": key.e2e(row.get("end_to_end_id")), "source": "csv",
                        "file": res["file"]})
                    entry["kept"] += 1
            else:  # bank
                for row in rows:
                    if row["amount"] <= 0:
                        counts["debit_lines_skipped"] += row["amount"] < 0
                        continue
                    if _iban(row.get("counterparty_iban")) in own:
                        counts["own_transfers_skipped"] += 1
                        continue
                    bank.append(_bank_line(row, res["file"], "csv", key, counts))
                    entry["kept"] += 1
        else:
            entry["own_accounts"] = len(res.get("own_accounts") or [])
            for f in res["failed"]:
                mcode = key.mandate(f["mandate_reference"])[0] if f.get("mandate_reference") else None
                failed.append({
                    "status": "failed", "date": f["date"], "date_kind": f["date_kind"], "amount": f["amount"],
                    "currency": _ccy(f["currency"]),
                    "customer": key.party(f.get("debtor_name"), None, f.get("debtor_iban")),
                    "mandate": mcode, "account": key.account(f.get("debtor_iban")), "scheme": f.get("scheme"),
                    "reason_code": f.get("reason_code"), "reason_proprietary": bool(f.get("reason_proprietary")),
                    "reason_missing": bool(f.get("reason_missing")), "batch_count": f.get("batch_count", 1),
                    "e2e": key.e2e(f.get("end_to_end_id")), "source": res["format"], "file": res["file"]})
                entry["kept"] += 1
            for c in res["collected"]:
                mcode = key.mandate(c["mandate_reference"])[0] if c.get("mandate_reference") else None
                collected.append({
                    "status": "collected", "date": c["date"], "date_kind": "collection", "amount": c["amount"],
                    "currency": _ccy(c["currency"]),
                    "customer": key.party(c.get("debtor_name"), None, c.get("debtor_iban")),
                    "mandate": mcode, "account": key.account(c.get("debtor_iban")), "scheme": c.get("scheme"),
                    "reason_code": None, "batch_count": 1, "e2e": key.e2e(c.get("end_to_end_id")),
                    "source": res["format"], "file": res["file"]})
                entry["kept"] += 1
            for line in res["bank_lines"]:
                if _iban(line.get("counterparty_iban")) in own:
                    counts["own_transfers_skipped"] += 1
                    continue
                bank.append(_bank_line(line, res["file"], res["format"], key, counts))
                entry["kept"] += 1
            counts["debit_lines_skipped"] += res["skipped"].get("debit (payment out)", 0)
        report["files"].append(entry)
        for a in entry.get("assumptions") or []:
            report["assumptions"].append("%s: %s" % (res["file"], a))

    # Invoices: one record per invoice number. A later file overrides an earlier one.
    no_due = {}
    for code, (row, fname, cust) in inv_rows.items():
        state, open_amt = _invoice_state(row)
        terms = row.get("terms_days")
        inv_date, due = row.get("invoice_date"), row.get("due_date")
        if due is None and inv_date is not None:
            due = inv_date + dt.timedelta(days=terms if terms is not None else cfg.get("default_terms_days", 30))
            no_due[fname] = no_due.get(fname, 0) + 1
        if terms is None and inv_date and due:
            terms = (due - inv_date).days
        ogm_value, ogm_status = ogm.from_field(row.get("structured_communication"))
        pays = []
        if state == "PAID" and row.get("paid_date"):
            pays = [{"action": "paid", "method": row.get("method") or "other", "date": iso(row["paid_date"])}]
        invoices[code] = {
            "id": code, "number": code, "amount": round(abs(row["amount"]), 2), "date": iso(inv_date),
            "duedate": iso(due), "state": state,
            "customer": {"customerNumber": cust, "companyName": cust, "email": None, "l": None},
            "meta": {}, "lastpayment": pays, "url": None,
            # the structured communication is checked above, then kept only as a code (R0001)
            "xray": {"open_amount": round(open_amt, 2), "ogm": key.ref(ogm_value), "ogm_status": ogm_status,
                     "terms_days": terms, "method": row.get("method"), "paid_date": iso(row.get("paid_date")),
                     "file": fname}}
    for fname, n in sorted(no_due.items()):
        report["assumptions"].append("%s: %d invoices without a due date, set to invoice date + payment terms"
                                     % (fname, n))

    # Collections: drop copies of the same transaction from different files.
    def dedupe(items, keyf):
        seen, out = {}, []
        for it in items:
            k = keyf(it)
            if k in seen and seen[k] != it["file"]:
                counts["duplicates_removed"] += 1
                continue
            seen.setdefault(k, it["file"])
            out.append(it)
        return out

    failed = dedupe(failed, lambda f: (f["e2e"], f["reason_code"]) if f["e2e"] else
                    (f["mandate"], cents_known(f["amount"]), iso(f["date"]), f["reason_code"]))
    collected = dedupe(collected, lambda c: (c["e2e"],) if c["e2e"] else (c["mandate"], cents(c["amount"]), iso(c["date"])))
    by_e2e = {c["e2e"]: c for c in collected if c["e2e"]}
    for f in failed:
        if f["date_kind"] in ("booked", "returned") and f["e2e"] in by_e2e:
            f["date"], f["date_kind"] = by_e2e[f["e2e"]]["date"], "collection"
    scheme_of = {m["mandate"]: m["scheme"] for m in mandates if m.get("scheme")}
    for c in failed + collected:
        if not c.get("scheme") and c.get("mandate") in scheme_of:
            c["scheme"] = scheme_of[c["mandate"]]
    # The same account loaded twice (a bank CSV and a camt.053) holds the same payments: one copy counts.
    bank = dedupe(bank, lambda b: b.pop("_dedupe"))
    # The match on the structured communication, kept as invoice codes: which invoices carry the same one.
    by_ref = {}
    for c, inv in sorted(invoices.items()):
        if inv["xray"]["ogm"]:
            by_ref.setdefault(inv["xray"]["ogm"], []).append(c)
    for b in bank:
        b["ogm_invoices"] = by_ref.get(b["ogm"], []) if b["ogm"] else []

    # Free text: does it name an open invoice number? Only the boolean is kept.
    open_numbers = [key.invoices[c] for c, inv in invoices.items() if inv["state"] == "BOOKED"]
    rx = None
    nums = sorted({n for n in open_numbers if len(n) >= 4}, key=len, reverse=True)
    if nums:
        rx = re.compile(r"(?<![A-Za-z0-9])(%s)(?![A-Za-z0-9])" % "|".join(re.escape(n) for n in nums), re.I)
    for b in bank:
        text = b.pop("_text", "")
        b["mentions_open_invoice"] = bool(rx and text and rx.search(text))

    # Customers collected by direct debit: their invoices carry the mandate.
    dd_mandate = {}
    for c in sorted(collected, key=lambda c: (c["date"] or dt.date.min)):
        if c.get("customer") and c.get("mandate"):
            dd_mandate[c["customer"]] = c["mandate"]
    for inv in invoices.values():
        m = dd_mandate.get(inv["customer"]["customerNumber"])
        if m:
            inv["meta"] = {"mndtId": m}

    for i, b in enumerate(sorted(bank, key=lambda b: (b["date"] or dt.date.min, natural_key(b["file"]))), 1):
        b["id"] = "B%04d" % i
    for i, c in enumerate(sorted(failed + collected, key=lambda c: (c["date"] or dt.date.min, c["status"])), 1):
        c["id"] = "K%04d" % i

    def ser(items):
        out = []
        for it in items:
            it = dict(it)
            for k, v in list(it.items()):
                if isinstance(v, dt.date):
                    it[k] = v.isoformat()
            out.append(it)
        return out

    customers = {inv["customer"]["customerNumber"] for inv in invoices.values()}

    def period(items, field="date"):
        ds = [it[field] if isinstance(it[field], str) else iso(it[field]) for it in items if it.get(field)]
        return {"from": min(ds), "to": max(ds)} if ds else None

    report["periods"] = {"invoices": period(list(invoices.values())), "bank": period(bank),
                         "collections": period(collected), "failed_collections": period(failed)}
    report["totals"] = {
        "invoices": len(invoices), "parties": len(key.parties), "customers": len(customers),
        "other_parties": len(set(key.parties) - customers), "mandate_rows": len(mandates),
        "mandate_codes": len({m["mandate"] for m in mandates}), "bank_credit_lines": len(bank),
        "collections_collected": len(collected), "failed_collections": sum(f["batch_count"] for f in failed),
        "failed_amount_unknown": sum(f["batch_count"] for f in failed if f["amount"] is None),
        **counts}
    return {"status": "ok", "version": VERSION, "files": files, "key": key, "report": report,
            "store": {"invoices": invoices, "feed_position": None,
                      "synced_at": dt.datetime.now().isoformat(timespec="seconds"), "source": "xray-intake"},
            "mandates": ser(mandates), "collections": ser(sorted(failed + collected, key=lambda c: c["id"])),
            "bank": ser(sorted(bank, key=lambda b: b["id"]))}


def _bank_line(row, fname, source, key, counts):
    value, status = ogm.from_field(row.get("structured_communication"))
    free = row.get("communication") or ""
    if value is None and status in ("absent",):
        value, status = ogm.from_text(free)
    if status == "invalid":
        counts["invalid_structured_communications"] += 1
    elif status == "other":
        counts["other_references"] += 1
    when = row.get("booking_date") or row.get("value_date")
    line = {
        "id": None, "date": when, "value_date": row.get("value_date"), "amount": round(abs(row["amount"]), 2),
        "currency": _ccy(row.get("currency")),
        "customer": key.party(row.get("counterparty_name"), None, row.get("counterparty_iban")),
        # checked above (ogm_status), then kept only as a code (R0001)
        "account": key.account(row.get("counterparty_iban")), "ogm": key.ref(value), "ogm_status": status,
        "source": source, "file": fname, "_text": free,
        # Not the own account or the text: a CSV and a camt.053 of one account spell those differently.
        "_dedupe": (iso(when), cents(row["amount"]), _iban(row.get("counterparty_iban")), value or "")}
    return line


def write(home, raw_dir, result):
    """Write the coded ledger to the workspace and the key to the raw folder."""
    save_key(raw_dir, result["key"])
    write_json(os.path.join(home, "store.json"), result["store"])
    write_json(os.path.join(home, "mandates.json"), result["mandates"])
    write_json(os.path.join(home, "collections.json"), result["collections"])
    write_json(os.path.join(home, "bank.json"), result["bank"])
    write_json(os.path.join(home, "intake.json"), {"version": VERSION, "files": result["report"]["files"],
                                                   "totals": result["report"]["totals"],
                                                   "periods": result["report"]["periods"],
                                                   "assumptions": result["report"]["assumptions"],
                                                   "at": dt.datetime.now().isoformat(timespec="seconds")})
