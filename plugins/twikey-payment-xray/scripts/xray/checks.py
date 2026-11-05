"""The checks. Each takes the coded ledger and returns a JSON-ready dict with codes, counts, amounts
and dates only. No check opens a raw file."""
import copy
import datetime as dt
import itertools
import json
import os

from . import VERSION, calc, claims, reasons
from .common import (DATA_DIR, add_months, cents, cents_known, euros, months_spanned, parse_iso, working_day)

LANGS = ("en", "nl", "fr")


def _lang(lang):
    return lang if lang in LANGS else "en"


# --------------------------------------------------------------------------- which exports were read

# What each check needs, and the line it prints when that export is missing. Not checked is never "none".
SOURCES = ("invoices", "failures", "mandates", "bank")
NOT_CHECKED = {
    "en": {"invoices": "Not checked: no invoice list in your exports.",
           "failures": "Not checked: no file with failed collections in your exports (a pain.002, a camt.053 or "
                       "camt.054 statement, or a failed-collections export).",
           "mandates": "Not checked: no mandate list in your exports.",
           "bank": "Not checked: no bank statement in your exports."},
    "nl": {"invoices": "Niet nagekeken: geen factuurlijst in je exports.",
           "failures": "Niet nagekeken: geen bestand met mislukte domiciliëringen in je exports (een pain.002, een "
                       "camt.053- of camt.054-afschrift of een export van mislukte domiciliëringen).",
           "mandates": "Niet nagekeken: geen mandatenlijst in je exports.",
           "bank": "Niet nagekeken: geen bankafschrift in je exports."},
    "fr": {"invoices": "Non vérifié : aucune liste de factures dans vos exports.",
           "failures": "Non vérifié : aucun fichier de prélèvements échoués dans vos exports (un pain.002, un "
                       "relevé camt.053 ou camt.054, ou un export des prélèvements échoués).",
           "mandates": "Non vérifié : aucune liste de mandats dans vos exports.",
           "bank": "Non vérifié : aucun relevé bancaire dans vos exports."},
}


def sources(files=None, store=None, mandates=None, collections=None, bank=None):
    """Which exports the ledger holds: from the file kinds intake recorded (intake.json), else from the ledger."""
    if files:
        kinds = {f.get("kind") if f.get("format") == "csv" else f.get("format") for f in files}
        return {"invoices": "invoices" in kinds,
                "failures": bool(kinds & {"failed_collections", "pain.002", "camt.054", "camt.053"}),
                "mandates": "mandates" in kinds, "bank": bool(kinds & {"bank", "camt.053"})}
    return {"invoices": bool(store and store.get("invoices")), "failures": bool(collections),
            "mandates": bool(mandates), "bank": bool(bank)}


def not_checked(source, lang="en"):
    return NOT_CHECKED[_lang(lang)][source]


# --------------------------------------------------------------------------- reason codes

# What the reason code points to. Our classification of Twikey's reason-code texts (the RES field of
# data/rcodes_*.json), plus ED05 from the EPC list (settlement failed: a question for the bank).
ACTION = {
    "AM04": "new_attempt", "MS03": "new_attempt",
    "AC04": "new_mandate", "MD02": "new_mandate", "AC13": "new_mandate",
    "MD06": "conversation", "MS02": "conversation", "AC01": "conversation", "AC06": "conversation",
    "AG01": "conversation", "SL01": "conversation", "DNOR": "conversation", "RC01": "conversation",
    "MD07": "conversation", "PY01": "conversation",
    "AG02": "own_setup", "AM05": "own_setup", "BE05": "own_setup", "FF01": "own_setup", "RR01": "own_setup",
    "RR02": "own_setup", "RR03": "own_setup",
    "CNOR": "bank", "RR04": "bank", "ED05": "bank",
}
# Codes whose Twikey text (the RES field) says a B2B mandate is not registered at the debtor's bank: on a B2B
# mandate the customer asks their bank to register it (month.py, reason b2b_register).
B2B_REGISTER_CODES = ("MD01",)
CATEGORY_TEXTS = {
    "en": {
        "new_attempt": "Worth a new attempt: the reason code points to a problem that can pass, such as too "
                       "little money on the account.",
        "new_mandate": "Needs a new or amended mandate before the next collection.",
        "conversation": "Needs a conversation with the customer (a refund, a refusal, an account that cannot be "
                        "debited, or a B2B mandate the customer has not registered at their bank).",
        "own_setup": "Points to your own collection file or setup, fix it before the next run.",
        "bank": "Ask your bank.",
        "unknown": "Unknown code: neither on Twikey's reason-code page nor in the EPC list. Ask your bank what it "
                   "means.",
        "unreadable": "No usable reason code for these (not in the file, or a bank text that is not shown). "
                      "Ask your bank.",
    },
    "nl": {
        "new_attempt": "Heraanbieden waard: de redencode wijst op een probleem dat kan overgaan, zoals te weinig "
                       "saldo op de rekening.",
        "new_mandate": "Vraagt een nieuw of aangepast mandaat voor de volgende domiciliëring.",
        "conversation": "Vraagt een gesprek met de klant (een terugbetaling, een weigering, een rekening die niet "
                        "gedebiteerd kan worden, of een B2B-mandaat dat de klant niet bij zijn bank liet "
                        "registreren).",
        "own_setup": "Wijst op je eigen domiciliëringsbestand of instellingen, pas dat aan voor de volgende reeks "
                     "domiciliëringen.",
        "bank": "Vraag het aan je bank.",
        "unknown": "Onbekende code: niet op de redencodepagina van Twikey en niet in de EPC-lijst. Vraag je bank "
                   "wat ze betekent.",
        "unreadable": "Geen bruikbare redencode (niet in het bestand, of een banktekst die niet getoond wordt). "
                      "Vraag het aan je bank.",
    },
    "fr": {
        "new_attempt": "À présenter à nouveau : le code motif indique un problème passager, comme un solde "
                       "insuffisant sur le compte.",
        "new_mandate": "Demande un nouveau mandat ou un mandat modifié avant le prochain prélèvement.",
        "conversation": "Demande un échange avec le client (un remboursement, un refus, un compte qui ne peut pas "
                        "être débité, ou un mandat B2B que le client n'a pas fait enregistrer auprès de sa banque).",
        "own_setup": "Indique un problème dans votre propre fichier de prélèvement ou votre paramétrage, à corriger "
                     "avant la prochaine série de prélèvements.",
        "bank": "Demandez à votre banque.",
        "unknown": "Code inconnu : ni sur la page des codes motif de Twikey, ni dans la liste de l'EPC. Demandez à "
                   "votre banque ce qu'il signifie.",
        "unreadable": "Pas de code motif utilisable (absent du fichier, ou un texte de la banque qui n'est pas "
                      "affiché). Demandez à votre banque.",
    },
}
CATEGORY_TEXT = CATEGORY_TEXTS["en"]
LABELS = {
    "en": {"unknown": "unknown code", "proprietary": "proprietary reason (not shown)", "missing": "reason not in file"},
    "nl": {"unknown": "onbekende code", "proprietary": "eigen reden van de bank (niet getoond)",
           "missing": "reden niet in het bestand"},
    "fr": {"unknown": "code inconnu", "proprietary": "motif propre à la banque (non affiché)",
           "missing": "motif absent du fichier"},
}
UNKNOWN_CODE = LABELS["en"]["unknown"]
PROPRIETARY_LABEL = LABELS["en"]["proprietary"]
MISSING_LABEL = LABELS["en"]["missing"]
# Twikey's reason-code pages per language (Belgian Dutch and French pages for nl and fr).
RCODE_PAGE = {"en": "https://www.twikey.com/product/r-codes/%s.html",
              "nl": "https://www.twikey.com/be/product/r-codes/%s.html",
              "fr": "https://www.twikey.com/fr/product/r-codes/%s.html"}
CATEGORIES = ["new_attempt", "new_mandate", "conversation", "own_setup", "bank", "unknown", "unreadable"]


def _clean(s):
    """Twikey's codes_*.json has stray quotes and line breaks in some values. Clean them for display only."""
    s = " ".join((s or "").split())
    s = s.strip().strip('"').strip()
    return s.replace('""', '"')


def rcodes(lang="en"):
    lang = lang if lang in ("en", "nl", "fr") else "en"
    with open(os.path.join(DATA_DIR, "rcodes_%s.json" % lang), encoding="utf-8") as f:
        return {r["CODE"].strip(): r for r in json.load(f)}


def category(code, scheme, known_codes):
    if not code:
        return "unreadable"
    if code == "MD01":
        return "conversation" if scheme == "B2B" else "new_mandate"
    if code not in known_codes and code not in reasons.EPC_SDD:
        return "unknown"
    return ACTION.get(code, "unknown")


# A new presentation on the same mandate for the same amount comes within three weeks. A month later, a collection
# of the same amount is the next invoice.
RETRY_WINDOW_DAYS = 21
# A run moved by a weekend or bank holiday lands at most three days after its usual day.
SHIFT_DAYS = 3
# A collection day counts for the suggested day only with this many presentations over this many months.
DAY_MIN_PRESENTED = 20
DAY_MIN_MONTHS = 2


def same_debt(earlier, later):
    """True when `later` (collected or failed) presents the failed collection `earlier` again: the same end-to-end
    reference, or the same mandate and amount within RETRY_WINDOW_DAYS. The original presentation of a return has
    the same date, so it is never later."""
    d0, d1 = parse_iso(earlier.get("date")), parse_iso(later.get("date"))
    if not d0 or not d1 or d1 <= d0:
        return False
    if earlier.get("e2e") and later.get("e2e") == earlier["e2e"]:
        return True
    return (bool(earlier.get("mandate")) and later.get("mandate") == earlier["mandate"]
            and earlier.get("amount") is not None and later.get("amount") is not None
            and cents(later["amount"]) == cents(earlier["amount"]) and (d1 - d0).days <= RETRY_WINDOW_DAYS)


def day_stats(collections):
    """Failure rate per usual collection day of the month: failed collections against collections presented.

    Only months in which the ledger holds successful collections count (the bank statements show what was
    presented). A presentation that succeeded and was later returned counts once. A new presentation of a failed
    collection (same_debt) is left out: it is a retry, not the usual run. A run moved by a weekend or bank holiday
    counts under its usual day: a run on the first working day after a closed day D (at most SHIFT_DAYS after it)
    counts as D when other months have runs on day D. `qualifies`: DAY_MIN_PRESENTED presentations or more over
    DAY_MIN_MONTHS months or more.
    """
    dated = [c for c in collections if parse_iso(c.get("date"))]
    collected = [c for c in dated if c["status"] == "collected"]
    failed = [c for c in dated if c["status"] == "failed" and c.get("date_kind") == "collection"]
    months = {(d.year, d.month) for d in (parse_iso(c["date"]) for c in collected)}
    by_mandate, by_e2e = {}, {}
    for f in failed:
        if f.get("mandate"):
            by_mandate.setdefault(f["mandate"], []).append(f)
        if f.get("e2e"):
            by_e2e.setdefault(f["e2e"], []).append(f)

    def retry(p):
        earlier = by_mandate.get(p.get("mandate"), []) + by_e2e.get(p.get("e2e"), [])
        return any(same_debt(f, p) for f in earlier)

    # A return: collected, then failed with the same end-to-end reference and collection date. It was presented once.
    seen = {(c["e2e"], c["date"]) for c in collected if c.get("e2e")}

    def returned(f):
        return bool(f.get("e2e")) and (f["e2e"], f["date"]) in seen

    pres, retries = [], 0  # (date, presented, failed)
    for c in collected:
        if retry(c):
            retries += 1
        else:
            pres.append((parse_iso(c["date"]), 1, 0))
    for f in failed:
        d = parse_iso(f["date"])
        if (d.year, d.month) not in months:
            continue
        n = int(f.get("batch_count") or 1)
        if retry(f):
            retries += 0 if returned(f) else n
            continue
        pres.append((d, 0 if returned(f) else n, n))

    exact = {}
    for d, _, _ in pres:
        exact.setdefault(d.day, set()).add((d.year, d.month))

    def usual(d):
        best, best_n = d.day, len(exact.get(d.day, set()) - {(d.year, d.month)})
        for k in range(1, SHIFT_DAYS + 1):
            e = d - dt.timedelta(days=k)
            if working_day(e) != d:
                break
            n = len(exact.get(e.day, set()) - {(d.year, d.month)})
            if n > best_n:
                best, best_n = e.day, n
        return best

    usual_of = {d: usual(d) for d in {p[0] for p in pres}}
    days, total_p, total_x = {}, 0, 0
    for d, p, x in pres:
        s = days.setdefault(usual_of[d], {"presented": 0, "failed": 0, "months": set(), "moved": set()})
        s["presented"] += p
        s["failed"] += x
        s["months"].add((d.year, d.month))
        if usual_of[d] != d.day:
            s["moved"].add((d.year, d.month))
        total_p += p
        total_x += x
    rows = {}
    for day in sorted(days):
        s = days[day]
        rows[str(day)] = {"failed": s["failed"], "presented": s["presented"], "months": len(s["months"]),
                          "rate_pct": round(100.0 * s["failed"] / s["presented"], 1) if s["presented"] else None,
                          "moved_runs": len(s["moved"]),
                          "qualifies": s["presented"] >= DAY_MIN_PRESENTED and len(s["months"]) >= DAY_MIN_MONTHS}
    covered = sorted(months)
    return {"days": rows,
            "overall": {"failed": total_x, "presented": total_p,
                        "rate_pct": round(100.0 * total_x / total_p, 1) if total_p else None},
            "retries_left_out": retries,
            "period": ({"from": "%d-%02d" % covered[0], "to": "%d-%02d" % covered[-1], "months": len(covered)}
                       if covered else None)}


def decode(collections, lang="en", source=None):
    lang = _lang(lang)
    failed = [c for c in collections if c["status"] == "failed"]
    codes = rcodes(lang)
    labels = LABELS[lang]
    by_code, by_cat, days, booked_days, per_customer = {}, {}, {}, {}, {}
    total_n = total_c = total_unknown = 0
    for f in failed:
        n, c = int(f.get("batch_count") or 1), cents_known(f.get("amount"))
        unknown_amount = n if f.get("amount") is None else 0
        code = f.get("reason_code") or None
        cat = category(code, f.get("scheme"), codes)
        key = code or ("proprietary" if f.get("reason_proprietary") else
                       "missing" if f.get("reason_missing") else "unreadable")
        b = by_code.setdefault(key, {"code": code, "count": 0, "cents": 0, "unknown": 0,
                                     "known": bool(code and code in codes), "categories": {}, "schemes": {},
                                     "proprietary": key == "proprietary", "missing": key == "missing"})
        b["count"] += n
        b["cents"] += c
        b["unknown"] += unknown_amount
        b["categories"][cat] = b["categories"].get(cat, 0) + n
        sch = f.get("scheme") or "unknown"
        b["schemes"][sch] = b["schemes"].get(sch, 0) + n
        k = by_cat.setdefault(cat, {"count": 0, "cents": 0, "unknown": 0, "customers": set()})
        k["count"] += n
        k["cents"] += c
        k["unknown"] += unknown_amount
        if f.get("customer"):
            k["customers"].add(f["customer"])
        total_n += n
        total_c += c
        total_unknown += unknown_amount
        when = parse_iso(f.get("date"))
        if when:
            target = days if f.get("date_kind") == "collection" else booked_days
            target[str(when.day)] = target.get(str(when.day), 0) + n
        if f.get("customer"):
            per_customer[f["customer"]] = per_customer.get(f["customer"], 0) + n
    rows = []
    for key, b in by_code.items():
        r = codes.get(b["code"] or "")
        epc = None
        if r:
            meaning = _clean(r["DESC"])
        elif b["proprietary"]:
            meaning = labels["proprietary"]
        elif b["missing"]:
            meaning = labels["missing"]
        elif b["code"] in reasons.EPC_SDD:
            # Not on Twikey's page, but in the EPC list: the EPC rulebook reason, word for word (English).
            meaning, epc = reasons.EPC_SDD[b["code"]], reasons.EPC_SOURCE
        elif b["code"]:
            meaning = labels["unknown"]
        else:
            meaning = None
        label = b["code"] or (labels["proprietary"] if b["proprietary"] else labels["missing"] if b["missing"]
                              else None)
        rows.append({"code": b["code"], "label": label,
                     "count": b["count"], "amount": euros(b["cents"]), "amount_unknown_count": b["unknown"],
                     "known": b["known"], "meaning": meaning, "meaning_source": epc,
                     "categories": b["categories"], "schemes": b["schemes"],
                     "page": RCODE_PAGE[lang] % b["code"] if r else None})
    rows.sort(key=lambda r: (-r["amount"], r["code"] or ""))
    dates = [parse_iso(f.get("date")) for f in failed]
    stats = day_stats(collections)
    rates = {k: v for k, v in stats["days"].items() if v["months"] >= DAY_MIN_MONTHS}
    top = sorted(((k, v) for k, v in rates.items() if v["failed"]),
                 key=lambda kv: (-kv[1]["rate_pct"], int(kv[0])))[:3]
    out = {
        "version": VERSION, "check": "failure-decoder",
        "checked": bool(collections) if source is None else bool(source),
        "total": {"count": total_n, "amount": euros(total_c), "amount_unknown_count": total_unknown},
        "period": {"from": str(min(d for d in dates if d)) if any(dates) else None,
                   "to": str(max(d for d in dates if d)) if any(dates) else None,
                   "months": months_spanned(dates)},
        "by_code": rows,
        "by_category": {cat: {"count": by_cat[cat]["count"], "amount": euros(by_cat[cat]["cents"]),
                              "amount_unknown_count": by_cat[cat]["unknown"], "meaning": CATEGORY_TEXTS[lang][cat],
                              "customers": sorted(by_cat[cat]["customers"])}
                        for cat in CATEGORIES if cat in by_cat},
        "days_of_month": rates,
        "days_of_month_basis": DAY_BASIS[lang],
        "days_of_month_period": stats["period"],
        "days_of_month_overall": stats["overall"],
        "failures_by_day": dict(sorted(days.items(), key=lambda kv: int(kv[0]))),
        "days_of_month_return_booked": dict(sorted(booked_days.items(), key=lambda kv: int(kv[0]))),
        "top_days": [{"day": int(k), "failed": v["failed"], "presented": v["presented"], "rate_pct": v["rate_pct"]}
                     for k, v in top],
        "repeat_customers": dict(sorted((c, n) for c, n in per_customer.items() if n >= 2)),
        # codes that are not on Twikey's reason-code page (an EPC code keeps its EPC meaning in by_code)
        "unknown_codes": sorted(r["code"] for r in rows if r["code"] and not r["known"]),
        "language": lang,
        "twikey": claims.line("failure-decoder", lang),
    }
    if not out["checked"]:
        out["not_checked"] = not_checked("failures", lang)
    return out


DAY_BASIS = {
    "en": "failure rate per usual collection day of the month: failed collections against collections presented "
          "(collection date), in the months the bank statements cover. A new presentation of a failed collection "
          "is left out, and a run moved by a weekend or bank holiday counts under its usual day. A day is shown "
          "with two months of data or more, and counts for a suggested day with 20 collections or more.",
    "nl": "percentage mislukte domiciliëringen per gewone domiciliëringsdag van de maand: mislukte tegenover "
          "aangeboden domiciliëringen (domiciliëringsdatum), in de maanden die de bankafschriften dekken. Een "
          "domiciliëring die opnieuw aangeboden wordt na een mislukking telt niet mee, en een reeks die door een "
          "weekend of feestdag verschoven is telt op haar gewone dag. Een dag wordt getoond met twee maanden "
          "gegevens of meer, en telt voor een voorgestelde dag met 20 domiciliëringen of meer.",
    "fr": "taux d'échec par jour de prélèvement habituel du mois : prélèvements échoués par rapport aux prélèvements "
          "présentés (date de prélèvement), sur les mois couverts par les relevés bancaires. Une nouvelle "
          "présentation d'un prélèvement échoué n'est pas comptée, et une série décalée par un week-end ou un jour "
          "férié compte pour son jour habituel. Un jour est affiché avec deux mois de données ou plus, et compte "
          "pour un jour proposé avec 20 prélèvements ou plus.",
}


# --------------------------------------------------------------------------- mandates

RULES_36 = {
    "en": "EPC SEPA Direct Debit rulebooks (Core and B2B), section 4.2: when no collection is presented on a mandate "
          "for 36 months, counted from the last presented collection even if it was rejected, returned or "
          "refunded, the creditor must cancel the mandate.",
    "nl": "EPC SEPA Direct Debit-rulebooks (Core en B2B), sectie 4.2: als er 36 maanden geen domiciliëring op een "
          "mandaat aangeboden wordt, geteld vanaf de laatste aangeboden domiciliëring, ook als die geweigerd, "
          "teruggestort of terugbetaald werd, moet de schuldeiser het mandaat annuleren.",
    "fr": "Rulebooks EPC SEPA Direct Debit (Core et B2B), section 4.2 : quand aucun prélèvement n'est présenté sur "
          "un mandat pendant 36 mois, à compter du dernier prélèvement présenté, même s'il a été rejeté, retourné "
          "ou remboursé, le créancier doit annuler le mandat.",
}
RULE_36 = RULES_36["en"]


ISSUES = ("expired", "expiring_90_days", "unused_since_signing", "last_collection_unknown", "missing_reference",
          "missing_signature_date", "signature_missing", "duplicate_reference", "possible_duplicate", "iban_changed",
          "b2b_not_confirmed")


def mandate_health(mandates, collections, on, lang="en", source=None):
    """Mandate checks. A presentation is a collection with its collection date: a collected one or a failed one.

    A return or refund booked without the date of the collection it returns never counts as a presentation:
    its booking date is weeks or months later. When such a return is booked after the last known
    presentation, the real last presentation is unknown, and the mandate is listed as "last collection
    unknown" instead of being judged on the 36-month rule.

    An expired mandate carries `counted_from`: the last presentation before the 36 months without one (a date
    from the collections or the mandate list's last collection). Presentations after the expiry date are
    counted in `presented_after_expiry`, the failed ones among them in `failed_after_expiry`.
    """
    lang = _lang(lang)
    by_code = {}
    for m in mandates:
        by_code.setdefault(m["mandate"], []).append(m)
    pres = {}
    for c in collections:
        if c.get("mandate") and parse_iso(c.get("date")):
            pres.setdefault(c["mandate"], []).append(c)

    out = {k: [] for k in ISSUES}
    failed_on = {}
    cancelled = 0
    for m in mandates:
        rows_same = by_code[m["mandate"]]
        mine_all = pres.get(m["mandate"], [])
        if len(rows_same) > 1:
            # One reference on several rows: a collection belongs to the row of its customer. Only when
            # no collection names any of those customers do they count for every row.
            row_customers = {r.get("customer") for r in rows_same}
            if any(c.get("customer") in row_customers for c in mine_all):
                mine_all = [c for c in mine_all if c.get("customer") == m.get("customer")]
        mine = [c for c in mine_all if c.get("date_kind") == "collection"]
        undated_returns = sorted(parse_iso(c["date"]) for c in mine_all
                                 if c.get("date_kind") != "collection" and c["status"] == "failed")
        item = {"mandate": m["mandate"], "customer": m.get("customer")}
        failed_on[(m["mandate"], m.get("customer"))] = sum(cents_known(c.get("amount")) for c in mine_all
                                                           if c["status"] == "failed")
        if m.get("ref_missing"):
            out["missing_reference"].append(dict(item))
        if not m.get("signed_date"):
            out["missing_signature_date"].append(dict(item))
        if m.get("signed") is False:
            out["signature_missing"].append(dict(item))
        if m.get("scheme") == "B2B" and m.get("bank_confirmed") is False:
            out["b2b_not_confirmed"].append(dict(item))
        accounts = {m.get("account")} | {c.get("account") for c in mine_all}
        accounts.discard(None)
        if len(accounts) > 1:
            out["iban_changed"].append(dict(item, accounts=len(accounts)))
        if m.get("status") == "cancelled":
            cancelled += 1
            continue
        dates = sorted({parse_iso(c["date"]) for c in mine} | ({parse_iso(m["last_collection_date"])}
                                                              if m.get("last_collection_date") else set()))
        dates = [x for x in dates if x and x <= on]
        late_returns = [r for r in undated_returns if r and r <= on and (not dates or r > dates[-1])]
        if late_returns:
            out["last_collection_unknown"].append(dict(item, return_booked_on=str(late_returns[-1]),
                                                       last_known_collection=str(dates[-1]) if dates else None))
            continue
        if not dates:
            signed = parse_iso(m.get("signed_date"))
            if signed and on >= add_months(signed, 36):
                out["unused_since_signing"].append(dict(item, signed_on=str(signed)))
            continue
        expired_on, base, after = None, None, 0
        for a, b in zip(dates, dates[1:]):
            if expired_on is None and b >= add_months(a, 36):
                expired_on, base = add_months(a, 36), a
            if expired_on is not None and b >= expired_on:
                after += 1
        if expired_on is None:
            limit = add_months(dates[-1], 36)
            if on >= limit:
                expired_on, base = limit, dates[-1]
            elif (limit - on).days <= 90:
                out["expiring_90_days"].append(dict(item, expires_on=str(limit), last_presented=str(dates[-1])))
        if expired_on is not None:
            e = dict(item, expired_on=str(expired_on), counted_from=str(base), last_presented=str(dates[-1]))
            if after:
                e["presented_after_expiry"] = after
                late = [c for c in mine if parse_iso(c["date"]) and expired_on <= parse_iso(c["date"]) <= on]
                late_dates = {c["date"] for c in late}
                failed_dates = {c["date"] for c in late if c["status"] == "failed"}
                # a presentation that was collected and later returned counts as failed
                e["failed_after_expiry"] = sum(1 for d in late_dates if d in failed_dates)
            out["expired"].append(e)

    for code, rows in by_code.items():
        if len(rows) > 1 and not rows[0].get("ref_missing"):
            out["duplicate_reference"].append({"mandate": code, "customers": sorted({r.get("customer") or "?" for r in rows})})
    groups = {}
    for m in mandates:
        if m.get("status") == "cancelled" or not m.get("customer") or not m.get("account"):
            continue
        groups.setdefault((m["customer"], m["account"], m.get("scheme")), set()).add(m["mandate"])
    for (cust, _acct, _sch), codes in sorted(groups.items()):
        if len(codes) > 1:
            out["possible_duplicate"].append({"customer": cust, "mandates": sorted(codes)})

    def at_stake(items):
        return euros(sum(failed_on.get((i["mandate"], i.get("customer")), 0) for i in items))

    for k in out:
        out[k].sort(key=lambda i: (i.get("mandate") or "", i.get("customer") or ""))
    result = {
        "version": VERSION, "check": "mandate-health", "on": str(on), "rule": RULES_36[lang],
        "checked": bool(mandates) if source is None else bool(source),
        "rows": len(mandates), "codes": len(by_code), "cancelled": cancelled,
        "core": sum(1 for m in mandates if m.get("scheme") == "CORE"),
        "b2b": sum(1 for m in mandates if m.get("scheme") == "B2B"),
        "scheme_unknown": sum(1 for m in mandates if not m.get("scheme")),
        "issues": out,
        "counts": {k: len(v) for k, v in out.items()},
        # Mandates to renew: expired under the 36-month rule and expiring within 90 days, nothing else. Mandates
        # never used since signing are counted apart (unused_since_signing).
        "to_renew": len(to_renew(out)),
        "failed_amount_on": {k: at_stake(v) for k, v in out.items() if k not in ("duplicate_reference",
                                                                                   "possible_duplicate")},
        "twikey": claims.line("mandate-health", lang),
    }
    if not result["checked"]:
        result["not_checked"] = not_checked("mandates", lang)
    return result


def to_renew(issues):
    """The one definition of mandates to renew: expired under the 36-month rule, and expiring within 90 days."""
    return issues["expired"] + issues["expiring_90_days"]


# --------------------------------------------------------------------------- matching

def match(store, bank, lang="en", source=None):
    """Bank payments in against invoices.

    A payment never settles an invoice issued after the payment date. Among candidates, an invoice the books
    show as paid within seven days of the payment comes first, then open invoices from the oldest due date.
    A payment from a party that is in none of the invoices, without a structured communication and without
    an open invoice number in its text, is a receipt that is not an invoice payment (a deposit refund, a
    loan, a grant): it is listed apart and not counted as an unmatched invoice payment.

    Cancelled invoices are never candidates. A credit note is never matched on its own: it only counts,
    with a minus sign, in a payment for two to four documents of the same customer (an invoice of €1,000
    and a credit note of €200 settled by one payment of €800).
    """
    invs = store["invoices"]
    remaining = {k: cents(v["amount"]) for k, v in invs.items()}
    by_ogm, by_cust, credits = {}, {}, {}
    # A payer with any invoice in the books, credited or cancelled ones included, is a customer.
    invoiced = {v["customer"]["customerNumber"] for v in invs.values()}
    for k, v in sorted(invs.items()):
        cust = v["customer"]["customerNumber"]
        if v["state"] == "CREDITED":
            credits.setdefault(cust, []).append(k)
            continue
        if v["state"] in NOT_PAYABLE:
            continue
        o = (v.get("xray") or {}).get("ogm")
        if o:
            by_ogm.setdefault(o, []).append(k)
        by_cust.setdefault(cust, []).append(k)

    def value(k):
        return -remaining[k] if invs[k]["state"] == "CREDITED" else remaining[k]

    def paid_day(k):
        return parse_iso((invs[k].get("xray") or {}).get("paid_date"))

    def due_day(k):
        return parse_iso(invs[k].get("duedate")) or parse_iso(invs[k].get("date"))

    def issued_by(k, day):
        issued = parse_iso(invs[k].get("date"))
        return issued is None or day is None or issued <= day

    def rank(k, day):
        p = paid_day(k)
        if p == day:
            return (0, 0)
        if p and abs((p - day).days) <= 7:
            return (1, abs((p - day).days))
        if invs[k]["state"] == "BOOKED":
            return (2, (due_day(k) or day).toordinal())
        return (3, abs(((p or day) - day).days))

    cats = {k: {"count": 0, "cents": 0, "customers": set(), "lines": []} for k in
            ("matched", "paid_but_open", "partial", "bundled", "double", "overpaid", "unmatched", "other_receipts")}
    extra = {"partial_still_open": 0, "bundled_invoices": 0, "bundled_credit_notes": 0, "paid_but_open_invoices": [],
             "unmatched_known": 0, "unmatched_unknown": 0, "unmatched_mentions_open_invoice": 0}

    def add(cat, line, invoices=(), **more):
        c = cats[cat]
        c["count"] += 1
        c["cents"] += cents(line["amount"])
        if line.get("customer"):
            c["customers"].add(line["customer"])
        c["lines"].append(dict({"line": line["id"], "date": line["date"], "amount": line["amount"],
                                "customer": line.get("customer"), "invoices": list(invoices)}, **more))

    def settle(k, line):
        amt, rem = cents(line["amount"]), remaining[k]
        if rem <= 0:
            add("double", line, [k])
        elif amt == rem:
            remaining[k] = 0
            if invs[k]["state"] == "BOOKED":
                add("paid_but_open", line, [k])
                extra["paid_but_open_invoices"].append(k)
            else:
                add("matched", line, [k])
        elif amt < rem:
            remaining[k] = rem - amt
            # what stays open on that invoice after this payment
            add("partial", line, [k], still_open=euros(remaining[k]))
            extra["partial_still_open"] += remaining[k]
        else:
            remaining[k] = 0
            add("overpaid", line, [k])

    for line in sorted(bank, key=lambda b: (b["date"] or "", b["id"])):
        day = parse_iso(line["date"])
        amt = cents(line["amount"])
        cands = [k for k in by_ogm.get(line.get("ogm") or "", []) if issued_by(k, day)]
        if cands:
            settle(sorted(cands, key=lambda k: (remaining[k] <= 0, rank(k, day)))[0], line)
            continue
        cust = line.get("customer")
        mine = [k for k in by_cust.get(cust, []) if remaining[k] > 0 and issued_by(k, day)] if cust else []
        exact = sorted([k for k in mine if remaining[k] == amt], key=lambda k: rank(k, day))
        if exact:
            settle(exact[0], line)
            continue
        pool = sorted(mine, key=lambda k: rank(k, day))[:12]
        pool += [k for k in credits.get(cust, []) if remaining[k] > 0 and issued_by(k, day)][:4] if cust else []
        found = None
        for size in (2, 3, 4):
            for combo in itertools.combinations(pool, size):
                if any(invs[k]["state"] != "CREDITED" for k in combo) and sum(value(k) for k in combo) == amt:
                    found = combo
                    break
            if found:
                break
        if found:
            for k in found:
                remaining[k] = 0
            add("bundled", line, found)
            extra["bundled_invoices"] += sum(1 for k in found if invs[k]["state"] != "CREDITED")
            extra["bundled_credit_notes"] += sum(1 for k in found if invs[k]["state"] == "CREDITED")
            continue
        known = bool(cust and cust in invoiced)
        if not known and not line.get("ogm") and line.get("ogm_status") != "invalid" \
                and not line.get("mentions_open_invoice"):
            add("other_receipts", line)
            continue
        add("unmatched", line)
        if known:
            extra["unmatched_known"] += 1
        else:
            extra["unmatched_unknown"] += 1
        if line.get("mentions_open_invoice"):
            extra["unmatched_mentions_open_invoice"] += 1

    dates = [parse_iso(b["date"]) for b in bank]
    result = {"version": VERSION, "check": "unmatched-payments",
              "credit_lines": {"count": len(bank), "amount": euros(sum(cents(b["amount"]) for b in bank))},
              "period": {"from": str(min(d for d in dates if d)) if any(dates) else None,
                         "to": str(max(d for d in dates if d)) if any(dates) else None,
                         "months": months_spanned(dates)}}
    for k, c in cats.items():
        result[k] = {"count": c["count"], "amount": euros(c["cents"]), "customers": sorted(c["customers"]),
                     "lines": c["lines"] if k != "matched" else []}
    result["partial"]["still_open"] = euros(extra["partial_still_open"])
    result["bundled"]["invoices"] = extra["bundled_invoices"]
    result["bundled"]["credit_notes"] = extra["bundled_credit_notes"]
    result["paid_but_open"]["invoices"] = extra["paid_but_open_invoices"]
    result["unmatched"].update({"known_customer": extra["unmatched_known"], "unknown_party": extra["unmatched_unknown"],
                                "mentions_open_invoice": extra["unmatched_mentions_open_invoice"]})
    lang = _lang(lang)
    result["method"] = MATCH_METHOD[lang]
    result["checked"] = bool(bank) if source is None else bool(source)
    if not result["checked"]:
        result["not_checked"] = not_checked("bank", lang)
    result["twikey"] = claims.line("unmatched-payments", lang)
    return result


MATCH_METHOD = {
    "en": "Structured communication first (Belgian OGM, check digits verified), then amount and customer code: one "
          "invoice with the same amount, else two to four documents of that customer that add up to it, credit "
          "notes counted with a minus sign. Canceled invoices and credit notes on their own are never matched. A "
          "payment never settles an invoice issued after the payment date. Lines that match nothing stay unmatched. "
          "X-ray does not guess. Payments from parties that are in none of your invoices, without a structured "
          "communication or an open invoice number, are listed as other receipts, not as unmatched invoice "
          "payments.",
    "nl": "Eerst de gestructureerde mededeling (Belgische OGM, controlecijfers nagekeken), dan bedrag en klantcode: "
          "één factuur met hetzelfde bedrag, anders twee tot vier documenten van die klant die samen dat bedrag "
          "geven, creditnota's met een minteken. Geannuleerde facturen en creditnota's op zich worden nooit "
          "gekoppeld. Een betaling betaalt nooit een factuur die na de betaaldatum gemaakt is. Regels die nergens "
          "bij passen, blijven ongekoppeld. X-ray gokt niet. Betalingen van partijen die op geen enkele factuur "
          "staan, zonder gestructureerde mededeling of open factuurnummer, staan apart als andere ontvangsten, niet "
          "als ongekoppelde factuurbetalingen.",
    "fr": "D'abord la communication structurée (OGM belge, chiffres de contrôle vérifiés), puis le montant et le code "
          "client : une facture du même montant, sinon deux à quatre documents de ce client dont la somme donne ce "
          "montant, les notes de crédit comptées en négatif. Les factures annulées et les notes de crédit seules ne "
          "sont jamais rapprochées. Un paiement ne règle jamais une facture émise après la date du paiement. Les "
          "lignes sans correspondance restent non rapprochées. X-ray ne devine pas. Les paiements de tiers qui ne "
          "figurent sur aucune facture, sans communication structurée ni numéro de facture ouverte, sont listés "
          "comme autres recettes, pas comme des paiements de factures non rapprochés.",
}


# --------------------------------------------------------------------------- terms and payer profiles

NOT_PAYABLE = ("CANCELLED", "ARCHIVED")


def calc_view(store):
    """Store for the standard formulas: open invoices count with their open amount."""
    view = copy.deepcopy(store)
    for inv in view["invoices"].values():
        if inv.get("state") == "BOOKED":
            inv["amount"] = (inv.get("xray") or {}).get("open_amount", inv["amount"])
    return view


def _slope(values):
    n = len(values)
    if n < 2:
        return 0.0
    mx = (n - 1) / 2.0
    my = sum(values) / float(n)
    den = sum((i - mx) ** 2 for i in range(n))
    return sum((i - mx) * (v - my) for i, v in enumerate(values)) / den


PROFILES = ("clockwork", "after_failures", "late_but_pays", "drifting", "at_risk", "too_early")


def own_terms_90d(store, cfg, on):
    """Each invoice's own term (due date minus invoice date), weighted by amount, over the invoices billed in
    the 90 days before the as-of date: the same invoices the DSO counts. None when there are none."""
    since = on - dt.timedelta(days=90)
    num_ = den = 0.0
    for inv in store["invoices"].values():
        issued, due = parse_iso(inv.get("date")), parse_iso(inv.get("duedate"))
        if not (issued and due) or issued < since or inv["state"] in cfg["closed_states"]:
            continue
        amt = float(inv.get("amount") or 0)
        num_ += (due - issued).days * amt
        den += amt
    return round(num_ / den, 1) if den else None


def dso_90d(store, cfg, on):
    """Countback DSO: open receivables (open amounts) / what was billed in the 90 days before the as-of date
    (billed amounts, so a partly paid invoice counts in full) x 90."""
    since = on - dt.timedelta(days=90)
    billed = open_ar = 0.0
    for inv in store["invoices"].values():
        if inv["state"] in cfg["closed_states"]:
            continue
        issued = parse_iso(inv.get("date"))
        if issued and issued >= since:
            billed += float(inv.get("amount") or 0)
        if inv["state"] not in cfg["paid_states"]:
            open_ar += float((inv.get("xray") or {}).get("open_amount", inv.get("amount")) or 0)
    return round(open_ar / billed * 90, 1) if billed else None


def terms(store, cfg, on, collections=None, lang="en"):
    calc.TODAY = on
    view = calc_view(store)
    stats = calc.customer_stats(view, cfg)
    failed_customers = {c["customer"] for c in collections or [] if c["status"] == "failed" and c.get("customer")}
    per = {}
    for inv in store["invoices"].values():
        if inv["state"] in cfg["closed_states"]:
            continue
        per.setdefault(inv["customer"]["customerNumber"], []).append(inv)
    rows = []
    for cust, invs in sorted(per.items()):
        s = stats.get(cust, {})
        paid = sorted([i for i in invs if i["state"] == "PAID" and calc.paid_date(i) and calc.d(i.get("duedate"))],
                      key=lambda i: i["duedate"])
        late = [(calc.paid_date(i) - calc.d(i["duedate"])).days for i in paid]
        to_pay = [(calc.paid_date(i) - calc.d(i["date"])).days for i in paid if calc.d(i.get("date"))]
        term_list = [(i.get("xray") or {}).get("terms_days") for i in invs]
        term_list = [t for t in term_list if t is not None]
        agreed = max(sorted(set(term_list)), key=term_list.count) if term_list else None
        slope = round(_slope(late), 2)
        if s.get("max_days_overdue", 0) > 60:
            profile = "at_risk"
        elif len(paid) < 3:
            profile = "too_early"
        elif len(paid) >= 6 and slope >= 2.0:
            profile = "drifting"
        elif (s.get("avg_days_late") or 0) > 5:
            profile = "late_but_pays"
        elif cust in failed_customers:
            profile = "after_failures"  # pays on time in the books, but only after failed collections
        else:
            profile = "clockwork"
        rows.append({"customer": cust, "profile": profile, "agreed_terms_days": agreed,
                     "avg_days_to_pay": round(sum(to_pay) / len(to_pay), 1) if to_pay else None,
                     "avg_days_late": s.get("avg_days_late"), "on_time_pct": s.get("on_time_pct"),
                     "late_trend_days_per_invoice": slope, "paid_invoices": len(paid),
                     "open_amount": s.get("open_amount", 0.0), "overdue_amount": s.get("overdue_amount", 0.0),
                     "max_days_overdue": s.get("max_days_overdue", 0), "score": s.get("score"),
                     "risk": s.get("risk"), "direct_debit": s.get("mandate", False),
                     "failed_collections": cust in failed_customers})
    profiles = {}
    for p in PROFILES:
        sel = [r for r in rows if r["profile"] == p]
        profiles[p] = {"customers": [r["customer"] for r in sel], "count": len(sel),
                       "open_amount": round(sum(r["open_amount"] for r in sel), 2),
                       "overdue_amount": round(sum(r["overdue_amount"] for r in sel), 2)}
    ag = calc.aging(view, cfg)
    ds = calc.dso(view, cfg)
    dso = dso_90d(store, cfg, on)
    own = own_terms_90d(store, cfg, on)
    lang = _lang(lang)
    return {
        "version": VERSION, "check": "terms-vs-reality", "as_of": str(on),
        "profiles": profiles,
        "rules": dict(PROFILE_RULES[lang]),
        "customers": rows,
        "open_receivables": round(sum(r["open_amount"] for r in rows), 2),
        "overdue": round(sum(r["overdue_amount"] for r in rows), 2),
        "aging": {b: round(ag["total"][b], 2) for b in ag["buckets"]},
        "dso_90d": dso, "terms_days_90d": own,
        "dso_minus_terms": round(dso - own, 1) if dso is not None and own is not None else None,
        "dso_trend": ds["trend"],
        "method": TERMS_METHOD[lang],
        "twikey": [claims.line("terms-vs-reality", lang), claims.line("payer-profiles", lang)],
    }


PROFILE_RULES = {
    "en": {"at_risk": "an open invoice more than 60 days past due",
           "too_early": "fewer than three paid invoices",
           "drifting": "six or more paid invoices and days late grow by two or more per invoice",
           "late_but_pays": "pays on average more than five days late",
           "after_failures": "pays on average at most five days late, but had failed collections",
           "clockwork": "pays on average at most five days late, no failed collections"},
    "nl": {"at_risk": "een open factuur meer dan 60 dagen over de vervaldag",
           "too_early": "minder dan drie betaalde facturen",
           "drifting": "zes betaalde facturen of meer, en de dagen te laat groeien met twee of meer per factuur",
           "late_but_pays": "betaalt gemiddeld meer dan vijf dagen te laat",
           "after_failures": "betaalt gemiddeld hoogstens vijf dagen te laat, maar had mislukte domiciliëringen",
           "clockwork": "betaalt gemiddeld hoogstens vijf dagen te laat, geen mislukte domiciliëringen"},
    "fr": {"at_risk": "une facture ouverte échue depuis plus de 60 jours",
           "too_early": "moins de trois factures payées",
           "drifting": "six factures payées ou plus, et les jours de retard augmentent de deux ou plus par facture",
           "late_but_pays": "paie en moyenne avec plus de cinq jours de retard",
           "after_failures": "paie en moyenne avec au plus cinq jours de retard, mais a eu des prélèvements échoués",
           "clockwork": "paie en moyenne avec au plus cinq jours de retard, aucun prélèvement échoué"},
}
TERMS_METHOD = {
    "en": "Standard aging and DSO formulas. DSO is days sales outstanding: open receivables divided by what was "
          "billed in the last 90 days, times 90. It is compared with each invoice's own term (due date minus "
          "invoice date) over the same invoices, weighted by amount. Open invoices count with their open amount, "
          "billed invoices with their full amount.",
    "nl": "Standaardformules voor ouderdom en DSO. DSO is het aantal dagen klantenkrediet: de openstaande "
          "vorderingen gedeeld door wat in de laatste 90 dagen gefactureerd is, maal 90. Het wordt vergeleken met "
          "de eigen termijn van elke factuur (vervaldag min factuurdatum) over dezelfde facturen, gewogen naar "
          "bedrag. Open facturen tellen met hun openstaand bedrag, gefactureerde facturen met hun volledige bedrag.",
    "fr": "Formules standard pour la balance âgée et le DSO. Le DSO est le délai moyen de paiement des clients : "
          "les créances ouvertes divisées par ce qui a été facturé sur les 90 derniers jours, multiplié par 90. Il "
          "est comparé au délai propre de chaque facture (date d'échéance moins date de facture) sur les mêmes "
          "factures, pondéré par le montant. Les factures ouvertes comptent pour leur montant ouvert, les factures "
          "émises pour leur montant total.",
}


# --------------------------------------------------------------------------- manual steps

LATE_DAYS = 7
# The item types of the steps check, in the order of data/manual_steps.json, and what each is counted from.
STEP_ITEMS = ("failed_new_attempt", "failed_new_mandate", "failed_conversation", "failed_own_setup", "failed_unknown",
              "mandate_renew", "mandate_fix", "unmatched", "double_payment", "paid_but_open", "late_invoice")
STEP_SOURCES = {
    "failed_new_attempt": "decode: reason category new_attempt",
    "failed_new_mandate": "decode: reason category new_mandate",
    "failed_conversation": "decode: reason category conversation",
    "failed_own_setup": "decode: reason category own_setup",
    "failed_unknown": "decode: reason categories bank, unknown and unreadable",
    "mandate_renew": "mandates: expired under the 36-month rule, and expiring within 90 days",
    "mandate_fix": "mandates: missing reference, date of signing or signature, duplicate references, possible "
                   "duplicates, collections from more than one account, B2B not confirmed",
    "unmatched": "match: no match, partial, one payment for several invoices",
    "double_payment": "match: paid twice",
    "paid_but_open": "match: paid at the bank, still open in the books",
    "late_invoice": "invoices: paid more than seven days after the due date, or open more than seven days past it",
}
# The export each item type is counted from: without it, the item type was not checked.
STEP_NEEDS = {"failed_new_attempt": "failures", "failed_new_mandate": "failures", "failed_conversation": "failures",
              "failed_own_setup": "failures", "failed_unknown": "failures", "mandate_renew": "mandates",
              "mandate_fix": "mandates", "unmatched": "bank", "double_payment": "bank", "paid_but_open": "bank",
              "late_invoice": "invoices"}
MANDATE_FIX = ("missing_reference", "missing_signature_date", "signature_missing", "duplicate_reference",
               "possible_duplicate", "iban_changed", "b2b_not_confirmed")
UNMATCHED = ("unmatched", "partial", "bundled")


def late_invoices(store, on):
    """Invoices that went more than seven days past due: paid more than seven days after the due date, or still
    open more than seven days after it on the as-of date. Credit notes and cancelled invoices do not count.
    months: the invoice months the history covers."""
    invs = list(store["invoices"].values())
    late = []
    for i in invs:
        due = parse_iso(i.get("duedate"))
        if not due or i["state"] in ("CREDITED", "CANCELLED", "ARCHIVED"):
            continue
        if i["state"] == "PAID":
            p = parse_iso((i.get("xray") or {}).get("paid_date"))
            if p and (p - due).days > LATE_DAYS:
                late.append(i)
        elif (on - due).days > LATE_DAYS:
            late.append(i)
    return {"count": len(late), "months": months_spanned(parse_iso(i.get("date")) for i in invs),
            "customers": sorted({i["customer"]["customerNumber"] for i in late})}


def manual_steps(lang="en"):
    """The labels, checklists and text lines of data/manual_steps.json in one language."""
    with open(os.path.join(DATA_DIR, "manual_steps.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data[lang if lang in ("en", "nl", "fr") else "en"]


def steps(store, mandates, collections, bank, on, lang="en", source=None):
    """Per item type: how many items the files hold, and the checklist of manual steps one item asks for when it
    is done by hand. Counted with the other checks: decode, mandate_health, match and late_invoices. An item type
    whose export is missing (source, see sources()) is not checked: checked false, never counted as zero."""
    lang = _lang(lang)
    source = source or sources(None, store, mandates, collections, bank)
    dec = decode(collections, lang)
    mand = mandate_health(mandates, collections, on, lang)
    mat = match(store, bank, lang)
    late = late_invoices(store, on)
    copy_ = manual_steps(lang)
    cats = dec["by_category"]

    def failed(*names):
        sel = [cats[c] for c in names if c in cats]
        return (sum(c["count"] for c in sel), dec["period"]["months"],
                sorted({x for c in sel for x in c["customers"]}))

    renew = to_renew(mand["issues"])
    fix = {}
    for issue in MANDATE_FIX:
        for i in mand["issues"][issue]:
            k = i["mandate"] if i.get("mandate") else ("customer", i.get("customer"))
            fix.setdefault(k, set()).update(i.get("customers") or [i.get("customer")])
    counts = {
        "failed_new_attempt": failed("new_attempt"),
        "failed_new_mandate": failed("new_mandate"),
        "failed_conversation": failed("conversation"),
        "failed_own_setup": failed("own_setup"),
        "failed_unknown": failed("bank", "unknown", "unreadable"),
        "mandate_renew": (len(renew), None, sorted({i["customer"] for i in renew if i.get("customer")})),
        "mandate_fix": (len(fix), None, sorted({c for cs in fix.values() for c in cs if c})),
        "unmatched": (sum(mat[k]["count"] for k in UNMATCHED), mat["period"]["months"],
                      sorted({c for k in UNMATCHED for c in mat[k]["customers"]})),
        "double_payment": (mat["double"]["count"], mat["period"]["months"], mat["double"]["customers"]),
        "paid_but_open": (mat["paid_but_open"]["count"], mat["period"]["months"], mat["paid_but_open"]["customers"]),
        "late_invoice": (late["count"], late["months"], late["customers"]),
    }
    items = []
    for k in STEP_ITEMS:
        n, months, customers = counts[k]
        months = months or None
        checklist = copy_["items"][k]["checklist"]
        checked = bool(source.get(STEP_NEEDS[k]))
        item = {"id": k, "label": copy_["items"][k]["label"], "label_one": copy_["items"][k]["label_one"],
                "checked": checked, "count": n, "months": months,
                "per_month": round(n / float(months), 1) if months and checked else None,
                "steps_each": len(checklist), "steps_total": n * len(checklist), "checklist": checklist,
                "examples": customers[:12], "source": STEP_SOURCES[k]}
        if not checked:
            item["not_checked"] = not_checked(STEP_NEEDS[k], lang)
        items.append(item)
    items.sort(key=lambda i: (-i["steps_total"], STEP_ITEMS.index(i["id"])))
    timed = [i for i in items if i["per_month"] is not None]
    return {
        "version": VERSION, "check": "manual-steps", "as_of": str(on), "language": lang,
        "items": items,
        "total_items": sum(i["count"] for i in items),
        "total_steps": sum(i["steps_total"] for i in items),
        # the per-month totals add up the exact per-month values, rounded once, for the item types with a period
        "per_month_total": round(sum(i["count"] / float(i["months"]) for i in timed), 1) if timed else None,
        "per_month_steps_total": (round(sum(i["steps_total"] / float(i["months"]) for i in timed), 1)
                                  if timed else None),
        "per_month_left_out": [i["id"] for i in items if i["per_month"] is None and i["count"]],
        "not_checked": [i["id"] for i in items if not i["checked"]],
        "basis": copy_["text"]["basis"],
        # failure-decoder already holds the mandate-health quote (renewed consent for expired mandates) word for word
        "twikey": [claims.line(c, lang) for c in ("failure-decoder", "unmatched-payments")],
    }


# --------------------------------------------------------------------------- go-live facts

GOLIVE_LINES = ("own-bank", "core-b2b", "b2b-registered", "core-refund", "creditor-id", "about")
GOLIVE_QUESTIONS = {
    "en": ("creditor ID", "Core or B2B per customer group", "existing mandates", "accounting tool", "timing"),
    "nl": ("schuldeisernummer", "Core of B2B per klantengroep", "bestaande mandaten", "boekhoudpakket", "timing"),
    "fr": ("identifiant de créancier", "Core ou B2B par groupe de clients", "mandats existants",
           "logiciel comptable", "calendrier"),
}
EXISTING_MANDATES = {
    "en": "Ask Twikey whether your existing mandates can be reused. It depends on the bank and the mandate type.",
    "nl": "Vraag Twikey of je bestaande mandaten opnieuw gebruikt kunnen worden. Dat hangt af van de bank en het "
          "type mandaat.",
    "fr": "Demandez à Twikey si vos mandats existants peuvent être réutilisés. Cela dépend de la banque et du type "
          "de mandat.",
}


def golive(store, collections, mand, term, tool=None, lang="en"):
    invs = list(store["invoices"].values())
    customers = {i["customer"]["customerNumber"] for i in invs}
    dd = {c["customer"] for c in collections if c["status"] == "collected" and c.get("customer")}
    dd |= {i["customer"]["customerNumber"] for i in invs
           if any(p.get("method") == "sdd" for p in (i.get("lastpayment") or []))}
    months = months_spanned(parse_iso(i.get("date")) for i in invs)
    failed = [c for c in collections if c["status"] == "failed"]
    fmonths = months_spanned(parse_iso(c.get("date")) for c in failed)
    out = {
        "version": VERSION, "check": "go-live-plan",
        "customers": len(customers), "direct_debit_customers": len(dd & customers),
        "invoices_per_month": round(len(invs) / float(months), 1) if months else None,
        "mandates_core": mand["core"], "mandates_b2b": mand["b2b"],
        # expired and expiring within 90 days (to_renew), never the mandates unused since signing
        "mandates_to_renew": len(to_renew(mand["issues"])),
        "mandates_never_used": len(mand["issues"]["unused_since_signing"]),
        "b2b_not_confirmed": len(mand["issues"]["b2b_not_confirmed"]),
        "failed_per_month": round(sum(int(c.get("batch_count") or 1) for c in failed) / float(fmonths), 1)
                            if fmonths else None,
        "open_receivables": term["open_receivables"], "overdue": term["overdue"],
        "profiles": {k: v["count"] for k, v in term["profiles"].items()},
        "questions": list(GOLIVE_QUESTIONS[_lang(lang)]),
        "existing_mandates": EXISTING_MANDATES.get(lang, EXISTING_MANDATES["en"]),
        "twikey": [claims.line(i, lang) for i in GOLIVE_LINES],
        # Linked once, here: the packages named in the Twikey lines are on this page.
        "pricing_page": claims.page("pricing", lang),
        # The one call to action. The report ends with it. go-live-plan.md does not repeat it.
        "demo": claims.line("demo", lang),
    }
    if tool:
        hits = claims.partner_matches(tool)
        out["tool"] = {"asked": tool, "listed_as": hits,
                       "partners_page": claims.page("partners", lang)}
    return out
