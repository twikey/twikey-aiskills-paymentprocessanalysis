"""This month's work, prepared: collections worth a new attempt, customer mail drafts, mandates to renew and
match suggestions.

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
from .common import (DATA_DIR, MONTH_PREFIX, add_months, cents, cents_known, closing_days, euros, long_date,  # noqa
                     money, month_year, parse_iso, pct, working_day)
from . import common

DEFAULT_SINCE_DAYS = 90
# One mail per customer. With open debts of several reasons, the first reason in this order is the mail's reason,
# and the mail lists all of that customer's open debts.
MAIL_PRIORITY = ("conversation", "new_mandate", "b2b_register", "new_attempt")
MAIL_REASONS = MAIL_PRIORITY
# A new attempt whose customer's one mail asks for something first waits for it (the note in part 1).
WAIT_NOTE = {"conversation": "wait", "new_mandate": "wait_new_mandate", "b2b_register": "wait_b2b_register"}
STRENGTHS = ("structured_communication", "same_customer_same_amount", "amount_only")
MAX_CANDIDATES = 3
# A failed collection belongs to an invoice of the same customer and amount whose due date lies on or up to this
# many days before the failure date. With two such invoices on the same latest due date, it is not known.
INVOICE_WINDOW_DAYS = 31
RETRY_WINDOW_DAYS = checks.RETRY_WINDOW_DAYS
# The suggested date lies at least this many days after today: the usual SEPA pre-notification period.
NOTICE_DAYS = 14
# Only insufficient funds asks the customer to make sure there is money in the account.
FUNDS_CODES = ("AM04",)
SKIP_CATEGORIES = ("partial", "unmatched")  # bank lines that get match suggestions
TAKEN = ("paid_but_open", "bundled", "double", "overpaid")  # their invoices are settled at the bank already
CLOSED = ("collected_later", "invoice_closed", "paid_at_bank", "bank_credit")

TEXT = {
    "en": {
        "title": "This month's work, prepared",
        "as_of": "As of %s.",
        "s1": "1. Collections worth a new attempt", "s2": "2. Customer mail drafts", "s3": "3. Mandates to renew",
        "s4": "4. Match suggestions", "s5": "Paid, still open in your books", "s6": "Paid twice",
        "window": "Failed in the last {days} days ({start} to {end}) with a reason worth a new attempt, and not "
                  "collected since. A collection presented again and failed again is one item, counted once.",
        "closed": "Left out because they are no longer owed: {n} (a later collection, a payment at the bank, or "
                  "the invoice is closed in your books).",
        "day": "Suggested day: day {day} of the month, next on {date}{moved}. Of the {qualifying} collection days "
               "with 20 collections or more over two months or more in your files, day {day} has the lowest failure "
               "rate: {rate} ({presented} collections over {months} months, {failed} of them failed), against "
               "{overall} for all collections.",
        "notice": "At least 14 days from today, the usual SEPA pre-notification period. Check what your mandate "
                  "terms say.",
        "moved": " (moved to the next working day)",
        "no_day": "Too little history to suggest a day: that needs two collection days or more with 20 collections "
                  "or more each, over two months or more, in your files.",
        "no_better_day": "No suggested day: no collection day in your files fails less often than all collections "
                         "together.",
        "attempt": "- **{customer}**, mandate {mandate}{invoice}: {amount}, {failed}. {code}: {meaning}. "
                   "New attempt: {new_date}.{note}",
        "failed_once": "failed on {date}", "failed_times": "failed {times}, last on {date}",
        "open_of": "{open} of {amount} still open",
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
        "invoice": ", invoice %s", "pick_day": "pick a day yourself", "none": "None.",
        "check": "Check each draft, then send it yourself. Nothing was sent.",
        "mails_window": "The drafts cover the failed collections of the last {days} days that are still open.",
        "older": "Older failed collections whose invoice is still open in your books, from before {start}: {n}. They "
                 "are not in these drafts. Ask Claude to prepare this again with a longer window to add them.",
        "no_invoice": " No invoice found for it in your export: check in your books that the amount is still owed.",
        "no_invoice_mail": "No invoice was found in your export for a collection in this mail: check in your books "
                           "that the amount is still owed before you send it.",
        "reason": {"new_attempt": "new attempt", "new_mandate": "new mandate needed",
                   "conversation": "how would you like to pay", "b2b_register": "register the B2B mandate"},
        "subject": "Subject",
        "expired": "- **{customer}**, mandate {mandate}: expired on {expiry}, 36 months after the last collection "
                   "presented on it ({base}).",
        "expired_after": "- **{customer}**, mandate {mandate}: expired on {expiry}, 36 months after the last "
                         "collection presented on it before then ({base}).",
        "after_one_failed": " A collection was presented on it after that, on {last}, and failed.",
        "after_one_ok": " A collection was presented on it after that, on {last}, and went through.",
        "after_many": " {n} collections were presented on it after that, the last on {last}, {failed} of them "
                      "failed.",
        "expiring": "- **{customer}**, mandate {mandate}: expires on {expiry}, 36 months after the last collection "
                    "presented on it ({base}).",
        "active": " Still active: an open invoice or a collection in the last 12 months.",
        "inactive": " No open invoice and no collection in the last 12 months.",
        "keep_valid": " A collection on it before {expiry} keeps it valid, so there is no renewal mail.",
        "no_mail": " Not expired yet, so there is no renewal mail.",
        "renew_heading": "%s, mandate %s",
        "covered": "No separate draft: the mail in part 2 already asks this customer to sign a new mandate.",
        "covered_other": "No separate draft, so this customer gets one mail: add the request to sign a new mandate "
                         "to the mail in part 2.",
        "match_intro": "Suggestions, not matches. Check each one before you book it.",
        "payment": "- Payment of {amount} on {date} from **{customer}**: {candidates}.",
        "candidate": "invoice {invoice} of {customer} ({strength})", "or": " or ",
        "partial_rest": " {paid} paid, {open} still open on invoice {invoice}.",
        "unknown_payer": "an unknown payer",
        "strength": {"structured_communication": "the structured communication names this invoice",
                     "same_customer_same_amount": "the payer's only open invoice with this amount",
                     "amount_only": "the only open invoice with this amount, check before you book"},
        "without": "Payments without a candidate: %s.",
        "double_intro": "Contact the customer, then refund or credit the amount and record it.",
        "double": "- Payment of {amount} on {date} from **{customer}** pays invoice {invoice} a second time.",
        "close": "Close these invoices in your books:",
        "paid_open": "- Invoice {invoice} of **{customer}**: {amount}, paid on {date}.",
        "twikey": "What Twikey does:",
        "closing": "Claude prepared this once, from your exports of {period}. Nothing was sent and no bank file "
                   "was written.",
        "closing_no_period": "Claude prepared this once, from your exports. Nothing was sent and no bank file was "
                             "written.",
        "period": "%s to %s", "and": "and", "zero": "none", "colon": ":",
        "basis": "failure rate per usual collection day of the month in your own files: a collection presented "
                 "again after a failure is left out, a run moved by a weekend or bank holiday counts under its "
                 "usual day, and a day counts with 20 collections or more over two months or more",
    },
    "nl": {
        "title": "Het werk van deze maand, voorbereid",
        "as_of": "Stand op %s.",
        "s1": "1. Domiciliëringen die heraangeboden kunnen worden", "s2": "2. Conceptmails voor klanten",
        "s3": "3. Te vernieuwen mandaten", "s4": "4. Koppelvoorstellen", "s5": "Betaald, nog open in je boekhouding",
        "s6": "Dubbel betaald",
        "window": "Mislukt in de laatste {days} dagen ({start} tot {end}) met een reden die heraanbieden waard "
                  "is, en sindsdien niet geïnd. Een domiciliëring die opnieuw aangeboden werd en opnieuw mislukte, "
                  "is één item en telt één keer.",
        "closed": "Weggelaten omdat ze niet meer verschuldigd zijn: {n} (een latere domiciliëring, een betaling op "
                  "de bank, of de factuur is afgesloten in je boekhouding).",
        "day": "Voorgestelde dag: dag {day} van de maand, de volgende keer op {date}{moved}. Van de {qualifying} "
               "domiciliëringsdagen met 20 domiciliëringen of meer over twee maanden of meer in je bestanden heeft "
               "dag {day} het laagste percentage mislukte domiciliëringen: {rate} ({presented} domiciliëringen over "
               "{months} maanden, waarvan {failed} mislukt), tegenover {overall} voor alle domiciliëringen samen.",
        "notice": "Minstens 14 dagen na vandaag, de gebruikelijke SEPA-termijn voor de voorafgaande kennisgeving. "
                  "Kijk na wat je mandaatvoorwaarden zeggen.",
        "moved": " (verschoven naar de volgende werkdag)",
        "no_day": "Te weinig historiek om een dag voor te stellen: daarvoor zijn twee domiciliëringsdagen of meer "
                  "nodig met elk 20 domiciliëringen of meer, over twee maanden of meer, in je bestanden.",
        "no_better_day": "Geen voorgestelde dag: geen enkele domiciliëringsdag in je bestanden heeft een lager "
                         "percentage mislukte domiciliëringen dan alle domiciliëringen samen.",
        "attempt": "- **{customer}**, mandaat {mandate}{invoice}: {amount}, {failed}. {code}: {meaning}. "
                   "Heraanbieden op: {new_date}.{note}",
        "failed_once": "mislukt op {date}", "failed_times": "{times} mislukt, laatst op {date}",
        "open_of": "{open} van {amount} staat nog open",
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
        "invoice": ", factuur %s", "pick_day": "kies zelf een dag", "none": "Geen.",
        "check": "Kijk elk concept na en verstuur het dan zelf. Er is niets verstuurd.",
        "mails_window": "De concepten gaan over de mislukte domiciliëringen van de laatste {days} dagen die nog "
                        "openstaan.",
        "older": "Oudere mislukte domiciliëringen waarvan de factuur nog openstaat in je boekhouding, van vóór {start}: "
                 "{n}. Ze staan niet in deze concepten. Vraag Claude om dit opnieuw voor te bereiden over een langere "
                 "periode om ze toe te voegen.",
        "no_invoice": " Geen factuur gevonden in je export: kijk in je boekhouding na of het bedrag nog verschuldigd "
                      "is.",
        "no_invoice_mail": "Voor een domiciliëring in deze mail is geen factuur gevonden in je export: kijk in je "
                           "boekhouding na of het bedrag nog verschuldigd is voor je de mail verstuurt.",
        "reason": {"new_attempt": "wordt heraangeboden", "new_mandate": "nieuw mandaat nodig",
                   "conversation": "hoe wil je betalen", "b2b_register": "B2B-mandaat laten registreren"},
        "subject": "Onderwerp",
        "expired": "- **{customer}**, mandaat {mandate}: verlopen op {expiry}, 36 maanden na de laatste "
                   "domiciliëring die op dit mandaat aangeboden werd ({base}).",
        "expired_after": "- **{customer}**, mandaat {mandate}: verlopen op {expiry}, 36 maanden na de laatste "
                         "domiciliëring die daarvoor op dit mandaat aangeboden werd ({base}).",
        "after_one_failed": " Daarna werd er nog een domiciliëring op dit mandaat aangeboden, op {last}, en die "
                            "mislukte.",
        "after_one_ok": " Daarna werd er nog een domiciliëring op dit mandaat aangeboden, op {last}, en die is "
                        "gelukt.",
        "after_many": " Daarna werden er nog {n} domiciliëringen op dit mandaat aangeboden, de laatste op {last}, "
                      "waarvan {failed} mislukt.",
        "expiring": "- **{customer}**, mandaat {mandate}: verloopt op {expiry}, 36 maanden na de laatste "
                    "domiciliëring die op dit mandaat aangeboden werd ({base}).",
        "active": " Nog actief: een open factuur of een domiciliëring in de laatste 12 maanden.",
        "inactive": " Geen open factuur en geen domiciliëring in de laatste 12 maanden.",
        "keep_valid": " Een domiciliëring op dit mandaat vóór {expiry} houdt het geldig, dus geen mail om het te "
                      "vernieuwen.",
        "no_mail": " Nog niet verlopen, dus geen mail om het te vernieuwen.",
        "renew_heading": "%s, mandaat %s",
        "covered": "Geen apart concept: de mail in deel 2 vraagt deze klant al om een nieuw mandaat te tekenen.",
        "covered_other": "Geen apart concept, zodat deze klant één mail krijgt: voeg de vraag om een nieuw mandaat "
                         "te tekenen toe aan de mail in deel 2.",
        "match_intro": "Voorstellen, geen koppelingen. Kijk elk voorstel na voor je het boekt.",
        "payment": "- Betaling van {amount} op {date} van **{customer}**: {candidates}.",
        "candidate": "factuur {invoice} van {customer} ({strength})", "or": " of ",
        "partial_rest": " {paid} betaald, {open} staat nog open op factuur {invoice}.",
        "unknown_payer": "een onbekende betaler",
        "strength": {"structured_communication": "de gestructureerde mededeling noemt deze factuur",
                     "same_customer_same_amount": "de enige open factuur van de betaler met dit bedrag",
                     "amount_only": "de enige open factuur met dit bedrag, kijk na voor je boekt"},
        "without": "Betalingen zonder voorstel: %s.",
        "double_intro": "Neem contact op met de klant, betaal het bedrag terug of crediteer het, en leg het vast.",
        "double": "- Betaling van {amount} op {date} van **{customer}**: factuur {invoice} een tweede keer betaald.",
        "close": "Sluit deze facturen af in je boekhouding:",
        "paid_open": "- Factuur {invoice} van **{customer}**: {amount}, betaald op {date}.",
        "twikey": "Wat Twikey doet:",
        "closing": "Claude heeft dit één keer voorbereid, uit je exports van {period}. Er is niets verstuurd en er "
                   "is geen bankbestand gemaakt.",
        "closing_no_period": "Claude heeft dit één keer voorbereid, uit je exports. Er is niets verstuurd en er is "
                             "geen bankbestand gemaakt.",
        "period": "%s tot %s", "and": "en", "zero": "geen", "colon": ":",
        "basis": "percentage mislukte domiciliëringen per gewone domiciliëringsdag van de maand in je eigen "
                 "bestanden: een domiciliëring die na een mislukking opnieuw aangeboden wordt telt niet mee, een "
                 "reeks die door een weekend of feestdag verschoven is telt op haar gewone dag, en een dag telt "
                 "mee met 20 domiciliëringen of meer over twee maanden of meer",
    },
    "fr": {
        "title": "Le travail du mois, préparé",
        "as_of": "Situation au %s.",
        "s1": "1. Prélèvements à présenter à nouveau", "s2": "2. Brouillons de mails aux clients",
        "s3": "3. Mandats à renouveler", "s4": "4. Suggestions de rapprochement",
        "s5": "Payées, encore ouvertes dans votre comptabilité", "s6": "Payées deux fois",
        "window": "Échoués au cours des {days} derniers jours (du {start} au {end}) pour une raison qui vaut une "
                  "nouvelle présentation, et pas encaissés depuis. Un prélèvement présenté à nouveau et de nouveau "
                  "échoué est un seul élément, compté une fois.",
        "closed": "Laissés de côté parce qu'ils ne sont plus dus : {n} (un prélèvement ultérieur, un "
                  "paiement à la banque, ou la facture est clôturée dans votre comptabilité).",
        "day": "Jour proposé : le {day} du mois, la prochaine fois le {date}{moved}. Parmi les {qualifying} jours "
               "de prélèvement avec 20 prélèvements ou plus sur deux mois ou plus dans vos fichiers, le {day} a le "
               "taux d'échec le plus bas : {rate} ({presented} prélèvements sur {months} mois, dont {failed} en "
               "échec), contre {overall} pour l'ensemble des prélèvements.",
        "notice": "Au moins 14 jours après aujourd'hui, le délai habituel de pré-notification SEPA. Vérifiez ce "
                  "que prévoient les conditions de vos mandats.",
        "moved": " (reporté au jour ouvrable suivant)",
        "no_day": "Trop peu d'historique pour proposer un jour : il faut au moins deux jours de prélèvement avec "
                  "chacun 20 prélèvements ou plus, sur deux mois ou plus, dans vos fichiers.",
        "no_better_day": "Pas de jour proposé : aucun jour de prélèvement de vos fichiers n'échoue moins souvent "
                         "que l'ensemble des prélèvements.",
        "attempt": "- **{customer}**, mandat {mandate}{invoice} : {amount}, {failed}. {code} : {meaning}. "
                   "Nouvelle présentation : {new_date}.{note}",
        "failed_once": "échoué le {date}", "failed_times": "échoué {times}, la dernière fois le {date}",
        "open_of": "{open} sur {amount} encore ouverts",
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
        "invoice": ", facture %s", "pick_day": "jour à choisir vous-même", "none": "Aucun.",
        "check": "Vérifiez chaque brouillon, puis envoyez-le vous-même. Rien n'a été envoyé.",
        "mails_window": "Les brouillons couvrent les prélèvements échoués des {days} derniers jours encore ouverts.",
        "older": "Prélèvements échoués plus anciens dont la facture est encore ouverte dans votre comptabilité, d'avant "
                 "le {start}, absents de ces brouillons : {n}. Pour les ajouter, demandez à Claude de préparer à "
                 "nouveau ce travail sur une période plus longue.",
        "no_invoice": " Aucune facture trouvée pour ce prélèvement dans votre export : vérifiez dans votre "
                      "comptabilité que le montant est encore dû.",
        "no_invoice_mail": "Aucune facture n'a été trouvée dans votre export pour un prélèvement de ce mail : vérifiez "
                           "dans votre comptabilité que le montant est encore dû avant de l'envoyer.",
        "reason": {"new_attempt": "nouvelle présentation", "new_mandate": "nouveau mandat nécessaire",
                   "conversation": "comment souhaitez-vous payer", "b2b_register": "faire enregistrer le mandat B2B"},
        "subject": "Objet",
        "expired": "- **{customer}**, mandat {mandate} : a expiré le {expiry}, 36 mois après le dernier prélèvement "
                   "présenté sur ce mandat ({base}).",
        "expired_after": "- **{customer}**, mandat {mandate} : a expiré le {expiry}, 36 mois après le dernier "
                         "prélèvement présenté sur ce mandat avant cette date ({base}).",
        "after_one_failed": " Un prélèvement a encore été présenté sur ce mandat ensuite, le {last}, et il a échoué.",
        "after_one_ok": " Un prélèvement a encore été présenté sur ce mandat ensuite, le {last}, et il est passé.",
        "after_many": " {n} prélèvements ont encore été présentés sur ce mandat ensuite, le dernier le {last}, dont "
                      "{failed} en échec.",
        "expiring": "- **{customer}**, mandat {mandate} : expire le {expiry}, 36 mois après le dernier prélèvement "
                    "présenté sur ce mandat ({base}).",
        "active": " Toujours actif : une facture ouverte ou un prélèvement au cours des 12 derniers mois.",
        "inactive": " Aucune facture ouverte et aucun prélèvement au cours des 12 derniers mois.",
        "keep_valid": " Un prélèvement sur ce mandat avant le {expiry} le garde valable, donc pas de mail de "
                      "renouvellement.",
        "no_mail": " Pas encore expiré, donc pas de mail de renouvellement.",
        "renew_heading": "%s, mandat %s",
        "covered": "Pas de brouillon séparé : le mail de la partie 2 demande déjà à ce client de signer un nouveau "
                   "mandat.",
        "covered_other": "Pas de brouillon séparé, pour que ce client reçoive un seul mail : ajoutez la demande de "
                         "signer un nouveau mandat au mail de la partie 2.",
        "match_intro": "Des suggestions, pas des rapprochements. Vérifiez chacune avant de la comptabiliser.",
        "payment": "- Paiement de {amount} le {date} de **{customer}** : {candidates}.",
        "candidate": "facture {invoice} de {customer} ({strength})", "or": " ou ",
        "partial_rest": " {paid} payés, {open} restent ouverts sur la facture {invoice}.",
        "unknown_payer": "un payeur inconnu",
        "strength": {"structured_communication": "la communication structurée désigne cette facture",
                     "same_customer_same_amount": "la seule facture ouverte du payeur avec ce montant",
                     "amount_only": "la seule facture ouverte avec ce montant, à vérifier avant de comptabiliser"},
        "without": "Paiements sans suggestion : %s.",
        "double_intro": "Contactez le client, puis remboursez ou créditez le montant et enregistrez-le.",
        "double": "- Paiement de {amount} le {date} de **{customer}** : deuxième paiement de la facture {invoice}.",
        "close": "Clôturez ces factures dans votre comptabilité :",
        "paid_open": "- Facture {invoice} de **{customer}** : {amount}, payée le {date}.",
        "twikey": "Ce que fait Twikey :",
        "closing": "Claude a préparé ce travail une fois, à partir de vos exports de {period}. Rien n'a été envoyé "
                   "et aucun fichier bancaire n'a été créé.",
        "closing_no_period": "Claude a préparé ce travail une fois, à partir de vos exports. Rien n'a été envoyé et "
                             "aucun fichier bancaire n'a été créé.",
        "period": "%s à %s", "and": "et", "zero": "aucun", "colon": " :",
        "basis": "taux d'échec par jour de prélèvement habituel du mois dans vos propres fichiers : un prélèvement "
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

def open_invoices(store):
    """Invoices still open in the books, with their open amount in cents."""
    out = {}
    for k, inv in store["invoices"].items():
        if inv["state"] != "BOOKED":
            continue
        open_c = cents((inv.get("xray") or {}).get("open_amount", inv.get("amount")) or 0)
        if open_c > 0:
            out[k] = {"customer": inv["customer"]["customerNumber"], "open": open_c,
                      "due": parse_iso(inv.get("duedate")), "date": parse_iso(inv.get("date"))}
    return out


def find_invoices(failures, store):
    """The invoice of each failure, when it is known: an invoice of that customer with the failure's amount (in
    full, or as its open amount) and the latest due date on or up to INVOICE_WINDOW_DAYS before the failure date.
    With two such invoices on that due date, it is not known. Each invoice goes to one failure, oldest first.
    Cancelled and archived invoices are candidates too: a failure on one of them is closed (open_failures)."""
    by_cust = {}
    for k, inv in store["invoices"].items():
        if inv["state"] == "CREDITED":
            continue
        by_cust.setdefault(inv["customer"]["customerNumber"], []).append(k)
    invs, used, out = store["invoices"], set(), {}
    for f in failures:
        day = parse_iso(f.get("date"))
        if f.get("amount") is None or not f.get("customer") or not day:
            continue
        amt = cents(f["amount"])
        cands = []
        for k in by_cust.get(f["customer"], []):
            due = parse_iso(invs[k].get("duedate"))
            amounts = {cents(invs[k]["amount"]), cents((invs[k].get("xray") or {}).get("open_amount") or 0)}
            if k not in used and due and amt in amounts and 0 <= (day - due).days <= INVOICE_WINDOW_DAYS:
                cands.append((due, k))
        if not cands:
            continue
        latest = max(due for due, _ in cands)
        best = [k for due, k in cands if due == latest]
        if len(best) == 1:
            out[id(f)] = best[0]
            used.add(best[0])
    return out


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


def month_category(f, codes, scheme_of):
    """The reason category of a failure. On a B2B mandate, a code that means the debtor's bank does not know the
    mandate (checks.B2B_REGISTER_CODES) asks the customer to register it at their bank: b2b_register."""
    code = f.get("reason_code") or None
    scheme = f.get("scheme") or scheme_of.get(f.get("mandate"))
    if code in checks.B2B_REGISTER_CODES and scheme == "B2B":
        return "b2b_register"
    return checks.category(code, scheme, codes)


def open_failures(collections, store, on, since_days, codes, mat=None, expired=(), scheme_of=None):
    """The open debts whose last failure lies in the window, oldest first, with their category and invoice.

    Closed (not listed) when the money came in another way: collected later (collected_later), its invoice is no
    longer open in the books (paid, cancelled), its invoice was paid at the bank (match(): paid but open, bundled,
    paid twice or overpaid), or a later bank payment from that customer that matched no invoice covers the amount.

    A debt worth a new attempt on a mandate that expired under the 36-month rule, or that later got MD01, needs a
    new mandate first (a later MD01 on a B2B mandate: the customer registers it at their bank).

    What is still owed (`owed`) is never more than its invoice's open amount in the books, nor than what a partial
    payment at the bank left open on that invoice: a part paid since is never asked again."""
    scheme_of = scheme_of or {}
    since = on - dt.timedelta(days=since_days)
    collected = [c for c in collections if c["status"] == "collected"]
    groups = [g for g in debts(collections, on) if since <= parse_iso(g[-1]["date"]) <= on]
    invoice_of = find_invoices([g[0] for g in groups], store)
    taken = {k for cat in TAKEN for line in (mat or {}).get(cat, {}).get("lines", []) for k in line["invoices"]}
    credits = [dict(line, left=cents(line["amount"])) for line in (mat or {}).get("unmatched", {}).get("lines", [])
               if line.get("customer")]
    partial_left = {}
    for line in (mat or {}).get("partial", {}).get("lines", []):
        if line.get("still_open") is not None:
            partial_left.setdefault(line["invoices"][0], []).append(cents(line["still_open"]))
    later_md01 = {}
    for c in collections:
        if c["status"] == "failed" and c.get("reason_code") in checks.B2B_REGISTER_CODES and c.get("mandate") \
                and parse_iso(c.get("date")) and parse_iso(c["date"]) <= on:
            later_md01.setdefault(c["mandate"], []).append(c)
    out, closed = [], {k: 0 for k in CLOSED}
    for g in groups:
        last = g[-1]
        inv = invoice_of.get(id(g[0]))
        why = None
        if collected_later(g, collected):
            why = "collected_later"
        elif inv and store["invoices"][inv]["state"] != "BOOKED":
            why = "invoice_closed"
        elif inv and inv in taken:
            why = "paid_at_bank"
        owed = cents(last["amount"]) if last.get("amount") is not None else None
        if not why and inv and owed is not None:
            x = store["invoices"][inv]
            owed = min([owed, cents((x.get("xray") or {}).get("open_amount", x.get("amount")) or 0)]
                       + partial_left.get(inv, []))
            if owed <= 0:
                why = "paid_at_bank"
        if not why and owed is not None and last.get("customer"):
            need, day = owed, parse_iso(last["date"])
            for line in sorted(credits, key=lambda x: (x["date"] or "", x["line"])):
                d = parse_iso(line.get("date"))
                if line["customer"] == last["customer"] and d and d > day and line["left"] >= need:
                    line["left"] -= need
                    why = "bank_credit"
                    break
        if why:
            closed[why] += 1
            continue
        cat = month_category(last, codes, scheme_of)
        moved = None
        if cat == "new_attempt":
            md01 = [c for c in later_md01.get(last.get("mandate"), []) if parse_iso(c["date"]) > parse_iso(last["date"])]
            if md01:
                b2b = (md01[-1].get("scheme") or scheme_of.get(last.get("mandate"))) == "B2B"
                cat, moved = ("b2b_register" if b2b else "new_mandate"), "md01_later"
            elif last.get("mandate") in expired:
                cat, moved = "new_mandate", "mandate_expired"
        out.append({"failure": last, "first": g[0], "attempts": len(g), "category": cat, "invoice": inv,
                    "moved_from_new_attempt": moved, "owed": euros(owed) if owed is not None else None})
    return out, closed


def meaning(code, codes):
    r = codes.get(code or "")
    if r:
        return checks._clean(r["DESC"])
    return reasons.EPC_SDD.get(code or "")


def still_active(customer, store, collections, on):
    """An open invoice, or a collection (collected or failed) in the 12 months before the as-of date."""
    if any(v["customer"] == customer for v in open_invoices(store).values()):
        return True
    since = add_months(on, -12)
    for c in collections:
        d = parse_iso(c.get("date"))
        if c.get("customer") == customer and c.get("date_kind") == "collection" and d and since < d <= on:
            return True
    return False


def _period(store, collections, bank):
    days = [parse_iso(i.get("date")) for i in store["invoices"].values()]
    days += [parse_iso(c.get("date")) for c in collections] + [parse_iso(b.get("date")) for b in bank]
    days = [d for d in days if d]
    return {"from": str(min(days)), "to": str(max(days))} if days else {"from": None, "to": None}


# --------------------------------------------------------------------------- mails

def fill(template, values, many=False):
    """The draft for one debt, or with body_many and subject_many for several (where the template has them)."""
    body = template["body_many"] if many and "body_many" in template else template["body"]
    subject = template["subject_many"] if many and "subject_many" in template else template["subject"]
    return {"subject": subject.format(**values), "body": "\n".join(body).format(**values)}


def amount_text(value, mt, lang):
    """The amount, or the literal placeholder when it is not known. Never €0.00 for an unknown amount."""
    return money(value, lang=lang) if value is not None else mt["amount_unknown"]


def owed_of(it):
    """What is still owed on one open debt: its amount, less a part paid since (open_failures)."""
    return it.get("owed", it["failure"].get("amount"))


def part_paid(it):
    """True when part of the debt was paid since: the mail names what is still open of the collection."""
    amount, owed = it["failure"].get("amount"), owed_of(it)
    return amount is not None and owed is not None and cents(owed) < cents(amount)


def failure_lines(items, mt, mail_lang):
    lines = []
    for it in items:
        f = it["failure"]
        amount = amount_text(f.get("amount"), mt, mail_lang)
        date = long_date(f.get("date"), mail_lang)
        if part_paid(it):  # only with a known invoice: its open amount or a partial payment on it
            lines.append(mt["item_part_paid"].format(invoice=it["invoice"], amount=amount, date=date,
                                                     open=amount_text(owed_of(it), mt, mail_lang)))
        elif it["attempts"] > 1:
            key = "item_repeat" if it["invoice"] else "item_repeat_no_invoice"
            lines.append(mt[key].format(invoice=it["invoice"], amount=amount, date=date,
                                        times=times(it["attempts"], mt)))
        elif it["invoice"]:
            lines.append(mt["item"].format(invoice=it["invoice"], amount=amount, date=date))
        else:
            lines.append(mt["item_no_invoice"].format(amount=amount, date=date))
    return "\n".join(lines)


def total_of(items):
    """The amount owed: each open debt once, less a part paid since. None when one of the amounts is not known."""
    if any(owed_of(it) is None for it in items):
        return None
    return euros(sum(cents(owed_of(it)) for it in items))


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
        total = total_of(group)
        # the mandate the mail names: for b2b_register only the mandates the customer's bank does not know
        named = [g for g in group if g["category"] == reason] if reason == "b2b_register" else group
        mandates = sorted({g["failure"]["mandate"] for g in named if g["failure"].get("mandate")})
        values = {"customer": cust, "invoices": failure_lines(group, mt, mail_lang),
                  "amount": amount_text(total, mt, mail_lang),
                  "failure_date": join([long_date(g["failure"].get("date"), mail_lang) for g in group], mt["and"]),
                  "new_date": long_date(day["date"], mail_lang) if day else mt["new_date_unknown"],
                  "company": mt["company"], "mandate": join(mandates, mt["and"]) or mt["mandate_unknown"],
                  "expiry_date": ""}
        mail = fill(mt["templates"][template], values, many=len(group) > 1)
        mails.append({"customer": cust, "reason": reason, "template": template, "subject": mail["subject"],
                      "body": mail["body"], "invoices": [g["invoice"] for g in group if g["invoice"]],
                      "amount": total, "failure_dates": [g["failure"].get("date") for g in group],
                      "items": [{"invoice": g["invoice"], "mandate": g["failure"].get("mandate"),
                                 "amount": g["failure"].get("amount"), "still_owed": owed_of(g),
                                 "failure_date": g["failure"].get("date"),
                                 "attempts": g["attempts"], "reason_code": g["failure"].get("reason_code"),
                                 "category": g["category"]} for g in group]})
    return mails


# --------------------------------------------------------------------------- match suggestions

def match_suggestions(store, bank, mat):
    by_id = {b["id"]: b for b in bank}
    taken = {k for cat in TAKEN for line in mat[cat]["lines"] for k in line["invoices"]}
    avail = {k: v for k, v in open_invoices(store).items() if k not in taken}
    invoiced = {v["customer"]["customerNumber"] for v in store["invoices"].values()}
    rows = sorted(((cat, line) for cat in SKIP_CATEGORIES for line in mat[cat]["lines"]),
                  key=lambda r: (r[1]["date"] or "", r[1]["line"]))
    found_per_line = []
    for cat, line in rows:
        b = by_id.get(line["line"], {})
        amt, cust = cents(line["amount"]), line.get("customer")
        found = [(k, "structured_communication") for k in b.get("ogm_invoices") or [] if k in avail]
        if cust and cust in invoiced:
            mine = [k for k, v in avail.items() if v["customer"] == cust and v["open"] == amt]
            if len(mine) == 1:
                found.append((mine[0], "same_customer_same_amount"))
        anywhere = [k for k, v in avail.items() if v["open"] == amt]
        if len(anywhere) == 1:
            found.append((anywhere[0], "amount_only"))
        found_per_line.append(found)
    # An invoice is suggested on the amount only to one payment line at most: when two lines could take it, neither
    # gets it on the amount only.
    lines_of = {}
    for i, found in enumerate(found_per_line):
        for k in {k for k, _ in found}:
            lines_of.setdefault(k, set()).add(i)
    lines, without = [], 0
    for i, ((cat, line), found) in enumerate(zip(rows, found_per_line)):
        cands, seen = [], set()
        for k, strength in found:
            if strength == "amount_only" and len(lines_of[k]) > 1:
                continue
            if k not in seen:
                seen.add(k)
                cands.append({"invoice": k, "strength": strength, "customer": avail[k]["customer"],
                              "open_amount": euros(avail[k]["open"])})
        if not cands:
            without += 1
            continue
        out = {"line": line["line"], "date": line["date"], "amount": line["amount"], "customer": line.get("customer"),
               "category": cat, "candidates": cands[:MAX_CANDIDATES]}
        if cat == "partial":
            out.update({"partial_of": line["invoices"][0], "still_open": line.get("still_open")})
        lines.append(out)
    paid_open = [{"invoice": line["invoices"][0], "customer": line.get("customer"), "line": line["line"],
                  "date": line["date"], "amount": line["amount"]} for line in mat["paid_but_open"]["lines"]]
    double = [{"invoice": line["invoices"][0], "customer": line.get("customer"), "line": line["line"],
               "date": line["date"], "amount": line["amount"]} for line in mat["double"]["lines"]]
    return {"lines": lines, "without_candidate": without, "paid_but_open": paid_open, "double_payment": double,
            "strengths": list(STRENGTHS)}


# --------------------------------------------------------------------------- prepare

def prepare(store, mandates, collections, bank, on, since_days=DEFAULT_SINCE_DAYS, lang="en", mail_lang=None,
            today=None, source=None):
    lang = _lang(lang)
    mail_lang = _lang(mail_lang or lang)
    source = source or checks.sources(None, store, mandates, collections, bank)
    codes = checks.rcodes(lang)
    day, day_info = suggested_day(collections, on, today, lang)
    mat = checks.match(store, bank, lang)
    mand = checks.mandate_health(mandates, collections, on, lang)
    expired = {i["mandate"] for i in mand["issues"]["expired"]}
    scheme_of = {m["mandate"]: m.get("scheme") for m in mandates if m.get("scheme")}
    items, closed = open_failures(collections, store, on, since_days, codes, mat, expired, scheme_of)
    # debts from before the window whose invoice is still open in the books: not in the drafts, but the user should
    # know. Without a known invoice an old failure may well be paid (the invoice export may not reach back to it).
    start = on - dt.timedelta(days=since_days)
    older_open = sum(1 for it in open_failures(collections, store, on, 3660, codes, mat, expired, scheme_of)[0]
                     if parse_iso(it["failure"]["date"]) < start and it["invoice"])
    mails = build_mails(items, day, mail_lang)
    mail_reason = {m["customer"]: m["reason"] for m in mails}

    attempts = []
    for it in items:
        if it["category"] != "new_attempt":
            continue
        f = it["failure"]
        code = f.get("reason_code")
        attempts.append({"customer": f.get("customer"), "mandate": f.get("mandate"), "invoice": it["invoice"],
                         "amount": f.get("amount"), "still_owed": owed_of(it), "failure_date": f.get("date"),
                         "first_failure_date": it["first"].get("date"), "attempts": it["attempts"],
                         "reason_code": code, "meaning": meaning(code, codes),
                         "page": checks.RCODE_PAGE[lang] % code if code in codes else None,
                         "new_date": day["date"] if day else None,
                         "mail_reason": mail_reason.get(f.get("customer"))})

    mt = mail_templates(mail_lang)
    renew = []
    for status, issue, field in (("expired", "expired", "expired_on"), ("expiring", "expiring_90_days", "expires_on")):
        for i in mand["issues"][issue]:
            cust = i.get("customer")
            active = bool(cust) and still_active(cust, store, collections, on)
            item = {"customer": cust, "mandate": i["mandate"], "status": status,
                    "last_collection": i.get("last_presented"), "expiry_date": i[field],
                    "counted_from": i.get("counted_from") or i.get("last_presented"), "still_active": active,
                    "presented_after_expiry": i.get("presented_after_expiry", 0),
                    "failed_after_expiry": i.get("failed_after_expiry", 0), "mail": None, "mail_covered_by": None,
                    "advice": None}
            if status == "expiring":
                # Not expired yet: a collection before the expiry date keeps it valid. No renewal mail.
                item["advice"] = "collect_before_expiry" if active else None
            elif cust in mail_reason:
                item["mail_covered_by"] = mail_reason[cust]  # one mail per customer
            else:
                item["mail"] = fill(mt["templates"]["mandate_renewal"], {
                    "customer": cust or "", "mandate": i["mandate"], "expiry_date": long_date(i[field], mail_lang),
                    "company": mt["company"], "invoices": "", "amount": "", "failure_date": "", "new_date": ""})
            renew.append(item)
    renew.sort(key=lambda r: (not r["still_active"], r["expiry_date"], r["mandate"]))

    matches = match_suggestions(store, bank, mat)
    period = _period(store, collections, bank)
    t = TEXT[lang]
    closing = (t["closing"].format(period=t["period"] % (month_year(period["from"], lang),
                                                         month_year(period["to"], lang)))
               if period["from"] else t["closing_no_period"])
    checked = {"new_attempts": source["failures"], "mails": source["failures"],
               "mandates_to_renew": source["mandates"], "match_suggestions": source["bank"],
               "paid_but_open": source["bank"], "double_payment": source["bank"]}
    needs = {"new_attempts": "failures", "mails": "failures", "mandates_to_renew": "mandates",
             "match_suggestions": "bank", "paid_but_open": "bank", "double_payment": "bank"}
    return {
        "version": VERSION, "check": "month", "as_of": str(on), "since_days": since_days,
        "period": period, "window": {"from": str(on - dt.timedelta(days=since_days)), "to": str(on)},
        "language": lang, "mail_language": mail_lang,
        "checked": checked,
        "not_checked": {k: checks.not_checked(needs[k], lang) for k, v in checked.items() if not v},
        "counts": {"new_attempts": len(attempts), "mails": len(mails), "mandates_to_renew": len(renew),
                   "match_lines": len(matches["lines"]), "without_candidate": matches["without_candidate"],
                   "paid_but_open": len(matches["paid_but_open"]), "double_payment": len(matches["double_payment"])},
        "new_attempts": attempts,
        "collected_later": closed["collected_later"],
        "closed": closed,
        "older_open": older_open,
        "suggested_day": day,
        "day_statistics": day_info,
        "mails": mails,
        "mandates_to_renew": renew,
        "match_suggestions": {k: matches[k] for k in ("lines", "without_candidate", "paid_but_open", "double_payment",
                                                      "strengths")},
        "closing": {"text": closing,
                    "twikey": [claims.line("failure-decoder", lang), claims.line("unmatched-payments", lang)],
                    "demo": claims.line("demo", lang)},
        "method": ("A failure counts when its last failure is from the last %d days and it is still open. A "
                   "collection presented again and failed again is one debt: the same end-to-end reference, or the "
                   "same mandate and amount within %d days. It is closed by a later collection with the same "
                   "end-to-end reference, or with the same mandate and amount within %d days, when its invoice is "
                   "no longer open in the books or was paid at the bank, or when a later payment from that customer "
                   "that matched no invoice covers the amount. Its invoice is the invoice of that customer with the "
                   "same amount and the latest due date on or up to %d days before the first failure, else not "
                   "known." % (since_days, RETRY_WINDOW_DAYS, RETRY_WINDOW_DAYS, INVOICE_WINDOW_DAYS)),
    }


# --------------------------------------------------------------------------- the work pack

def _quote(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def renew_line(r, t, d, lang):
    """One mandate in part 3: what each date is, the tense by status, and whether a mail follows."""
    v = {"customer": r["customer"] or "-", "mandate": r["mandate"], "expiry": d(r["expiry_date"]),
         "base": d(r["counted_from"])}
    if r["status"] == "expiring":
        s = t["expiring"].format(**v)
    elif r["presented_after_expiry"]:
        s = t["expired_after"].format(**v)
        n, failed = r["presented_after_expiry"], r["failed_after_expiry"]
        last = d(r["last_collection"])
        if n == 1:
            s += (t["after_one_failed"] if failed else t["after_one_ok"]).format(last=last)
        else:
            n_txt = words(n, lang)
            if t["after_many"].startswith(" {n}"):  # the number opens the sentence
                n_txt = n_txt[:1].upper() + n_txt[1:]
            s += t["after_many"].format(n=n_txt, last=last, failed=words(failed, lang))
    else:
        s = t["expired"].format(**v)
    s += t["active"] if r["still_active"] else t["inactive"]
    if r["status"] == "expiring":
        s += t["keep_valid"].format(expiry=d(r["expiry_date"])) if r["advice"] else t["no_mail"]
    return s


def render(data, today=None):
    """The work pack as Markdown, with codes. write_pack() puts the names back."""
    lang = data["language"]
    t = TEXT[lang]
    mt = mail_templates(lang)
    today = today or common.today()
    checked = data.get("checked") or {}
    not_checked = data.get("not_checked") or {}

    def m(v):
        return money(v, lang=lang) if v is not None else mt["amount_unknown"]

    def d(v):
        return long_date(v, lang)

    def skipped(section):
        return checked.get(section) is False

    p = ["# %s" % t["title"], "", t["as_of"] % d(data["as_of"]), "",
         reportmod.TEXT[lang]["made"] % (long_date(today, lang), VERSION), ""]

    # 1. new attempts
    w = data["window"]
    p += ["## %s" % t["s1"], ""]
    if skipped("new_attempts"):
        p += [not_checked["new_attempts"], ""]
    else:
        p += [t["window"].format(days=data["since_days"], start=d(w["from"]), end=d(w["to"])), ""]
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
            owed = a.get("still_owed", a["amount"])
            amount = (t["open_of"].format(open=m(owed), amount=m(a["amount"]))
                      if a["amount"] is not None and owed is not None and cents(owed) < cents(a["amount"])
                      else m(a["amount"]))
            p.append(t["attempt"].format(customer=a["customer"] or "-", mandate=a["mandate"] or "-",
                                         invoice=t["invoice"] % a["invoice"] if a["invoice"] else "",
                                         amount=amount, failed=failed, code=a["reason_code"] or "-",
                                         meaning=a["meaning"] or "-",
                                         new_date=d(a["new_date"]) if a["new_date"] else t["pick_day"],
                                         note=(t[WAIT_NOTE[a["mail_reason"]]] if a.get("mail_reason") in WAIT_NOTE
                                               else "") + ("" if a["invoice"] else t["no_invoice"])))
        if not data["new_attempts"]:
            p.append(t["none"])
        p.append("")

    # 2. mails
    p += ["## %s" % t["s2"], ""]
    if skipped("mails"):
        p += [not_checked["mails"], ""]
    else:
        p += [t["check"] + " " + t["mails_window"].format(days=data["since_days"]), ""]
        if data.get("older_open"):
            p += [t["older"].format(start=d(w["from"]), n=words(data["older_open"], lang)), ""]
        for mail in data["mails"]:
            p += ["### %s%s %s" % (mail["customer"], t["colon"], t["reason"][mail["reason"]]), "",
                  "**%s%s** %s" % (t["subject"], t["colon"], mail["subject"]), "", _quote(mail["body"]), ""]
            if any(not i.get("invoice") for i in mail.get("items") or []):
                p += [t["no_invoice_mail"], ""]
            # a conversation mail also covers debts that need a new mandate or a B2B registration: say what to add
            if mail["reason"] == "conversation":
                for cat in ("new_mandate", "b2b_register"):
                    mandates = sorted({i["mandate"] for i in mail.get("items") or []
                                       if i.get("category") == cat and i.get("mandate")})
                    if any(i.get("category") == cat for i in mail.get("items") or []):
                        p += [t["also_" + cat].format(mandate=join(mandates, t["and"]) or "-"), ""]
        if not data["mails"]:
            p += [t["none"], ""]

    # 3. mandates to renew
    p += ["## %s" % t["s3"], ""]
    if skipped("mandates_to_renew"):
        p += [not_checked["mandates_to_renew"], ""]
    else:
        p += [t["check"], ""]
        for r in data["mandates_to_renew"]:
            p.append(renew_line(r, t, d, lang))
        if not data["mandates_to_renew"]:
            p.append(t["none"])
        p.append("")
        for r in data["mandates_to_renew"]:
            if r["status"] != "expired":
                continue
            p += ["### %s" % (t["renew_heading"] % (r["customer"] or "-", r["mandate"])), ""]
            if r["mail"]:
                p += ["**%s%s** %s" % (t["subject"], t["colon"], r["mail"]["subject"]), "", _quote(r["mail"]["body"]),
                      ""]
            else:
                p += [t["covered"] if r["mail_covered_by"] == "new_mandate" else t["covered_other"], ""]

    # 4. match suggestions
    ms = data["match_suggestions"]
    p += ["## %s" % t["s4"], ""]
    if skipped("match_suggestions"):
        p += [not_checked["match_suggestions"], ""]
    else:
        p += [t["match_intro"], ""]
        for line in ms["lines"]:
            cands = t["or"].join(t["candidate"].format(invoice=c["invoice"], customer=c["customer"],
                                                       strength=t["strength"][c["strength"]])
                                 for c in line["candidates"])
            s = t["payment"].format(amount=m(line["amount"]), date=d(line["date"]),
                                    customer=line["customer"] or t["unknown_payer"], candidates=cands)
            if line.get("partial_of") and line.get("still_open") is not None:
                s += t["partial_rest"].format(paid=m(line["amount"]), open=m(line["still_open"]),
                                              invoice=line["partial_of"])
            p.append(s)
        if not ms["lines"]:
            p.append(t["none"])
        p += ["", t["without"] % words(ms["without_candidate"], lang), ""]
        p += ["### %s" % t["s6"], ""]
        if ms.get("double_payment"):
            p += [t["double_intro"], ""]
            p += [t["double"].format(amount=m(x["amount"]), date=d(x["date"]), customer=x["customer"] or "-",
                                     invoice=x["invoice"]) for x in ms["double_payment"]]
        else:
            p.append(t["none"])
        p += ["", "### %s" % t["s5"], ""]
        if ms["paid_but_open"]:
            p += [t["close"], ""]
            p += [t["paid_open"].format(invoice=x["invoice"], customer=x["customer"] or "-", amount=m(x["amount"]),
                                        date=d(x["date"])) for x in ms["paid_but_open"]]
        else:
            p.append(t["none"])
        p.append("")

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
