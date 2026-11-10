"""Intake: the only code that opens the raw exports, the camt.053 bank statements.

It keeps a fixed list of fields, drops payer free text and addresses, and replaces names, IBANs, mandate
references and payment references with stable codes:

  C001  customer or other party      M001  mandate reference
  A001  bank account (IBAN)          R0001 structured communication
  E0001 end-to-end reference of a collection

The key that turns codes back into values is written next to the raw files, never into the workspace. A
structured communication's check digits are checked here, before it is coded: the workspace keeps the result
(ogm_status). Free text is read for one thing only (a valid structured communication in it) and then dropped.

What the workspace holds besides codes: amounts, dates, counts, currency codes, Core or B2B, reason codes from the
allow-list and file numbers.

File names can hold names too, so files are shown as "file 1", "file 2" (in name order) and never by name. The key
keeps which file is which, for the report on the user's own computer. A file that is not a camt.053 statement is
skipped and named by its number only.
"""
import datetime as dt
import os
import re

from . import VERSION, camt053, ogm
from .common import (KEY_FILE, REPORT_PREFIX, XrayError, cents, iso, natural_key, norm_name, read_json,
                     write_json)

MAX_FILE_BYTES = 200 * 1024 * 1024
# Why a file was skipped (the reason keys intake prints, see cli_text.TEXT "skip_<reason>").
TOO_LARGE = "too_large"
UNREADABLE = "unreadable"
# The shape of the coded ledger. A workspace written with another number is read again before any check runs.
LEDGER_FORMAT = 1


# --------------------------------------------------------------------------- the key

class Key:
    """Codes <-> values. Lives in the raw folder only."""

    def __init__(self, data=None):
        data = data or {}
        self.parties = data.get("parties", {})
        self.accounts = data.get("accounts", {})
        self.mandates = data.get("mandates", {})
        self.account_party = data.get("account_party", {})
        self.files = data.get("files", {})
        self.refs = data.get("refs", {})  # R0001: a structured communication (OGM), checked before it is coded
        self.e2e_ids = data.get("e2e", {})  # E0001: a collection's end-to-end reference
        self.by_name = {}
        for code, p in self.parties.items():
            for n in p.get("norms", []):
                self.by_name.setdefault(n, code)
        self.by_iban = {v: k for k, v in self.accounts.items()}
        self.by_ref = {v: k for k, v in self.mandates.items() if v}
        self.by_value = {"R": {v: k for k, v in self.refs.items()}, "E": {v: k for k, v in self.e2e_ids.items()}}

    def to_json(self):
        return {"version": 2, "warning": "Twikey Payment X-ray key: turns codes back into names. Keep it next to "
                "your raw exports. Never share it or move it into the folder Claude works in.",
                "parties": self.parties, "accounts": self.accounts, "mandates": self.mandates,
                "account_party": self.account_party, "files": self.files, "refs": self.refs, "e2e": self.e2e_ids}

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

    def party(self, name=None, iban=None):
        """A party by account first, else by its name without case, accents or legal form."""
        norm = norm_name(name) if name else ""
        acct = self.account(iban) if iban else None
        code = None
        if acct and acct in self.account_party:
            code = self.account_party[acct]
        elif norm and norm in self.by_name:
            code = self.by_name[norm]
        if code is None:
            if not (norm or acct):
                return None
            code = self._next("C", self.parties, 3)
            self.parties[code] = {"name": (name or "").strip() or None, "norms": []}
        p = self.parties[code]
        if not p.get("name") and name:
            p["name"] = name.strip()
        if norm and norm not in p["norms"]:
            p["norms"].append(norm)
            self.by_name.setdefault(norm, code)
        if acct and acct not in self.account_party:
            self.account_party[acct] = code
        return code

    def mandate(self, ref):
        r = (ref or "").strip()
        if not r:
            return None
        if r not in self.by_ref:
            code = self._next("M", self.mandates, 3)
            self.mandates[code] = r
            self.by_ref[r] = code
        return self.by_ref[r]


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
    """A currency code (three letters), or EUR. Nothing else from the field is kept."""
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


def parse_file(raw_dir, name):
    path = os.path.join(raw_dir, name)
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return {"status": "skipped", "file": name, "reason": TOO_LARGE}
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        # The error message would carry the file name, and file names can hold names.
        return {"status": "skipped", "file": name, "reason": UNREADABLE}
    # A byte order mark or blank lines before the XML declaration: the parser wants "<" first.
    body = (data[3:] if data.startswith(b"\xef\xbb\xbf") else data).lstrip(b" \t\r\n")
    if body[:1] != b"<":
        return {"status": "skipped", "file": name, "reason": camt053.NOT_CAMT053}
    try:
        return camt053.read_xml(body, name)
    except Exception:  # noqa: BLE001 - never a traceback: it could show the name or a value
        return {"status": "skipped", "file": name, "reason": camt053.NOT_CAMT053}


def describe(res):
    """'file 1 (camt.053, 312 entries)'. Never the file name."""
    if res.get("status") != "ok":
        return res["file"]
    n = res.get("entries") or 0
    return "%s (camt.053, %d %s)" % (res["file"], n, "entry" if n == 1 else "entries")


# --------------------------------------------------------------------------- building the ledger

def _iban(v):
    return re.sub(r"\s+", "", v or "").upper()


def run(raw_dir, cfg=None):
    """Read every file in the raw folder. A file that is not a camt.053 statement is skipped. Returns the summary;
    raises when no file is a camt.053 statement (then nothing is written)."""
    if not raw_dir or not os.path.isdir(raw_dir):
        raise XrayError("Raw folder not found. Run `init --raw <folder>` first.")
    results, names = [], {}
    for i, name in enumerate(raw_files(raw_dir), 1):
        label = "file %d" % i
        names[label] = name
        res = parse_file(raw_dir, name)
        res["file"] = label
        res["description"] = describe(res)
        results.append(res)
    files = [{k: r.get(k) for k in ("file", "description", "status", "format", "reason")} for r in results]
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        raise XrayError("No camt.053 bank statement in the raw folder. Export your camt.053 statements from your "
                        "bank, put them in the raw folder and run intake again.")

    key = load_key(raw_dir)
    key.files = names
    report = {"files": []}
    failed, collected, bank = [], [], []
    counts = {"debit_lines_skipped": 0, "duplicates_removed": 0, "invalid_structured_communications": 0,
              "other_references": 0, "own_transfers_skipped": 0}

    # The company's own accounts: the accounts of the statements read.
    own = set()
    for res in ok:
        own |= {_iban(a) for a in res.get("own_accounts") or []}
    own.discard("")

    for res in ok:
        entry = {"file": res["file"], "description": res["description"], "format": res["format"], "kept": 0,
                 "entries": res.get("entries"), "own_accounts": len(res.get("own_accounts") or []),
                 "skipped": dict(res.get("skipped") or {})}
        # Collections first, so the direct debit customers get the first codes.
        for c in res["collected"]:
            collected.append({
                "status": "collected", "date": c["date"], "date_kind": "collection", "amount": c["amount"],
                "currency": _ccy(c["currency"]), "customer": key.party(c.get("debtor_name"), c.get("debtor_iban")),
                "mandate": key.mandate(c.get("mandate_reference")), "account": key.account(c.get("debtor_iban")),
                "scheme": c.get("scheme"), "reason_code": None, "e2e": key.e2e(c.get("end_to_end_id")),
                "file": res["file"]})
            entry["kept"] += 1
        for f in res["failed"]:
            failed.append({
                "status": "failed", "date": f["date"], "date_kind": f["date_kind"], "amount": f["amount"],
                "currency": _ccy(f["currency"]), "customer": key.party(f.get("debtor_name"), f.get("debtor_iban")),
                "mandate": key.mandate(f.get("mandate_reference")), "account": key.account(f.get("debtor_iban")),
                "scheme": f.get("scheme"), "reason_code": f.get("reason_code"),
                "reason_proprietary": bool(f.get("reason_proprietary")),
                "reason_missing": bool(f.get("reason_missing")), "e2e": key.e2e(f.get("end_to_end_id")),
                "file": res["file"]})
            entry["kept"] += 1
        for line in res["bank_lines"]:
            if _iban(line.get("counterparty_iban")) in own:
                counts["own_transfers_skipped"] += 1
                continue
            bank.append(_bank_line(line, res["file"], key, counts))
            entry["kept"] += 1
        counts["debit_lines_skipped"] += res["skipped"].get("debit (payment out)", 0)
        report["files"].append(entry)

    # The same statement in two files (two exports that overlap): one copy counts. A collection presented again
    # with the same end-to-end reference is another transaction: the keys hold the date and the amount too, and a
    # return its booking date (before it takes the date of its collection below).
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

    failed = dedupe(failed, lambda f: (f["e2e"], f["reason_code"], iso(f["date"]), cents(f["amount"])) if f["e2e"]
                    else (f["mandate"], cents(f["amount"]), iso(f["date"]), f["reason_code"]))
    collected = dedupe(collected, lambda c: (c["e2e"], iso(c["date"]), cents(c["amount"])) if c["e2e"] else
                       (c["mandate"], cents(c["amount"]), iso(c["date"])))
    bank = dedupe(bank, lambda b: b.pop("_dedupe"))
    # A return carries the end-to-end reference of the collection it returns: it takes the date of the latest
    # collection with that reference on or before the day the return was booked.
    by_e2e = {}
    for c in collected:
        if c["e2e"] and c["date"]:
            by_e2e.setdefault(c["e2e"], []).append(c["date"])
    for f in failed:
        dates = [d for d in by_e2e.get(f["e2e"], []) if not f["date"] or d <= f["date"]]
        if dates:
            f["date"], f["date_kind"] = max(dates), "collection"
    # Core or B2B: a return's bank code seldom says it, the collections on the same mandate do.
    scheme_of = {c["mandate"]: c["scheme"] for c in collected if c.get("mandate") and c.get("scheme")}
    for f in failed:
        if not f.get("scheme") and f.get("mandate") in scheme_of:
            f["scheme"] = scheme_of[f["mandate"]]

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

    def period(items):
        ds = [iso(it["date"]) if not isinstance(it["date"], str) else it["date"] for it in items if it.get("date")]
        return {"from": min(ds), "to": max(ds)} if ds else None

    dd_customers = {c["customer"] for c in failed + collected if c.get("customer")}
    payers = {b["customer"] for b in bank if b.get("customer")} - dd_customers
    report["periods"] = {"bank": period(bank), "collections": period(collected), "failed_collections": period(failed)}
    report["totals"] = {
        "statements": len(ok), "entries": sum(r.get("entries") or 0 for r in ok),
        # the parties of this ledger: the key keeps every code it ever gave, also for files since removed
        "parties": len(dd_customers | payers),
        "direct_debit_customers": len(dd_customers),
        "payers": len(payers),
        "mandate_codes": len({c["mandate"] for c in failed + collected if c.get("mandate")}),
        "bank_credit_lines": len(bank), "collections_collected": len(collected), "failed_collections": len(failed),
        **counts}
    return {"status": "ok", "version": VERSION, "files": files, "key": key, "report": report,
            "collections": ser(sorted(failed + collected, key=lambda c: c["id"])),
            "bank": ser(sorted(bank, key=lambda b: b["id"]))}


def _bank_line(row, fname, key, counts):
    value, status = ogm.from_field(row.get("structured_communication"))
    if value is None and status == "absent":
        value, status = ogm.from_text(row.get("communication") or "")
    if status == "invalid":
        counts["invalid_structured_communications"] += 1
    elif status == "other":
        counts["other_references"] += 1
    when = row.get("booking_date") or row.get("value_date")
    return {
        "id": None, "date": when, "value_date": row.get("value_date"), "amount": round(abs(row["amount"]), 2),
        "currency": _ccy(row.get("currency")),
        "customer": key.party(row.get("counterparty_name"), row.get("counterparty_iban")),
        # checked above (ogm_status), then kept only as a code (R0001)
        "account": key.account(row.get("counterparty_iban")), "ogm": key.ref(value), "ogm_status": status,
        "file": fname, "_dedupe": (iso(when), cents(row["amount"]), _iban(row.get("counterparty_iban")), value or "")}


def write(home, raw_dir, result):
    """Write the coded ledger to the workspace and the key to the raw folder."""
    save_key(raw_dir, result["key"])
    write_json(os.path.join(home, "collections.json"), result["collections"])
    write_json(os.path.join(home, "bank.json"), result["bank"])
    write_json(os.path.join(home, "intake.json"), {"version": VERSION, "ledger_format": LEDGER_FORMAT,
                                                   "files": result["report"]["files"],
                                                   "skipped_files": [f["file"] for f in result["files"]
                                                                     if f["status"] != "ok"],
                                                   "totals": result["report"]["totals"],
                                                   "periods": result["report"]["periods"],
                                                   "at": dt.datetime.now().isoformat(timespec="seconds")})
