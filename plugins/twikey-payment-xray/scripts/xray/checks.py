"""The checks. Each takes the coded ledger (collections.json and bank.json, read from camt.053 statements) and
returns a JSON-ready dict with codes, counts, amounts and dates only. No check opens a raw file."""
import datetime as dt
import json
import os

from . import VERSION, claims, reasons
from .common import DATA_DIR, cents, euros, months_spanned, parse_iso, working_day

LANGS = ("en", "nl", "fr")


def _lang(lang):
    return lang if lang in LANGS else "en"


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
        "unreadable": "No usable reason code for these (not on the statement, or a bank text that is not shown). "
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
        "unreadable": "Geen bruikbare redencode (niet op het afschrift, of een banktekst die niet getoond wordt). "
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
        "unreadable": "Pas de code motif utilisable (absent du relevé, ou un texte de la banque qui n'est pas "
                      "affiché). Demandez à votre banque.",
    },
}
LABELS = {
    "en": {"unknown": "unknown code", "proprietary": "proprietary reason (not shown)",
           "missing": "reason not on the statement"},
    "nl": {"unknown": "onbekende code", "proprietary": "eigen reden van de bank (niet getoond)",
           "missing": "reden niet op het afschrift"},
    "fr": {"unknown": "code inconnu", "proprietary": "motif propre à la banque (non affiché)",
           "missing": "motif absent du relevé"},
}
# Twikey's reason-code pages per language (Belgian Dutch and French pages for nl and fr).
RCODE_PAGE = {"en": "https://www.twikey.com/product/r-codes/%s.html",
              "nl": "https://www.twikey.com/be/product/r-codes/%s.html",
              "fr": "https://www.twikey.com/fr/product/r-codes/%s.html"}
CATEGORIES = ["new_attempt", "new_mandate", "conversation", "own_setup", "bank", "unknown", "unreadable"]
# What the failed collections are counted from: one sentence, printed with the decode output.
DECODE_BASIS = {
    "en": "Counted from the direct debits returned or refunded on your camt.053 bank statements.",
    "nl": "Geteld uit de domiciliëringen die teruggeboekt of terugbetaald werden op je camt.053-bankafschriften.",
    "fr": "Comptés à partir des prélèvements retournés ou remboursés sur vos relevés bancaires camt.053.",
}


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
        if retry(f):
            retries += 0 if returned(f) else 1
            continue
        pres.append((d, 0 if returned(f) else 1, 1))

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


def decode(collections, lang="en"):
    """Failed collections by reason code, what the codes point to, and the failure rate per collection day."""
    lang = _lang(lang)
    failed = [c for c in collections if c["status"] == "failed"]
    codes = rcodes(lang)
    labels = LABELS[lang]
    by_code, by_cat, days, booked_days, per_customer = {}, {}, {}, {}, {}
    total_n = total_c = 0
    for f in failed:
        c = cents(f["amount"])
        code = f.get("reason_code") or None
        cat = category(code, f.get("scheme"), codes)
        key = code or ("proprietary" if f.get("reason_proprietary") else
                       "missing" if f.get("reason_missing") else "unreadable")
        b = by_code.setdefault(key, {"code": code, "count": 0, "cents": 0, "known": bool(code and code in codes),
                                     "categories": {}, "schemes": {}, "proprietary": key == "proprietary",
                                     "missing": key == "missing"})
        b["count"] += 1
        b["cents"] += c
        b["categories"][cat] = b["categories"].get(cat, 0) + 1
        sch = f.get("scheme") or "unknown"
        b["schemes"][sch] = b["schemes"].get(sch, 0) + 1
        k = by_cat.setdefault(cat, {"count": 0, "cents": 0, "customers": set()})
        k["count"] += 1
        k["cents"] += c
        if f.get("customer"):
            k["customers"].add(f["customer"])
        total_n += 1
        total_c += c
        when = parse_iso(f.get("date"))
        if when:
            target = days if f.get("date_kind") == "collection" else booked_days
            target[str(when.day)] = target.get(str(when.day), 0) + 1
        if f.get("customer"):
            per_customer[f["customer"]] = per_customer.get(f["customer"], 0) + 1
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
        rows.append({"code": b["code"], "label": label, "count": b["count"], "amount": euros(b["cents"]),
                     "known": b["known"], "meaning": meaning, "meaning_source": epc,
                     "categories": b["categories"], "schemes": b["schemes"],
                     "page": RCODE_PAGE[lang] % b["code"] if r else None})
    rows.sort(key=lambda r: (-r["amount"], r["code"] or ""))
    dates = [d for d in (parse_iso(f.get("date")) for f in failed) if d]
    stats = day_stats(collections)
    rates = {k: v for k, v in stats["days"].items() if v["months"] >= DAY_MIN_MONTHS}
    top = sorted(((k, v) for k, v in rates.items() if v["failed"]),
                 key=lambda kv: (-kv[1]["rate_pct"], int(kv[0])))[:3]
    return {
        "version": VERSION, "check": "failure-decoder",
        "total": {"count": total_n, "amount": euros(total_c)},
        "period": {"from": str(min(dates)) if dates else None, "to": str(max(dates)) if dates else None,
                   "months": months_spanned(dates)},
        "by_code": rows,
        "by_category": {cat: {"count": by_cat[cat]["count"], "amount": euros(by_cat[cat]["cents"]),
                              "meaning": CATEGORY_TEXTS[lang][cat], "customers": sorted(by_cat[cat]["customers"])}
                        for cat in CATEGORIES if cat in by_cat},
        "days_of_month": rates,
        "days_of_month_basis": DAY_BASIS[lang],
        "days_of_month_period": stats["period"],
        "days_of_month_overall": stats["overall"] if stats["overall"]["presented"] else None,
        "failures_by_day": dict(sorted(days.items(), key=lambda kv: int(kv[0]))),
        "days_of_month_return_booked": dict(sorted(booked_days.items(), key=lambda kv: int(kv[0]))),
        "top_days": [{"day": int(k), "failed": v["failed"], "presented": v["presented"], "rate_pct": v["rate_pct"]}
                     for k, v in top],
        "repeat_customers": dict(sorted((c, n) for c, n in per_customer.items() if n >= 2)),
        # codes that are not on Twikey's reason-code page (an EPC code keeps its EPC meaning in by_code)
        "unknown_codes": sorted(r["code"] for r in rows if r["code"] and not r["known"]),
        "basis": DECODE_BASIS[lang],
        "language": lang,
        "twikey": claims.line("failure-decoder", lang),
    }


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


# --------------------------------------------------------------------------- incoming payments

# What a structured communication on an incoming payment is, as intake checked it (ogm.py).
PAYMENT_GROUPS = ("valid", "invalid", "other", "absent")
# The payments a person books by hand: no structured communication, or one with wrong check digits.
BY_HAND = ("invalid", "absent")
PAYMENTS_METHOD = {
    "en": "Incoming payments on your camt.053 bank statements, direct debit collections left out. A payment with a "
          "Belgian structured communication whose check digits are right names what it pays, so your accounting "
          "can book it on its own. A payment without one, or with wrong check digits, is booked by a person who "
          "finds out what it pays. Another reference (an RF creditor reference, for example) is not checked and "
          "counted apart.",
    "nl": "Inkomende betalingen op je camt.053-bankafschriften, zonder de domiciliëringen. Een betaling met een "
          "Belgische gestructureerde mededeling met juiste controlecijfers zegt wat ze betaalt, zodat je "
          "boekhouding ze zelf kan boeken. Een betaling zonder, of met foute controlecijfers, boekt iemand met de "
          "hand na uit te zoeken wat ze betaalt. Een andere referentie (bijvoorbeeld een RF-referentie) wordt niet "
          "nagekeken en apart geteld.",
    "fr": "Paiements entrants sur vos relevés bancaires camt.053, sans les prélèvements. Un paiement avec une "
          "communication structurée belge aux chiffres de contrôle corrects indique ce qu'il paie, votre "
          "comptabilité peut donc le comptabiliser seule. Un paiement sans communication, ou avec des chiffres de "
          "contrôle erronés, est comptabilisé à la main par quelqu'un qui cherche ce qu'il paie. Une autre "
          "référence (une référence RF, par exemple) n'est pas vérifiée et est comptée à part.",
}


def payments(bank, lang="en"):
    """Incoming payments by structured communication: valid, wrong check digits, another reference, none. The
    payments without a valid one are the ones a person books by hand."""
    lang = _lang(lang)
    groups = {g: {"count": 0, "cents": 0, "customers": {}} for g in PAYMENT_GROUPS}
    for b in bank:
        g = groups[b.get("ogm_status") if b.get("ogm_status") in groups else "absent"]
        g["count"] += 1
        g["cents"] += cents(b["amount"])
        if b.get("customer"):
            g["customers"][b["customer"]] = g["customers"].get(b["customer"], 0) + 1
    dates = [d for d in (parse_iso(b.get("date")) for b in bank) if d]
    months = months_spanned(dates)
    hand_n = sum(groups[g]["count"] for g in BY_HAND)
    hand_c = sum(groups[g]["cents"] for g in BY_HAND)
    hand_customers = {}
    for g in BY_HAND:
        for c, n in groups[g]["customers"].items():
            hand_customers[c] = hand_customers.get(c, 0) + n

    def ranked(counts):
        """Codes, most payments first."""
        return [c for c, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {
        "version": VERSION, "check": "unmatched-payments",
        "credit_lines": {"count": len(bank), "amount": euros(sum(cents(b["amount"]) for b in bank))},
        "period": {"from": str(min(dates)) if dates else None, "to": str(max(dates)) if dates else None,
                   "months": months},
        "groups": {g: {"count": v["count"], "amount": euros(v["cents"]), "customers": ranked(v["customers"])}
                   for g, v in groups.items()},
        "by_hand": {"count": hand_n, "amount": euros(hand_c),
                    "share_pct": round(100.0 * hand_n / len(bank), 1) if bank else None,
                    "per_month": round(hand_n / float(months), 1) if months else None,
                    "customers": ranked(hand_customers)},
        "method": PAYMENTS_METHOD[lang],
        "language": lang,
        "twikey": claims.line("unmatched-payments", lang),
    }


# --------------------------------------------------------------------------- manual steps

# The item types of the steps check, in the order of data/manual_steps.json, and what each is counted from.
STEP_ITEMS = ("failed_new_attempt", "failed_new_mandate", "failed_conversation", "failed_own_setup", "failed_unknown",
              "book_by_hand")
STEP_SOURCES = {
    "failed_new_attempt": "decode: reason category new_attempt",
    "failed_new_mandate": "decode: reason category new_mandate",
    "failed_conversation": "decode: reason category conversation",
    "failed_own_setup": "decode: reason category own_setup",
    "failed_unknown": "decode: reason categories bank, unknown and unreadable",
    "book_by_hand": "payments: no structured communication, or wrong check digits",
}


def manual_steps(lang="en"):
    """The labels, checklists and text lines of data/manual_steps.json in one language."""
    with open(os.path.join(DATA_DIR, "manual_steps.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data[lang if lang in ("en", "nl", "fr") else "en"]


def steps(collections, bank, on, lang="en"):
    """Per item type: how many items the statements hold, and the checklist of manual steps one item asks for when
    it is done by hand. Counted with the other checks: decode and payments."""
    lang = _lang(lang)
    dec = decode(collections, lang)
    pay = payments(bank, lang)
    copy_ = manual_steps(lang)
    cats = dec["by_category"]

    def failed(*names):
        sel = [cats[c] for c in names if c in cats]
        return (sum(c["count"] for c in sel), dec["period"]["months"],
                sorted({x for c in sel for x in c["customers"]}))

    counts = {
        "failed_new_attempt": failed("new_attempt"),
        "failed_new_mandate": failed("new_mandate"),
        "failed_conversation": failed("conversation"),
        "failed_own_setup": failed("own_setup"),
        "failed_unknown": failed("bank", "unknown", "unreadable"),
        "book_by_hand": (pay["by_hand"]["count"], pay["period"]["months"], pay["by_hand"]["customers"]),
    }
    items = []
    for k in STEP_ITEMS:
        n, months, customers = counts[k]
        months = months or None
        checklist = copy_["items"][k]["checklist"]
        items.append({"id": k, "label": copy_["items"][k]["label"], "label_one": copy_["items"][k]["label_one"],
                      "count": n, "months": months, "per_month": round(n / float(months), 1) if months else None,
                      "steps_each": len(checklist), "steps_total": n * len(checklist), "checklist": checklist,
                      "examples": customers[:12], "source": STEP_SOURCES[k]})
    # biggest steps_total first
    items.sort(key=lambda i: (-i["steps_total"], STEP_ITEMS.index(i["id"])))
    timed = [i for i in items if i["per_month"] is not None]
    return {
        "version": VERSION, "check": "manual-steps", "as_of": str(on), "language": lang,
        "items": items,
        "total_items": sum(i["count"] for i in items),
        "total_steps": sum(i["steps_total"] for i in items),
        # the per-month totals add up the exact per-month values, rounded once
        "per_month_total": round(sum(i["count"] / float(i["months"]) for i in timed), 1) if timed else None,
        "per_month_steps_total": (round(sum(i["steps_total"] / float(i["months"]) for i in timed), 1)
                                  if timed else None),
        "basis": copy_["text"]["basis"],
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


def golive(collections, bank, tool=None, lang="en"):
    """The facts for the go-live plan, from the camt.053 statements."""
    lang = _lang(lang)
    collected = [c for c in collections if c["status"] == "collected"]
    failed = [c for c in collections if c["status"] == "failed"]
    dd = {c["customer"] for c in collections if c.get("customer")}
    stats = day_stats(collections)
    cmonths = (stats["period"] or {}).get("months") or 0
    fmonths = months_spanned(parse_iso(c.get("date")) for c in failed)
    pay = payments(bank, lang)
    bmonths = pay["period"]["months"]
    out = {
        "version": VERSION, "check": "go-live-plan",
        "direct_debit_customers": len(dd),
        "mandates": len({c["mandate"] for c in collections if c.get("mandate")}),
        "core_customers": len({c["customer"] for c in collected if c.get("scheme") == "CORE" and c.get("customer")}),
        "b2b_customers": len({c["customer"] for c in collected if c.get("scheme") == "B2B" and c.get("customer")}),
        "collections_per_month": round(stats["overall"]["presented"] / float(cmonths), 1) if cmonths else None,
        "failed_per_month": round(len(failed) / float(fmonths), 1) if fmonths else None,
        "failure_rate_pct": stats["overall"]["rate_pct"],
        "payers_by_transfer": len({b["customer"] for b in bank if b.get("customer")} - dd),
        "transfers_per_month": round(len(bank) / float(bmonths), 1) if bmonths else None,
        "by_hand_per_month": pay["by_hand"]["per_month"],
        "questions": list(GOLIVE_QUESTIONS[lang]),
        "existing_mandates": EXISTING_MANDATES[lang],
        "twikey": [claims.line(i, lang) for i in GOLIVE_LINES],
        # Linked once, here: the packages named in the Twikey lines are on this page.
        "pricing_page": claims.page("pricing", lang),
        # The one call to action. The report ends with it. go-live-plan.md does not repeat it.
        "demo": claims.line("demo", lang),
    }
    if tool:
        out["tool"] = {"asked": tool, "listed_as": claims.partner_matches(tool),
                       "partners_page": claims.page("partners", lang)}
    return out
