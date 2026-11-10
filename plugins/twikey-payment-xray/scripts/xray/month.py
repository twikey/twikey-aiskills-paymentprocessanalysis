"""This month's work, prepared: collections worth a new attempt, with a suggested day, and customer mail drafts.

prepare() works on the coded ledger and returns codes, counts, amounts and dates only (twikey_xray.py writes it to
month.json in the workspace). render() lays out the same content as Markdown, still with codes. write_pack() puts
the names and numbers back with the key (report.decode_codes) and writes the work pack next to the raw exports.

Nothing is sent and no bank file is written. The work pack is one Markdown file for a person to read.
"""
import datetime as dt
import json
import os

from . import VERSION, checks, claims, reasons
from . import report as reportmod
from .common import DATA_DIR, MONTH_PREFIX, add_months, cents, euros, long_date, money, month_year, parse_iso, \
    pct, working_day
from . import common

DEFAULT_SINCE_DAYS = 90
# One mail per customer. With open debts of several reasons, the first reason in this order is the mail's reason,
# and the mail lists all of that customer's open debts.
MAIL_PRIORITY = ("conversation", "new_mandate", "b2b_register", "new_attempt")
MAIL_REASONS = MAIL_PRIORITY
# A new attempt whose customer's one mail asks for something first waits for it (the note in part 1).
WAIT_NOTE = {"conversation": "wait", "new_mandate": "wait_new_mandate", "b2b_register": "wait_b2b_register"}
RETRY_WINDOW_DAYS = checks.RETRY_WINDOW_DAYS
# The suggested date lies at least this many days after today: the usual SEPA pre-notification period.
NOTICE_DAYS = 14
# Only insufficient funds asks the customer to make sure there is money in the account.
FUNDS_CODES = ("AM04",)
CLOSED = ("collected_later", "paid_by_transfer")

TEXT = {
    "en": {
        "title": "This month's work, prepared",
        "as_of": "As of %s.",
        "s1": "1. Collections worth a new attempt", "s2": "2. Customer mail drafts",
        "window": "Failed in the last {days} days ({start} to {end}) with a reason worth a new attempt, and not "
                  "collected since. A collection presented again and failed again is one item, counted once.",
        "closed": "Left out because they are no longer owed: {n} (a later collection, or a payment by transfer "
                  "from that customer since).",
        "day": "Suggested day: day {day} of the month, next on {date}{moved}. Of the {qualifying} collection days "
               "with 20 collections or more over two months or more in your statements, day {day} has the lowest "
               "failure rate: {rate} ({presented} collections over {months} months, {failed} of them failed), "
               "against {overall} for all collections.",
        "notice": "At least 14 days from today, the usual SEPA pre-notification period. Check what your mandate "
                  "terms say.",
        "moved": " (moved to the next working day)",
        "no_day": "Too little history to suggest a day: that needs two collection days or more with 20 collections "
                  "or more each, over two months or more, in your statements.",
        "no_better_day": "No suggested day: no collection day in your statements fails less often than all "
                         "collections together.",
        "attempt": "- **{customer}**, mandate {mandate}: {amount}, {failed}. {code}: {meaning}. "
                   "New attempt: {new_date}.{note}",
        "failed_once": "failed on {date}", "failed_times": "failed {times}, last on {date}",
        "wait": " The mail in part 2 asks this customer how they would like to pay: wait for the answer before you "
                "present it again.",
        "wait_new_mandate": " The mail in part 2 asks this customer to sign a new mandate: present it again once it "
                            "is signed.",
        "wait_b2b_register": " The mail in part 2 asks this customer to have the B2B mandate registered at their "
                             "bank: present it again once that is done.",
        "also_new_mandate": "This customer also needs a new mandate (mandate {mandate}): add the request to sign one "
                            "to this mail.",
        "also_b2b_register": "B2B mandate {mandate} is not registered at this customer's bank: add the request to "
                             "register it to this mail.",
        "pick_day": "pick a day yourself", "none": "None.",
        "check": "Check each draft, then send it yourself. Nothing was sent.",
        "mails_window": "The drafts cover the failed collections of the last {days} days that are still open. Your "
                        "bank statements show what came in at the bank, not what your books say: check that each "
                        "amount is still owed before you send a draft.",
        "reason": {"new_attempt": "new attempt", "new_mandate": "new mandate needed",
                   "conversation": "how would you like to pay", "b2b_register": "register the B2B mandate"},
        "subject": "Subject",
        "twikey": "What Twikey does:",
        "closing": "Claude prepared this once, from your bank statements of {period}. Nothing was sent and no bank "
                   "file was written.",
        "closing_no_period": "Claude prepared this once, from your bank statements. Nothing was sent and no bank "
                             "file was written.",
        "period": "%s to %s", "and": "and", "zero": "none", "colon": ":",
        "basis": "failure rate per usual collection day of the month in your own statements: a collection presented "
                 "again after a failure is left out, a run moved by a weekend or bank holiday counts under its "
                 "usual day, and a day counts with 20 collections or more over two months or more",
    },
    "nl": {
        "title": "Het werk van deze maand, voorbereid",
        "as_of": "Stand op %s.",
        "s1": "1. Domiciliëringen die heraangeboden kunnen worden", "s2": "2. Conceptmails voor klanten",
        "window": "Mislukt in de laatste {days} dagen ({start} tot {end}) met een reden die heraanbieden waard "
                  "is, en sindsdien niet geïnd. Een domiciliëring die opnieuw aangeboden werd en opnieuw mislukte, "
                  "is één item en telt één keer.",
        "closed": "Weggelaten omdat ze niet meer verschuldigd zijn: {n} (een latere domiciliëring, of een betaling "
                  "per overschrijving van die klant sindsdien).",
        "day": "Voorgestelde dag: dag {day} van de maand, de volgende keer op {date}{moved}. Van de {qualifying} "
               "domiciliëringsdagen met 20 domiciliëringen of meer over twee maanden of meer in je afschriften heeft "
               "dag {day} het laagste percentage mislukte domiciliëringen: {rate} ({presented} domiciliëringen over "
               "{months} maanden, waarvan {failed} mislukt), tegenover {overall} voor alle domiciliëringen samen.",
        "notice": "Minstens 14 dagen na vandaag, de gebruikelijke SEPA-termijn voor de voorafgaande kennisgeving. "
                  "Kijk na wat je mandaatvoorwaarden zeggen.",
        "moved": " (verschoven naar de volgende werkdag)",
        "no_day": "Te weinig historiek om een dag voor te stellen: daarvoor zijn twee domiciliëringsdagen of meer "
                  "nodig met elk 20 domiciliëringen of meer, over twee maanden of meer, in je afschriften.",
        "no_better_day": "Geen voorgestelde dag: geen enkele domiciliëringsdag in je afschriften heeft een lager "
                         "percentage mislukte domiciliëringen dan alle domiciliëringen samen.",
        "attempt": "- **{customer}**, mandaat {mandate}: {amount}, {failed}. {code}: {meaning}. "
                   "Heraanbieden op: {new_date}.{note}",
        "failed_once": "mislukt op {date}", "failed_times": "{times} mislukt, laatst op {date}",
        "wait": " De mail in deel 2 vraagt deze klant hoe hij wil betalen: wacht het antwoord af voor je de "
                "domiciliëring heraanbiedt.",
        "wait_new_mandate": " De mail in deel 2 vraagt deze klant om een nieuw mandaat te tekenen: bied de "
                            "domiciliëring opnieuw aan zodra het getekend is.",
        "wait_b2b_register": " De mail in deel 2 vraagt deze klant om het B2B-mandaat bij zijn bank te laten "
                             "registreren: bied de domiciliëring opnieuw aan zodra dat gebeurd is.",
        "also_new_mandate": "Deze klant heeft ook een nieuw mandaat nodig (mandaat {mandate}): voeg de vraag om er "
                            "een te tekenen toe aan deze mail.",
        "also_b2b_register": "B2B-mandaat {mandate} is niet geregistreerd bij de bank van deze klant: voeg de vraag "
                             "om het te laten registreren toe aan deze mail.",
        "pick_day": "kies zelf een dag", "none": "Geen.",
        "check": "Kijk elk concept na en verstuur het dan zelf. Er is niets verstuurd.",
        "mails_window": "De concepten gaan over de mislukte domiciliëringen van de laatste {days} dagen die nog "
                        "openstaan. Je bankafschriften tonen wat er op de bank binnenkwam, niet wat je boekhouding "
                        "zegt: kijk na of elk bedrag nog verschuldigd is voor je een concept verstuurt.",
        "reason": {"new_attempt": "wordt heraangeboden", "new_mandate": "nieuw mandaat nodig",
                   "conversation": "hoe wil je betalen", "b2b_register": "B2B-mandaat laten registreren"},
        "subject": "Onderwerp",
        "twikey": "Wat Twikey doet:",
        "closing": "Claude heeft dit één keer voorbereid, uit je bankafschriften van {period}. Er is niets verstuurd "
                   "en er is geen bankbestand gemaakt.",
        "closing_no_period": "Claude heeft dit één keer voorbereid, uit je bankafschriften. Er is niets verstuurd en "
                             "er is geen bankbestand gemaakt.",
        "period": "%s tot %s", "and": "en", "zero": "geen", "colon": ":",
        "basis": "percentage mislukte domiciliëringen per gewone domiciliëringsdag van de maand in je eigen "
                 "afschriften: een domiciliëring die na een mislukking opnieuw aangeboden wordt telt niet mee, een "
                 "reeks die door een weekend of feestdag verschoven is telt op haar gewone dag, en een dag telt "
                 "mee met 20 domiciliëringen of meer over twee maanden of meer",
    },
    "fr": {
        "title": "Le travail du mois, préparé",
        "as_of": "Situation au %s.",
        "s1": "1. Prélèvements à présenter à nouveau", "s2": "2. Brouillons de mails aux clients",
        "window": "Échoués au cours des {days} derniers jours (du {start} au {end}) pour une raison qui vaut une "
                  "nouvelle présentation, et pas encaissés depuis. Un prélèvement présenté à nouveau et de nouveau "
                  "échoué est un seul élément, compté une fois.",
        "closed": "Laissés de côté parce qu'ils ne sont plus dus : {n} (un prélèvement ultérieur, ou un virement "
                  "de ce client depuis).",
        "day": "Jour proposé : le {day} du mois, la prochaine fois le {date}{moved}. Parmi les {qualifying} jours "
               "de prélèvement avec 20 prélèvements ou plus sur deux mois ou plus dans vos relevés, le {day} a le "
               "taux d'échec le plus bas : {rate} ({presented} prélèvements sur {months} mois, dont {failed} en "
               "échec), contre {overall} pour l'ensemble des prélèvements.",
        "notice": "Au moins 14 jours après aujourd'hui, le délai habituel de pré-notification SEPA. Vérifiez ce "
                  "que prévoient les conditions de vos mandats.",
        "moved": " (reporté au jour ouvrable suivant)",
        "no_day": "Trop peu d'historique pour proposer un jour : il faut au moins deux jours de prélèvement avec "
                  "chacun 20 prélèvements ou plus, sur deux mois ou plus, dans vos relevés.",
        "no_better_day": "Pas de jour proposé : aucun jour de prélèvement de vos relevés n'échoue moins souvent "
                         "que l'ensemble des prélèvements.",
        "attempt": "- **{customer}**, mandat {mandate} : {amount}, {failed}. {code} : {meaning}. "
                   "Nouvelle présentation : {new_date}.{note}",
        "failed_once": "échoué le {date}", "failed_times": "échoué {times}, la dernière fois le {date}",
        "wait": " Le mail de la partie 2 demande à ce client comment il souhaite payer : attendez sa réponse "
                "avant de présenter à nouveau le prélèvement.",
        "wait_new_mandate": " Le mail de la partie 2 demande à ce client de signer un nouveau mandat : présentez à "
                            "nouveau le prélèvement une fois le mandat signé.",
        "wait_b2b_register": " Le mail de la partie 2 demande à ce client de faire enregistrer le mandat B2B auprès "
                             "de sa banque : présentez à nouveau le prélèvement une fois que c'est fait.",
        "also_new_mandate": "Ce client a aussi besoin d'un nouveau mandat (mandat {mandate}) : ajoutez à ce mail la "
                            "demande d'en signer un.",
        "also_b2b_register": "Le mandat B2B {mandate} n'est pas enregistré auprès de la banque de ce client : ajoutez "
                             "à ce mail la demande de le faire enregistrer.",
        "pick_day": "jour à choisir vous-même", "none": "Aucun.",
        "check": "Vérifiez chaque brouillon, puis envoyez-le vous-même. Rien n'a été envoyé.",
        "mails_window": "Les brouillons couvrent les prélèvements échoués des {days} derniers jours encore ouverts. "
                        "Vos relevés bancaires montrent ce qui est arrivé à la banque, pas ce que dit votre "
                        "comptabilité : vérifiez que chaque montant est encore dû avant d'envoyer un brouillon.",
        "reason": {"new_attempt": "nouvelle présentation", "new_mandate": "nouveau mandat nécessaire",
                   "conversation": "comment souhaitez-vous payer", "b2b_register": "faire enregistrer le mandat B2B"},
        "subject": "Objet",
        "twikey": "Ce que fait Twikey :",
        "closing": "Claude a préparé ce travail une fois, à partir de vos relevés bancaires de {period}. Rien n'a "
                   "été envoyé et aucun fichier bancaire n'a été créé.",
        "closing_no_period": "Claude a préparé ce travail une fois, à partir de vos relevés bancaires. Rien n'a été "
                             "envoyé et aucun fichier bancaire n'a été créé.",
        "period": "%s à %s", "and": "et", "zero": "aucun", "colon": " :",
        "basis": "taux d'échec par jour de prélèvement habituel du mois dans vos propres relevés : un prélèvement "
                 "présenté à nouveau après un échec n'est pas compté, une série décalée par un week-end ou un jour "
                 "férié compte pour son jour habituel, et un jour compte avec 20 prélèvements ou plus sur deux mois "
                 "ou plus",
    },
}
WORDS = {"en": ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"],
         "nl": ["één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien"],
         "fr": ["un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"]}


def _lang(lang):
    return lang if lang in TEXT else "en"


def words(n, lang):
    """Zero to ten in words in prose, larger numbers in digits."""
    if n == 0:
        return TEXT[lang]["zero"]
    return WORDS[lang][n - 1] if 1 <= n <= 10 else str(n)


def join(items, lang_and):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return "%s %s %s" % (", ".join(items[:-1]), lang_and, items[-1])


def mail_templates(lang="en"):
    with open(os.path.join(DATA_DIR, "mail_templates.json"), encoding="utf-8") as f:
        return json.load(f)[_lang(lang)]


def times(n, mt):
    """'twice', 'drie keer', 'deux fois': how often a collection was presented."""
    return mt["times"][n] if 0 < n < len(mt["times"]) else mt["times_n"].format(n=n)


# --------------------------------------------------------------------------- dates

def next_day_of_month(day, after):
    """The first date after `after` that falls on this day of the month (months without that day are skipped)."""
    first = dt.date(after.year, after.month, 1)
    for k in range(0, 14):
        m = add_months(first, k)
        try:
            d = dt.date(m.year, m.month, day)
        except ValueError:
            continue
        if d > after:
            return d
    return None


def suggested_day(collections, on, today=None, lang="en"):
    """The usual collection day of the month with the lowest failure rate in the user's own data (checks.day_stats).

    A day qualifies with 20 collections or more over two months or more. A day is suggested only when two days or
    more qualify and the best one fails less often than all collections together. Its date is the first time that
    day comes on or after the later of the as-of date and today, plus 14 days (the usual SEPA pre-notification
    period), moved to a working day. Returns (the day or None, the day statistics)."""
    lang = _lang(lang)
    stats = checks.day_stats(collections)
    qual = {int(k): v for k, v in stats["days"].items() if v["qualifies"]}
    overall = stats["overall"]
    info = {"qualifying_days": sorted(qual), "overall_rate_pct": overall["rate_pct"],
            "overall_presented": overall["presented"], "overall_failed": overall["failed"],
            "retries_left_out": stats["retries_left_out"], "min_presented": checks.DAY_MIN_PRESENTED,
            "min_months": checks.DAY_MIN_MONTHS, "no_day_reason": None}
    if len(qual) < 2:
        info["no_day_reason"] = "too_little_history"
        return None, info
    day, r = min(qual.items(), key=lambda kv: (kv[1]["failed"] / float(kv[1]["presented"]), -kv[1]["presented"],
                                               kv[0]))
    if not r["failed"] * overall["presented"] < overall["failed"] * r["presented"]:
        info["no_day_reason"] = "no_better_day"
        return None, info
    earliest = max(on, today or common.today()) + dt.timedelta(days=NOTICE_DAYS)
    nxt = next_day_of_month(day, earliest - dt.timedelta(days=1))
    date = working_day(nxt)
    return ({"day": day, "rate_pct": r["rate_pct"], "months": r["months"], "failed": r["failed"],
             "presented": r["presented"], "date": str(date), "moved_to_working_day": date != nxt,
             "earliest": str(earliest), "overall_rate_pct": overall["rate_pct"], "qualifying_days": len(qual),
             "notice": TEXT[lang]["notice"], "basis": TEXT[lang]["basis"]}, info)


# --------------------------------------------------------------------------- the ledger

def debts(collections, on):
    """Failed collections up to the as-of date, one group per debt, oldest first. A failure and its new
    presentations that failed again (checks.same_debt: the same end-to-end reference, or the same mandate and
    amount within RETRY_WINDOW_DAYS of the last failure) are one debt, dated by its last failure."""
    failed = sorted((c for c in collections if c["status"] == "failed" and parse_iso(c.get("date"))
                     and parse_iso(c["date"]) <= on), key=lambda c: (c["date"], c.get("id") or ""))
    groups = []
    for f in failed:
        for g in groups:
            if any(checks.same_debt(x, f) for x in g):
                g.append(f)
                break
        else:
            groups.append([f])
    return groups


def collected_later(group, collected):
    """A later collection closes a debt when it carries the end-to-end reference of one of its failures, or the
    same mandate and amount within RETRY_WINDOW_DAYS of the last failure. The original presentation of a return has
    the same date, so it is never later. A regular collection of the same amount a month later is the next invoice,
    not this one."""
    last = group[-1]
    day = parse_iso(last.get("date"))
    e2es = {f["e2e"] for f in group if f.get("e2e")}
    for c in collected:
        d = parse_iso(c.get("date"))
        if not d or d <= day:
            continue
        if c.get("e2e") and c["e2e"] in e2es:
            return True
        if checks.same_debt(last, c):
            return True
    return False


def month_category(f, codes):
    """The reason category of a failure. On a B2B mandate, a code that means the debtor's bank does not know the
    mandate (checks.B2B_REGISTER_CODES) asks the customer to register it at their bank: b2b_register."""
    code = f.get("reason_code") or None
    if code in checks.B2B_REGISTER_CODES and f.get("scheme") == "B2B":
        return "b2b_register"
    return checks.category(code, f.get("scheme"), codes)


def open_failures(collections, bank, on, since_days, codes):
    """The open debts whose last failure lies in the window, oldest first, with their category.

    Closed (not listed) when the money came in another way: collected later (collected_later), or a later payment
    by transfer from that customer covers the amount (each payment covers one debt at most).

    A debt worth a new attempt on a mandate that later got MD01 needs a new mandate first (a later MD01 on a B2B
    mandate: the customer registers it at their bank)."""
    since = on - dt.timedelta(days=since_days)
    collected = [c for c in collections if c["status"] == "collected"]
    groups = [g for g in debts(collections, on) if since <= parse_iso(g[-1]["date"]) <= on]
    credits = [{"date": b.get("date"), "customer": b.get("customer"), "line": b.get("id") or "",
                "left": cents(b["amount"])} for b in bank if b.get("customer")]
    later_md01 = {}
    for c in collections:
        if c["status"] == "failed" and c.get("reason_code") in checks.B2B_REGISTER_CODES and c.get("mandate") \
                and parse_iso(c.get("date")) and parse_iso(c["date"]) <= on:
            later_md01.setdefault(c["mandate"], []).append(c)
    out, closed = [], {k: 0 for k in CLOSED}
    for g in groups:
        last = g[-1]
        why = None
        if collected_later(g, collected):
            why = "collected_later"
        owed = cents(last["amount"])
        if not why and last.get("customer"):
            day = parse_iso(last["date"])
            for line in sorted(credits, key=lambda x: (x["date"] or "", x["line"])):
                d = parse_iso(line.get("date"))
                if line["customer"] == last["customer"] and d and d > day and line["left"] >= owed:
                    line["left"] -= owed
                    why = "paid_by_transfer"
                    break
        if why:
            closed[why] += 1
            continue
        cat = month_category(last, codes)
        moved = None
        if cat == "new_attempt":
            md01 = [c for c in later_md01.get(last.get("mandate"), []) if parse_iso(c["date"]) > parse_iso(last["date"])]
            if md01:
                cat = "b2b_register" if md01[-1].get("scheme") == "B2B" else "new_mandate"
                moved = "md01_later"
        out.append({"failure": last, "first": g[0], "attempts": len(g), "category": cat,
                    "moved_from_new_attempt": moved})
    return out, closed


def meaning(code, codes):
    r = codes.get(code or "")
    if r:
        return checks._clean(r["DESC"])
    return reasons.EPC_SDD.get(code or "")


def _period(collections, bank):
    days = [parse_iso(c.get("date")) for c in collections] + [parse_iso(b.get("date")) for b in bank]
    days = [d for d in days if d]
    return {"from": str(min(days)), "to": str(max(days))} if days else {"from": None, "to": None}


# --------------------------------------------------------------------------- mails

def fill(template, values, many=False):
    """The draft for one debt, or with body_many and subject_many for several (where the template has them)."""
    body = template["body_many"] if many and "body_many" in template else template["body"]
    subject = template["subject_many"] if many and "subject_many" in template else template["subject"]
    return {"subject": subject.format(**values), "body": "\n".join(body).format(**values)}


def item_lines(items, mt, mail_lang):
    lines = []
    for it in items:
        f = it["failure"]
        amount = money(f["amount"], lang=mail_lang)
        date = long_date(f.get("date"), mail_lang)
        if it["attempts"] > 1:
            lines.append(mt["item_repeat"].format(amount=amount, date=date, times=times(it["attempts"], mt)))
        else:
            lines.append(mt["item"].format(amount=amount, date=date))
    return "\n".join(lines)


def build_mails(items, day, mail_lang):
    """One draft per customer. Its reason is the first of MAIL_PRIORITY among the customer's open debts, and it
    lists all of them."""
    mt = mail_templates(mail_lang)
    groups = {}
    for it in items:
        cust = it["failure"].get("customer")
        if cust and it["category"] in MAIL_REASONS:
            groups.setdefault(cust, []).append(it)
    mails = []
    for cust, group in sorted(groups.items()):
        reason = next(r for r in MAIL_PRIORITY if any(g["category"] == r for g in group))
        template = reason
        if reason == "new_attempt" and not any(g["failure"].get("reason_code") in FUNDS_CODES for g in group):
            template = "new_attempt_neutral"
        total = euros(sum(cents(g["failure"]["amount"]) for g in group))
        # the mandate the mail names: for b2b_register only the mandates the customer's bank does not know
        named = [g for g in group if g["category"] == reason] if reason == "b2b_register" else group
        mandates = sorted({g["failure"]["mandate"] for g in named if g["failure"].get("mandate")})
        values = {"customer": cust, "items": item_lines(group, mt, mail_lang), "amount": money(total, lang=mail_lang),
                  "new_date": long_date(day["date"], mail_lang) if day else mt["new_date_unknown"],
                  "company": mt["company"], "mandate": join(mandates, mt["and"]) or mt["mandate_unknown"]}
        mail = fill(mt["templates"][template], values, many=len(group) > 1)
        mails.append({"customer": cust, "reason": reason, "template": template, "subject": mail["subject"],
                      "body": mail["body"], "amount": total, "failure_dates": [g["failure"].get("date") for g in group],
                      "items": [{"mandate": g["failure"].get("mandate"), "amount": g["failure"]["amount"],
                                 "failure_date": g["failure"].get("date"), "attempts": g["attempts"],
                                 "reason_code": g["failure"].get("reason_code"), "category": g["category"]}
                                for g in group]})
    return mails


# --------------------------------------------------------------------------- prepare

def prepare(collections, bank, on, since_days=DEFAULT_SINCE_DAYS, lang="en", mail_lang=None, today=None):
    lang = _lang(lang)
    mail_lang = _lang(mail_lang or lang)
    codes = checks.rcodes(lang)
    day, day_info = suggested_day(collections, on, today, lang)
    items, closed = open_failures(collections, bank, on, since_days, codes)
    mails = build_mails(items, day, mail_lang)
    mail_reason = {m["customer"]: m["reason"] for m in mails}

    attempts = []
    for it in items:
        if it["category"] != "new_attempt":
            continue
        f = it["failure"]
        code = f.get("reason_code")
        attempts.append({"customer": f.get("customer"), "mandate": f.get("mandate"), "amount": f["amount"],
                         "failure_date": f.get("date"), "first_failure_date": it["first"].get("date"),
                         "attempts": it["attempts"], "reason_code": code, "meaning": meaning(code, codes),
                         "page": checks.RCODE_PAGE[lang] % code if code in codes else None,
                         "new_date": day["date"] if day else None,
                         "mail_reason": mail_reason.get(f.get("customer"))})

    period = _period(collections, bank)
    t = TEXT[lang]
    closing = (t["closing"].format(period=t["period"] % (month_year(period["from"], lang),
                                                         month_year(period["to"], lang)))
               if period["from"] else t["closing_no_period"])
    return {
        "version": VERSION, "check": "month", "as_of": str(on), "since_days": since_days,
        "period": period, "window": {"from": str(on - dt.timedelta(days=since_days)), "to": str(on)},
        "language": lang, "mail_language": mail_lang,
        "counts": {"new_attempts": len(attempts), "mails": len(mails)},
        "new_attempts": attempts,
        "closed": closed,
        "suggested_day": day,
        "day_statistics": day_info,
        "mails": mails,
        "closing": {"text": closing,
                    "twikey": [claims.line("failure-decoder", lang), claims.line("unmatched-payments", lang)],
                    "demo": claims.line("demo", lang)},
        "method": ("A failure counts when its last failure is from the last %d days and it is still open. A "
                   "collection presented again and failed again is one debt: the same end-to-end reference, or the "
                   "same mandate and amount within %d days. It is closed by a later collection with the same "
                   "end-to-end reference, or with the same mandate and amount within %d days, or when a later "
                   "payment by transfer from that customer covers the amount."
                   % (since_days, RETRY_WINDOW_DAYS, RETRY_WINDOW_DAYS)),
    }


# --------------------------------------------------------------------------- the work pack

def _quote(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def render(data, today=None):
    """The work pack as Markdown, with codes. write_pack() puts the names back."""
    lang = data["language"]
    t = TEXT[lang]
    mt = mail_templates(lang)
    today = today or common.today()

    def d(v):
        return long_date(v, lang)

    p = ["# %s" % t["title"], "", t["as_of"] % d(data["as_of"]), "",
         reportmod.TEXT[lang]["made"] % (long_date(today, lang), VERSION), ""]

    # 1. new attempts
    w = data["window"]
    p += ["## %s" % t["s1"], "", t["window"].format(days=data["since_days"], start=d(w["from"]), end=d(w["to"])), ""]
    closed = sum((data.get("closed") or {}).values())
    if closed:
        p += [t["closed"].format(n=words(closed, lang)), ""]
    day = data["suggested_day"]
    if day:
        p += [t["day"].format(day=day["day"], date=d(day["date"]), moved=t["moved"] if day["moved_to_working_day"]
                              else "", rate=pct(day["rate_pct"], lang), failed=words(day["failed"], lang),
                              presented=words(day["presented"], lang), months=words(day["months"], lang),
                              qualifying=words(day["qualifying_days"], lang),
                              overall=pct(day["overall_rate_pct"], lang)) + " " + day["notice"], ""]
    else:
        why = (data.get("day_statistics") or {}).get("no_day_reason")
        p += [t["no_better_day"] if why == "no_better_day" else t["no_day"], ""]
    for a in data["new_attempts"]:
        failed = (t["failed_times"].format(times=times(a["attempts"], mt), date=d(a["failure_date"]))
                  if a.get("attempts", 1) > 1 else t["failed_once"].format(date=d(a["failure_date"])))
        p.append(t["attempt"].format(customer=a["customer"] or "-", mandate=a["mandate"] or "-",
                                     amount=money(a["amount"], lang=lang), failed=failed,
                                     code=a["reason_code"] or "-", meaning=a["meaning"] or "-",
                                     new_date=d(a["new_date"]) if a["new_date"] else t["pick_day"],
                                     note=t[WAIT_NOTE[a["mail_reason"]]] if a.get("mail_reason") in WAIT_NOTE
                                     else ""))
    if not data["new_attempts"]:
        p.append(t["none"])
    p.append("")

    # 2. mails
    p += ["## %s" % t["s2"], "", t["check"] + " " + t["mails_window"].format(days=data["since_days"]), ""]
    for mail in data["mails"]:
        p += ["### %s%s %s" % (mail["customer"], t["colon"], t["reason"][mail["reason"]]), "",
              "**%s%s** %s" % (t["subject"], t["colon"], mail["subject"]), "", _quote(mail["body"]), ""]
        # a conversation mail also covers debts that need a new mandate or a B2B registration: say what to add
        if mail["reason"] == "conversation":
            for cat in ("new_mandate", "b2b_register"):
                mandates = sorted({i["mandate"] for i in mail.get("items") or []
                                   if i.get("category") == cat and i.get("mandate")})
                if any(i.get("category") == cat for i in mail.get("items") or []):
                    p += [t["also_" + cat].format(mandate=join(mandates, t["and"]) or "-"), ""]
    if not data["mails"]:
        p += [t["none"], ""]

    # closing
    c = data["closing"]
    p += ["---", "", c["text"], "", t["twikey"], ""]
    p += ["- %s" % claims.render(x, label=False) for x in c["twikey"]]
    p += ["", c["demo"]["text"], "", "---", "", reportmod.TEXT[lang]["footer"] % VERSION, ""]
    return "\n".join(p)


def write_pack(raw_dir, data, key, today=None):
    """Write the work pack next to the raw exports, with the names and numbers put back. Returns its path."""
    text = reportmod.decode_codes(render(data, today), key, data["language"])
    path = reportmod.unique_path(raw_dir, parse_iso(data["as_of"]), MONTH_PREFIX)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
