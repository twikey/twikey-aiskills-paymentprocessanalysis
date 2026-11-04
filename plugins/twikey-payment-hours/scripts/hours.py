#!/usr/bin/env python3
"""Twikey Payment Hours calculator.

Python 3.8+, standard library only, deterministic. It keeps the user's answers in a small JSON ledger in the
working folder and prints every number with the formula behind it.

  python3 hours.py [--ledger FILE] [--lang en|nl|fr] set KEY=VALUE [KEY=VALUE ...]
  python3 hours.py [--ledger FILE] unset KEY [KEY ...]
  python3 hours.py [--ledger FILE] show
  python3 hours.py [--ledger FILE] [--lang en|nl|fr] process
  python3 hours.py [--ledger FILE] [--lang en|nl|fr] methods
  python3 hours.py [--ledger FILE] [--lang en|nl|fr] report [--out FILE]

Keys:
  company.lang=en|nl|fr  company.hourly_cost=EUR  company.fte_hours_week=HOURS (default 38)
  task.STEP.NAME.count=N or an arithmetic expression such as 400*25%*2
  task.STEP.NAME.minutes=N  task.STEP.NAME.mode=manual|partly|automatic  task.STEP.NAME.who=TEXT
  task.STEP.NAME.label=TEXT  task.STEP.NAME.scales=yes|no
  payments.per_month=N  payments.avg_amount=EUR
  method.METHOD.FIELD=N  (FIELD: share fee_fixed fee_pct fail_pct fail_fee fail_minutes dispute_pct dispute_fee
                          dispute_minutes minutes days)
  whatif=FROM:TO:PCT     (move PCT% of the FROM payers to TO)
  note.KEY=TEXT          (free text the report lists under assumptions, e.g. note.dso=52 days)
"""
import argparse
import ast
import datetime
import json
import math
import operator
import os
import re
import sys

VERSION = "0.1.0"
LEDGER = "twikey-payment-hours.json"
HERE = os.path.dirname(os.path.abspath(__file__))
CLAIMS = os.path.join(HERE, os.pardir, "references", "twikey-claims.md")
LANGS = ("en", "nl", "fr")

STEPS = ["invoice", "collect", "match", "chase", "failed", "details", "refunds", "reporting"]
STEP_LABEL = {
    "en": {"invoice": "Send the invoice or payment request", "collect": "Take in payments",
           "match": "Match payments to invoices", "chase": "Remind and chase late payers",
           "failed": "Handle failed payments", "details": "Set up and update payment details",
           "refunds": "Refunds, disputes and chargebacks", "reporting": "Reporting and cash forecasting"},
    "nl": {"invoice": "Factuur of betaalverzoek versturen", "collect": "Betalingen innen",
           "match": "Betalingen aan facturen koppelen", "chase": "Herinneren en late betalers opvolgen",
           "failed": "Mislukte betalingen opvolgen", "details": "Betaalgegevens instellen en bijwerken",
           "refunds": "Terugbetalingen, betwistingen en chargebacks", "reporting": "Rapportering en cashprognose"},
    "fr": {"invoice": "Envoyer la facture ou la demande de paiement", "collect": "Encaisser les paiements",
           "match": "Rapprocher les paiements des factures", "chase": "Relancer les retardataires",
           "failed": "Traiter les paiements échoués", "details": "Configurer et mettre à jour les données de paiement",
           "refunds": "Remboursements, litiges et rétrofacturations", "reporting": "Reporting et prévision de trésorerie"},
}
MODES = ("manual", "partly", "automatic")
MODE_LABEL = {"en": {"manual": "by hand", "partly": "partly automatic", "automatic": "automatic"},
              "nl": {"manual": "handmatig", "partly": "deels automatisch", "automatic": "automatisch"},
              "fr": {"manual": "à la main", "partly": "en partie automatique", "automatic": "automatique"}}
METHODS = ["transfer", "sdd_core", "sdd_b2b", "card", "card_recurring", "bancontact", "wero", "paypal", "wallet",
           "link", "qr", "other"]
METHOD_LABEL = {
    "en": {"transfer": "Bank transfer", "sdd_core": "SEPA Direct Debit Core", "sdd_b2b": "SEPA Direct Debit B2B",
           "card": "Card (one-off)", "card_recurring": "Stored card (recurring)", "bancontact": "Bancontact",
           "wero": "Wero", "paypal": "PayPal", "wallet": "Apple Pay / Google Pay", "link": "Payment link",
           "qr": "QR code", "other": "Other"},
    "nl": {"transfer": "Overschrijving", "sdd_core": "SEPA-domiciliëring Core", "sdd_b2b": "SEPA-domiciliëring B2B",
           "card": "Kaart (eenmalig)", "card_recurring": "Opgeslagen kaart (terugkerend)", "bancontact": "Bancontact",
           "wero": "Wero", "paypal": "PayPal", "wallet": "Apple Pay / Google Pay", "link": "Betaallink",
           "qr": "QR-code", "other": "Andere"},
    "fr": {"transfer": "Virement", "sdd_core": "Prélèvement SEPA Core", "sdd_b2b": "Prélèvement SEPA B2B",
           "card": "Carte (ponctuelle)", "card_recurring": "Carte enregistrée (récurrente)", "bancontact": "Bancontact",
           "wero": "Wero", "paypal": "PayPal", "wallet": "Apple Pay / Google Pay", "link": "Lien de paiement",
           "qr": "Code QR", "other": "Autre"},
}
TASK_FIELDS = ("count", "minutes", "mode", "who", "label", "scales")
METHOD_FIELDS = ("share", "fee_fixed", "fee_pct", "fail_pct", "fail_fee", "fail_minutes", "dispute_pct",
                 "dispute_fee", "dispute_minutes", "minutes", "days")
PCT_FIELDS = ("share", "fee_pct", "fail_pct", "dispute_pct")
COMPANY_FIELDS = ("lang", "hourly_cost", "fte_hours_week")
PAYMENT_FIELDS = ("per_month", "avg_amount")
DEFAULT_FTE_HOURS_WEEK = 38

T = {
    "en": {
        "h": "h", "map_title": "Getting paid, step by step (hours a month)", "not_asked": "not asked yet",
        "table_title": "Hours a month, per task", "step": "Step", "task": "Task", "how": "How today", "who": "Who",
        "a_month": "Times a month", "min_each": "Minutes each", "hours_month": "Hours a month",
        "double": "At twice the volume", "total": "Total", "fixed": "does not grow with volume",
        "f_task": "Hours a month = times a month × minutes each ÷ 60, rounded to 0.1 hour. Totals add up the rounded lines.",
        "f_total": "Total hours a month", "f_fte": "FTE (full-time equivalent)",
        "f_fte_month": "hours in a full-time month", "f_cost": "Cost a month at your hourly cost",
        "f_year": "a year", "f_double": "At twice the volume",
        "no_cost": "No hourly cost given: set company.hourly_cost to see the cost.",
        "fte_default": "a {n}-hour week, the default value",
        "fte_given": "a {n}-hour week, your answer",
        "no_tasks": "No tasks given yet.",
        "methods_title": "Payment methods compared, from your own numbers",
        "m_fails_month": "Failed payments a month", "m_disp_month": "Disputes, refunds and chargebacks a month",
        "m_time_cost_month": "Time cost a month", "m_time_diff": "Difference in time cost a month",
        "m_pay_col": "Payments a month", "m_hours_col": "Hours a month", "m_days_col": "Days to cash",
        "m_no_fees": "Fees not given for: {m}. Euro totals are only compared between methods with fees.",
        "m_need_avg": "Set payments.avg_amount to work out the percentage fees of: {m}.",
        "m_pair_year": "Per year for {a} and {b}",
        "m_whatif_no_fees": "The euro difference needs fees for both {a} and {b}.",
        "m_payments": "{share} of {n} {pn} a month = {k} {pk} a month",
        "m_fees": "Fees per 100 payments", "m_time": "Handling time per 100 payments",
        "m_time_cost": "Handling cost per 100 payments", "m_one": "Cost of one", "m_per100": "Per 100",
        "m_fail": "Failed payments per 100", "m_disp": "Disputes, refunds and chargebacks per 100",
        "m_full": "Full cost per 100 payments", "m_year": "Per year",
        "m_hours": "Hours a month, failed payments and disputes included",
        "m_share_sum": "The shares add up to {f}, not 100%. Check the mix.",
        "m_days": "Days until the money is on your account", "m_days_none": "not given",
        "m_missing": "Not given, counted as zero: {f}",
        "m_table": "Summary", "m_method": "Method", "m_share": "Share", "m_total_year": "All methods, per year",
        "m_avg_days": "Average days until the money is in, weighted by share",
        "m_whatif": "What if {pct} of the payers move from {a} to {b}",
        "m_whatif_none": "{b} has no fees or rates yet, so the shift cannot be calculated.",
        "m_after": "Per year after the shift", "m_today": "today", "m_diff": "Difference a year",
        "m_hours_diff": "Hours a month on handling payments",
        "m_no_methods": "No payment methods given yet.", "m_no_volume": "Set payments.per_month first.",
        "twikey": "Twikey", "twikey_en": "Twikey (English)", "twikey_tr": "Twikey (translated from English)",
        "auto_note": "A step counts when a Twikey page says it automates it. Not every task in it is covered: the demo shows which of your tasks Twikey takes over.",
        "m_switch_note": "This difference does not count the work of moving payers, such as signing a mandate and, for B2B, registering it at the payer's bank.",
        "pkg": "Pricing page row", "pricing": "Pricing page",
        "rep_title": "Getting paid: hours a month", "rep_as_of": "Estimate from your own answers, {d}.",
        "found": "What we found", "found_line": "{s}: {h} hours a month, {p} of the total ({h} ÷ {t}).",
        "fits": "Where Twikey fits", "modes_today": "Hours a month by how the work is done today",
        "mode_none": "how not given", "grows": "Hours a month that grow with volume",
        "found_all": "Getting paid takes {h} hours a month",
        "found_some": "The {n} steps you answered take {h} hours a month",
        "found_one": "The one step you answered takes {h} hours a month",
        "found_fte_cost": "{f} FTE and {c} a month at your hourly cost", "found_fte": "{f} FTE",
        "found_cov": "a Twikey page says it automates this step",
        "found_nocov": "no Twikey page says it automates this step",
        "map_cov": "A Twikey page says it automates this step.",
        "gaps_steps": "Not asked yet: {s}.",
        "gaps_tasks": "Missing a count or minutes, so not in the total: {s}.",
        "m_overlap": "These handling hours overlap with the hours per step and are not added to the total hours a month.",
        "map": "The process map", "table": "Hours a month, per task",
        "auto_title": "Steps Twikey's site says it automates",
        "auto_sum": "Hours a month on steps Twikey's site says it automates: {a} of {t} hours{f}.",
        "manual_title": "Steps no Twikey page says it automates",
        "manual_sum": "Hours a month on steps no Twikey page says it automates: {m} of {t} hours{f}.",
        "none_steps": "None of the steps you described.",
        "methods": "Payment methods compared", "assumptions": "Assumptions and formulas",
        "a_answers": "Every count, minute, fee and rate is your own answer. Nothing was measured.",
        "a_ranges": "Where you estimated, the result is as good as the estimate.",
        "a_notes": "Your notes", "next": "Next step",
        "footer": "Made with Payment Hours by Twikey, version {v}. It calculates and explains. It never contacts your customers or touches your payment systems.",
        "no_saving": "The hours above are the hours you spend today, from your own answers. This report does not estimate how many of them would go.",
    },
    "nl": {
        "h": "uur", "map_title": "Betaald worden, stap voor stap (uren per maand)", "not_asked": "nog niet gevraagd",
        "table_title": "Uren per maand, per taak", "step": "Stap", "task": "Taak", "how": "Hoe nu", "who": "Wie",
        "a_month": "Keer per maand", "min_each": "Minuten per keer", "hours_month": "Uren per maand",
        "double": "Bij dubbel volume", "total": "Totaal", "fixed": "groeit niet mee met het volume",
        "f_task": "Uren per maand = keer per maand × minuten per keer ÷ 60, afgerond op 0,1 uur. Totalen tellen de afgeronde lijnen op.",
        "f_total": "Totaal uren per maand", "f_fte": "VTE (voltijdsequivalent)",
        "f_fte_month": "uren in een voltijdse maand", "f_cost": "Kost per maand aan je uurkost",
        "f_year": "per jaar", "f_double": "Bij dubbel volume",
        "no_cost": "Geen uurkost opgegeven: geef company.hourly_cost in om de kost te zien.",
        "fte_default": "een week van {n} uur, de standaardwaarde",
        "fte_given": "een week van {n} uur, je antwoord",
        "no_tasks": "Nog geen taken opgeslagen.",
        "methods_title": "Betaalmethodes vergeleken, met je eigen cijfers",
        "m_fails_month": "Mislukte betalingen per maand",
        "m_disp_month": "Betwistingen, terugbetalingen en chargebacks per maand",
        "m_time_cost_month": "Tijdskost per maand", "m_time_diff": "Verschil in tijdskost per maand",
        "m_pay_col": "Betalingen per maand", "m_hours_col": "Uren per maand", "m_days_col": "Dagen tot het geld er is",
        "m_no_fees": "Geen kosten opgegeven voor: {m}. Bedragen in euro worden alleen vergeleken tussen methodes met kosten.",
        "m_need_avg": "Geef payments.avg_amount in om de procentuele kosten te berekenen van: {m}.",
        "m_pair_year": "Per jaar voor ‘{a}’ en ‘{b}’",
        "m_whatif_no_fees": "Voor het verschil in euro zijn de kosten van zowel ‘{a}’ als ‘{b}’ nodig.",
        "m_payments": "{share} van {n} {pn} per maand = {k} {pk} per maand",
        "m_fees": "Kosten per 100 betalingen", "m_time": "Verwerkingstijd per 100 betalingen",
        "m_time_cost": "Verwerkingskost per 100 betalingen", "m_one": "Kost per geval", "m_per100": "Per 100",
        "m_fail": "Mislukte betalingen per 100", "m_disp": "Betwistingen, terugbetalingen en chargebacks per 100",
        "m_full": "Volledige kost per 100 betalingen", "m_year": "Per jaar",
        "m_hours": "Uren per maand, mislukte betalingen en betwistingen inbegrepen",
        "m_share_sum": "De aandelen tellen op tot {f}, niet 100%. Kijk de mix na.",
        "m_days": "Dagen tot het geld op je rekening staat", "m_days_none": "niet opgegeven",
        "m_missing": "Niet opgegeven, als nul geteld: {f}",
        "m_table": "Overzicht", "m_method": "Methode", "m_share": "Aandeel", "m_total_year": "Alle methodes, per jaar",
        "m_avg_days": "Gemiddeld aantal dagen tot het geld binnen is, gewogen naar aandeel",
        "m_whatif": "Wat als {pct} van de betalers overstapt van ‘{a}’ naar ‘{b}’",
        "m_whatif_none": "Voor {b} zijn nog geen kosten of percentages opgeslagen, dus de verschuiving kan niet berekend worden.",
        "m_after": "Per jaar na de verschuiving", "m_today": "nu", "m_diff": "Verschil per jaar",
        "m_hours_diff": "Uren per maand aan het verwerken van betalingen",
        "m_no_methods": "Nog geen betaalmethodes opgeslagen.", "m_no_volume": "Geef eerst payments.per_month in.",
        "twikey": "Twikey", "twikey_en": "Twikey (Engels)", "twikey_tr": "Twikey (vertaald uit het Engels)",
        "auto_note": "Een stap telt mee als een Twikey-pagina zegt dat Twikey hem automatiseert. Niet elke taak erin valt daaronder: in de demo zie je welke van je taken Twikey overneemt.",
        "m_switch_note": "Dit verschil telt het werk niet mee om betalers te laten overstappen, zoals een mandaat laten tekenen en, voor B2B, het laten registreren bij de bank van de betaler.",
        "pkg": "Rij op de prijspagina", "pricing": "Prijspagina",
        "rep_title": "Betaald worden: uren per maand", "rep_as_of": "Schatting op basis van je eigen antwoorden, {d}.",
        "found": "Wat we vonden", "found_line": "{s}: {h} uur per maand, {p} van het totaal ({h} ÷ {t}).",
        "fits": "Waar Twikey past", "modes_today": "Uren per maand volgens hoe het werk nu gebeurt",
        "mode_none": "niet opgegeven", "grows": "Uren per maand die meegroeien met het volume",
        "found_all": "Betaald worden kost je {h} uur per maand",
        "found_some": "De {n} stappen die je beantwoordde kosten {h} uur per maand",
        "found_one": "De ene stap die je beantwoordde kost {h} uur per maand",
        "found_fte_cost": "{f} VTE en {c} per maand aan je uurkost", "found_fte": "{f} VTE",
        "found_cov": "volgens een Twikey-pagina geautomatiseerd",
        "found_nocov": "geen Twikey-pagina zegt dat dit geautomatiseerd wordt",
        "map_cov": "Volgens een Twikey-pagina geautomatiseerd.",
        "gaps_steps": "Nog niet gevraagd: {s}.",
        "gaps_tasks": "Zonder aantal of minuten, dus niet in het totaal: {s}.",
        "m_overlap": "Deze verwerkingsuren overlappen met de uren per stap en tellen niet mee in het totaal aantal uren per maand.",
        "map": "De proceskaart", "table": "Uren per maand, per taak",
        "auto_title": "Stappen die Twikey volgens zijn site automatiseert",
        "auto_sum": "Uren per maand aan stappen die Twikey volgens zijn site automatiseert: {a} van {t} uur{f}.",
        "manual_title": "Stappen waarvan geen Twikey-pagina zegt dat ze geautomatiseerd worden",
        "manual_sum": "Uren per maand aan stappen waarvan geen Twikey-pagina zegt dat ze geautomatiseerd worden: {m} van {t} uur{f}.",
        "none_steps": "Geen van de stappen die je beschreef.",
        "methods": "Betaalmethodes vergeleken", "assumptions": "Aannames en formules",
        "a_answers": "Alle aantallen, minuten, kosten en percentages zijn je eigen antwoorden. Er werd niets gemeten.",
        "a_ranges": "Waar je schatte, is het resultaat zo goed als de schatting.",
        "a_notes": "Je notities", "next": "Volgende stap",
        "footer": "Gemaakt met Payment Hours van Twikey, versie {v}. Het rekent en legt uit. Het contacteert nooit je klanten en raakt je betaalsystemen niet aan.",
        "no_saving": "De uren hierboven zijn de uren die je nu besteedt, volgens je eigen antwoorden. Dit rapport schat niet hoeveel daarvan zouden wegvallen.",
    },
    "fr": {
        "h": "h", "map_title": "Se faire payer, étape par étape (heures par mois)", "not_asked": "pas encore demandé",
        "table_title": "Heures par mois, par tâche", "step": "Étape", "task": "Tâche", "how": "Méthode actuelle",
        "who": "Qui", "a_month": "Nombre par mois", "min_each": "Minutes par opération", "hours_month": "Heures par mois",
        "double": "Avec un volume doublé", "total": "Total", "fixed": "ne croît pas avec le volume",
        "f_task": "Heures par mois = nombre par mois × minutes par opération ÷ 60, arrondi à 0,1 heure. Les totaux additionnent les lignes arrondies.",
        "f_total": "Total des heures par mois", "f_fte": "ETP (équivalent temps plein)",
        "f_fte_month": "heures dans un mois à temps plein", "f_cost": "Coût par mois à votre coût horaire",
        "f_year": "par an", "f_double": "Avec un volume doublé",
        "no_cost": "Aucun coût horaire indiqué : renseignez company.hourly_cost pour voir le coût.",
        "fte_default": "une semaine de {n} heures, la valeur par défaut",
        "fte_given": "une semaine de {n} heures, votre réponse",
        "no_tasks": "Aucune tâche indiquée pour l'instant.",
        "methods_title": "Modes de paiement comparés, avec vos propres chiffres",
        "m_fails_month": "Paiements échoués par mois",
        "m_disp_month": "Litiges, remboursements et rétrofacturations par mois",
        "m_time_cost_month": "Coût du temps par mois", "m_time_diff": "Différence de coût du temps par mois",
        "m_pay_col": "Paiements par mois", "m_hours_col": "Heures par mois", "m_days_col": "Jours avant encaissement",
        "m_no_fees": "Frais non indiqués pour : {m}. Les montants en euros ne sont comparés qu'entre les modes avec frais.",
        "m_need_avg": "Renseignez payments.avg_amount pour calculer les frais en pourcentage de : {m}.",
        "m_pair_year": "Par an pour « {a} » et « {b} »",
        "m_whatif_no_fees": "La différence en euros demande les frais de « {a} » et de « {b} ».",
        "m_payments": "{share} de {n} {pn} par mois = {k} {pk} par mois",
        "m_fees": "Frais pour 100 paiements", "m_time": "Temps de traitement pour 100 paiements",
        "m_time_cost": "Coût de traitement pour 100 paiements", "m_one": "Coût par cas", "m_per100": "Pour 100",
        "m_fail": "Paiements échoués pour 100", "m_disp": "Litiges, remboursements et rétrofacturations pour 100",
        "m_full": "Coût complet pour 100 paiements", "m_year": "Par an",
        "m_hours": "Heures par mois, paiements échoués et litiges compris",
        "m_share_sum": "Les parts totalisent {f}, pas 100 %. Vérifiez la répartition.",
        "m_days": "Jours avant que l'argent soit sur votre compte", "m_days_none": "non indiqué",
        "m_missing": "Non indiqué, compté comme zéro : {f}",
        "m_table": "Synthèse", "m_method": "Mode", "m_share": "Part", "m_total_year": "Tous les modes, par an",
        "m_avg_days": "Nombre moyen de jours avant l'arrivée de l'argent, pondéré par la part",
        "m_whatif": "Simulation : {pct} des payeurs passent de « {a} » à « {b} »",
        "m_whatif_none": "{b} n'a pas encore de frais ni de taux indiqués : le transfert ne peut pas être calculé.",
        "m_after": "Par an après le transfert", "m_today": "aujourd'hui", "m_diff": "Différence par an",
        "m_hours_diff": "Heures par mois de traitement des paiements",
        "m_no_methods": "Aucun mode de paiement indiqué pour l'instant.", "m_no_volume": "Renseignez d'abord payments.per_month.",
        "twikey": "Twikey", "twikey_en": "Twikey (anglais)", "twikey_tr": "Twikey (traduit de l'anglais)",
        "auto_note": "Une étape compte quand une page de Twikey dit que Twikey l'automatise. Toutes ses tâches ne sont pas couvertes : la démo vous montre lesquelles de vos tâches Twikey prend en charge.",
        "m_switch_note": "Cette différence ne compte pas le travail pour faire changer les payeurs, comme la signature d'un mandat et, pour le B2B, son enregistrement auprès de la banque du payeur.",
        "pkg": "Ligne de la page des tarifs", "pricing": "Page des tarifs",
        "rep_title": "Se faire payer : heures par mois", "rep_as_of": "Estimation à partir de vos propres réponses, {d}.",
        "found": "Ce que nous avons trouvé", "found_line": "{s} : {h} heures par mois, {p} du total ({h} ÷ {t}).",
        "fits": "Où Twikey intervient", "modes_today": "Heures par mois selon la façon dont le travail est fait aujourd'hui",
        "mode_none": "non indiqué", "grows": "Heures par mois qui croissent avec le volume",
        "found_all": "Se faire payer vous prend {h} heures par mois",
        "found_some": "Les {n} étapes renseignées prennent {h} heures par mois",
        "found_one": "La seule étape renseignée prend {h} heures par mois",
        "found_fte_cost": "{f} ETP et {c} par mois à votre coût horaire", "found_fte": "{f} ETP",
        "found_cov": "automatisée selon une page de Twikey",
        "found_nocov": "aucune page de Twikey n'indique d'automatisation",
        "map_cov": "Automatisée selon une page de Twikey.",
        "gaps_steps": "Pas encore demandé : {s}.",
        "gaps_tasks": "Nombre ou minutes manquants, donc hors du total : {s}.",
        "m_overlap": "Ces heures de traitement recoupent les heures par étape et ne s'ajoutent pas au total des heures par mois.",
        "map": "La carte du processus", "table": "Heures par mois, par tâche",
        "auto_title": "Étapes que Twikey automatise selon son site",
        "auto_sum": "Heures par mois sur les étapes que Twikey automatise selon son site : {a} sur {t} heures{f}.",
        "manual_title": "Étapes pour lesquelles aucune page de Twikey n'indique d'automatisation",
        "manual_sum": "Heures par mois sur les étapes pour lesquelles aucune page de Twikey n'indique d'automatisation : {m} sur {t} heures{f}.",
        "none_steps": "Aucune des étapes que vous avez décrites.",
        "methods": "Modes de paiement comparés", "assumptions": "Hypothèses et formules",
        "a_answers": "Tous les nombres, minutes, frais et taux sont vos propres réponses. Rien n'a été mesuré.",
        "a_ranges": "Là où vous avez estimé, le résultat vaut ce que vaut l'estimation.",
        "a_notes": "Vos notes", "next": "Prochaine étape",
        "footer": "Réalisé avec Payment Hours par Twikey, version {v}. Il calcule et explique. Il ne contacte jamais vos clients et ne touche pas à vos systèmes de paiement.",
        "no_saving": "Les heures ci-dessus sont celles que vous y consacrez aujourd'hui, selon vos propres réponses. Ce rapport n'estime pas combien d'entre elles disparaîtraient.",
    },
}

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
}

# The method fields the "not given" line names, in the user's language.
FIELD_LABEL = {
    "en": {"minutes": "manual minutes per payment", "fail_pct": "failure rate",
           "fail_minutes": "minutes per failed payment", "dispute_pct": "dispute rate",
           "dispute_minutes": "minutes per dispute", "days": "days until the money is in"},
    "nl": {"minutes": "minuten handwerk per betaling", "fail_pct": "percentage mislukte betalingen",
           "fail_minutes": "minuten per mislukte betaling", "dispute_pct": "percentage betwistingen",
           "dispute_minutes": "minuten per betwisting", "days": "dagen tot het geld binnen is"},
    "fr": {"minutes": "minutes manuelles par paiement", "fail_pct": "taux d'échec",
           "fail_minutes": "minutes par paiement échoué", "dispute_pct": "taux de litiges",
           "dispute_minutes": "minutes par litige", "days": "jours avant l'arrivée de l'argent"},
}


class UserError(Exception):
    pass


# ---------------------------------------------------------------- numbers and formatting

def rnd(x, nd):
    """Round half up (not banker's rounding), so 0.25 -> 0.3 at one decimal."""
    q = 10 ** nd
    return float(int(abs(x) * q + 0.5 + 1e-9)) / q * (1 if x >= 0 else -1)


def num(x, nd, lang):
    s = "{:,.{nd}f}".format(rnd(x, nd), nd=nd)
    if lang == "nl":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    elif lang == "fr":
        s = s.replace(",", " ").replace(".", ",")
    return s


def smart(x, lang):
    """A count or a minute: no decimals when it is whole."""
    return num(x, 0, lang) if abs(x - round(x)) < 1e-9 else num(x, 2 if abs(x * 10 - round(x * 10)) > 1e-9 else 1, lang)


def eur(x, lang):
    """€1,790.40 (en), €1.790,40 (nl), 1 790,40 € (fr)."""
    if lang == "fr":
        return "{:,.2f}".format(rnd(x, 2)).replace(",", " ").replace(".", ",") + " €"
    return "€" + num(x, 2, lang)


NUMBER_WORDS = {  # one to ten spelled out in prose. French counts étapes (feminine): une.
    "en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"],
    "nl": ["nul", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien"],
    "fr": ["zéro", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"],
}
PAYMENT_WORDS = {"en": ("payment", "payments"), "nl": ("betaling", "betalingen"), "fr": ("paiement", "paiements")}


def payments_word(x, lang):
    """Singular for 1 (en, nl) and below 2 (fr: 0 paiement, 1 paiement)."""
    one, many = PAYMENT_WORDS[lang]
    return one if (x < 2 if lang == "fr" else abs(x - 1) < 1e-9) else many


def sum_text(terms, total):
    """a + b = total, or only the total when there is one term (no "6.0 = 6.0")."""
    return total if len(terms) <= 1 else "%s = %s" % (" + ".join(terms), total)


def pct(x, lang):
    """French puts a space before %: 37 % (en and nl: 37%)."""
    return smart(x, lang) + (" %" if lang == "fr" else "%")


def colon(lang):
    """French puts a space before a colon: « Total : 85,6 h »."""
    return " : " if lang == "fr" else ": "


def kv(lang, label, value):
    return label + colon(lang) + value


def date_text(d, lang):
    if lang == "en":
        return "%s %d, %d" % (MONTHS["en"][d.month - 1], d.day, d.year)
    return "%d %s %d" % (d.day, MONTHS[lang][d.month - 1], d.year)


# ---------------------------------------------------------------- safe arithmetic for counts

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate(expr):
    """Numbers, + - * /, parentheses and N% (N divided by 100). Nothing else."""
    text = expr.strip().replace("×", "*").replace("÷", "/")
    if not re.fullmatch(r"[0-9.+\-*/()% ]+", text):
        raise UserError("not a number or a simple sum: %r (use digits, + - * / ( ) and %%, a dot for decimals)" % expr)
    text = re.sub(r"(?<![\d.])0+(?=\d)", "", text)  # 08 -> 8 (Python rejects leading zeros)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", text)
    while True:  # (100-65)% -> ((100-65)/100)
        m = re.search(r"\)\s*%", text)
        if not m:
            break
        depth, start = 0, None
        for i in range(m.start(), -1, -1):
            depth += {")": 1, "(": -1}.get(text[i], 0)
            if depth == 0:
                start = i
                break
        if start is None:
            raise UserError("cannot read %r" % expr)
        text = text[:start] + "(" + text[start:m.start() + 1] + "/100)" + text[m.end():]
    if "%" in text:
        raise UserError("cannot read %r (put %% right after a number or a closing bracket)" % expr)
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            right = ev(n.right)
            if isinstance(n.op, ast.Div) and right == 0:
                raise UserError("division by zero in %r" % expr)
            return _OPS[type(n.op)](ev(n.left), right)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise UserError("cannot read %r" % expr)

    try:
        value = ev(ast.parse(text, mode="eval"))
    except (SyntaxError, ValueError, OverflowError, RecursionError, MemoryError):
        raise UserError("cannot read %r" % expr)
    return check_value(value, expr)


MAX_VALUE = 1e9


def check_value(value, expr):
    """No negative, infinite or absurdly large numbers in the ledger."""
    if not math.isfinite(value) or value > MAX_VALUE:
        raise UserError("%r is too large (at most %s)" % (expr, "{:,.0f}".format(MAX_VALUE)))
    if value < 0:
        raise UserError("negative value in %r" % expr)
    return value


def pretty_expr(expr, lang):
    """400*25%*2 -> 400 × 25% × 2 (decimal commas in nl and fr, 25 % in fr)."""
    s = re.sub(r"\s+", "", expr).replace("×", "*").replace("÷", "/")
    s = s.replace("*", " × ").replace("/", " ÷ ").replace("+", " + ").replace("-", " − ")
    if lang in ("nl", "fr"):
        s = s.replace(".", ",")
    if lang == "fr":
        s = s.replace("%", " %")
    return s


# ---------------------------------------------------------------- ledger

def empty_ledger():
    return {"version": VERSION, "company": {}, "payments": {}, "tasks": {}, "methods": {}, "notes": {}}


def load(path):
    if not os.path.exists(path):
        return empty_ledger()
    try:
        with open(path, encoding="utf-8-sig") as f:  # -sig: a ledger saved by a Windows editor may start with a BOM
            data = json.load(f)
    except ValueError:
        raise UserError("cannot read the ledger %s (not valid JSON)" % path)
    if not isinstance(data, dict):
        raise UserError("cannot read the ledger %s" % path)
    base = empty_ledger()
    base.update(data)
    return base


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def plain_number(key, value, percent=False):
    if not percent:
        return evaluate(value)
    # A percentage field takes one number, with or without %: 30 and 30% both mean 30 (never 0.3). No sums.
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%?\s*", value)
    if not m:
        raise UserError("%s is a percentage: give one number such as 30 or 30%%, not %r" % (key, value))
    v = check_value(float(m.group(1)), value)
    if v > 100:
        raise UserError("%s is a percentage, 0 to 100: %r" % (key, value))
    return v


def set_value(led, key, value):
    value = value.strip()
    parts = key.split(".")
    if key == "whatif":
        m = re.fullmatch(r"([a-z0-9_]+):([a-z0-9_]+):([0-9.]+%?)", value.strip())
        if not m or m.group(1) not in METHODS or m.group(2) not in METHODS or m.group(1) == m.group(2):
            raise UserError("whatif is FROM:TO:PCT with two different methods from %s" % ", ".join(METHODS))
        share = plain_number(key, m.group(3), percent=True)
        led["whatif"] = {"from": m.group(1), "to": m.group(2), "pct": share}
        return
    if parts[0] == "company" and len(parts) == 2 and parts[1] in COMPANY_FIELDS:
        if parts[1] == "lang":
            if value not in LANGS:
                raise UserError("company.lang is en, nl or fr")
            led["company"]["lang"] = value
        else:
            number = plain_number(key, value)
            if parts[1] == "fte_hours_week" and not 1 <= number <= 168:
                raise UserError("company.fte_hours_week is the hours in a full-time week, 1 to 168: %r" % value)
            led["company"][parts[1]] = number
        return
    if parts[0] == "payments" and len(parts) == 2 and parts[1] in PAYMENT_FIELDS:
        led["payments"][parts[1]] = plain_number(key, value)
        return
    if parts[0] == "note" and len(parts) == 2 and re.fullmatch(r"[a-z0-9_]+", parts[1]):
        led["notes"][parts[1]] = value.strip()
        return
    if parts[0] == "task" and len(parts) == 4:
        step, name, field = parts[1:]
        if step not in STEPS:
            raise UserError("unknown step %r, use one of %s" % (step, ", ".join(STEPS)))
        if not re.fullmatch(r"[a-z0-9_]+", name):
            raise UserError("task name %r: use lowercase letters, digits and _" % name)
        if field not in TASK_FIELDS:
            raise UserError("unknown task field %r, use one of %s" % (field, ", ".join(TASK_FIELDS)))
        task = led["tasks"].setdefault(step, {}).setdefault(name, {})
        if field == "count":
            task["count"] = evaluate(value)
            task["count_expr"] = value.strip()
        elif field == "minutes":
            task["minutes"] = plain_number(key, value)
        elif field == "mode":
            if value not in MODES:
                raise UserError("mode is manual, partly or automatic")
            task["mode"] = value
        elif field == "scales":
            if value.lower() not in ("yes", "no", "true", "false"):
                raise UserError("scales is yes or no")
            task["scales"] = value.lower() in ("yes", "true")
        else:
            task[field] = value.strip()
        return
    if parts[0] == "method" and len(parts) == 3:
        method, field = parts[1:]
        if method not in METHODS:
            raise UserError("unknown method %r, use one of %s" % (method, ", ".join(METHODS)))
        if field not in METHOD_FIELDS:
            raise UserError("unknown method field %r, use one of %s" % (field, ", ".join(METHOD_FIELDS)))
        led["methods"].setdefault(method, {})[field] = plain_number(key, value, percent=field in PCT_FIELDS)
        return
    raise UserError("unknown key %r (see the keys at the top of hours.py)" % key)


def unset_value(led, key):
    parts = key.split(".")
    root = {"company": "company", "payments": "payments", "task": "tasks", "method": "methods", "note": "notes"}
    if key == "whatif":
        led.pop("whatif", None)
        return
    if parts[0] not in root:
        raise UserError("unknown key %r" % key)
    if parts[0] == "task" and len(parts) > 1 and parts[1] not in STEPS:
        raise UserError("unknown step %r, use one of %s" % (parts[1], ", ".join(STEPS)))
    if parts[0] == "method" and len(parts) > 1 and parts[1] not in METHODS:
        raise UserError("unknown method %r, use one of %s" % (parts[1], ", ".join(METHODS)))
    node = led[root[parts[0]]]
    for p in parts[1:-1]:
        node = node.get(p, {}) if isinstance(node, dict) else {}
    if not isinstance(node, dict):
        node = {}
    if len(parts) == 1:
        led[root[parts[0]]] = {}
    else:
        node.pop(parts[-1], None)
    if parts[0] == "task" and len(parts) >= 3 and not led["tasks"].get(parts[1]):
        led["tasks"].pop(parts[1], None)


# ---------------------------------------------------------------- claims

def load_claims(path=None):
    with open(path or CLAIMS, encoding="utf-8") as f:
        text = f.read()
    claims = {}
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        lines = block.splitlines()
        fields = {}
        for line in lines[1:]:
            if line.startswith("## "):
                break
            m = re.match(r"- ([a-z-]+): (.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2).strip()
        for k in ("steps", "methods"):
            fields[k] = [x.strip() for x in fields.get(k, "").split(",") if x.strip()]
        claims[lines[0].strip()] = fields
    m = re.search(r"^## Pricing page\n\n((?:- .*\n?)+)", text, re.M)
    pricing = dict(re.findall(r"- ([a-z]+): (\S+)", m.group(1))) if m else {}
    return claims, pricing


def claim_text(c, lang):
    """(label, text, url, package) in the user's language, English when there is no line in it."""
    t = T[lang]
    if lang == "en":
        return t["twikey"], c["en"], c["source"], c.get("package")
    if lang in c:
        if lang == "nl" and "nl-kind" in c:  # our translation: labelled as one, linking the English page
            return t["twikey_tr"], c[lang], c["nl-kind"].split(" of ", 1)[1].strip(), c.get("package-" + lang)
        return t["twikey"], c[lang], c.get("source-" + lang, c["source"]), c.get("package-" + lang)
    return t["twikey_en"], c["en"], c["source"], c.get("package")


def claims_for(kind, key, claims):
    return [cid for cid, c in claims.items() if key in c.get(kind, []) or (kind == "methods" and "all" in c.get(kind, []))]


def claim_lines(cids, claims, lang, pkg=True):
    out = []
    for cid in cids:
        label, text, url, package = claim_text(claims[cid], lang)
        out.append("%s (%s)" % (kv(lang, label, text), url))
        if pkg and package:
            out.append("  " + kv(lang, T[lang]["pkg"], package))
    return out


# ---------------------------------------------------------------- process: hours per task and step

def task_rows(led):
    """One row per task, in step order, with the rounded hours shown. The count and the minutes are taken as the
    table shows them (two decimals at most), so every row's formula gives exactly the hours printed."""
    rows = []
    for step in STEPS:
        for name, task in sorted(led["tasks"].get(step, {}).items()):
            count = None if task.get("count") is None else rnd(task["count"], 2)
            minutes = None if task.get("minutes") is None else rnd(task["minutes"], 2)
            scales = task.get("scales", step != "reporting")
            row = {"step": step, "name": name, "label": task.get("label") or None,
                   "mode": task.get("mode"), "who": task.get("who", ""), "count": count,
                   "count_expr": task.get("count_expr"), "minutes": minutes, "scales": scales,
                   "complete": count is not None and minutes is not None}
            if row["complete"]:
                exact = count * minutes / 60.0
                row["hours"] = rnd(exact, 1)
                row["hours_double"] = rnd(exact * 2, 1) if scales else row["hours"]
            rows.append(row)
    return rows


def totals(led):
    rows = task_rows(led)
    done = [r for r in rows if r["complete"]]
    step_hours = {}
    for r in done:
        step_hours[r["step"]] = rnd(step_hours.get(r["step"], 0.0) + r["hours"], 1)
    total = rnd(sum(r["hours"] for r in done), 1)
    total_double = rnd(sum(r["hours_double"] for r in done), 1)
    week = led["company"].get("fte_hours_week", DEFAULT_FTE_HOURS_WEEK)
    fte_month = week * 52 / 12.0
    cost = led["company"].get("hourly_cost")
    return {
        "rows": rows, "done": done, "missing": [r for r in rows if not r["complete"]], "step_hours": step_hours,
        "total": total, "total_double": total_double, "fte_week": week,
        "fte_week_given": "fte_hours_week" in led["company"], "fte_month": rnd(fte_month, 1),
        "fte": rnd(total / rnd(fte_month, 1), 2) if total else 0.0,
        "fte_double": rnd(total_double / rnd(fte_month, 1), 2) if total_double else 0.0,
        "hourly_cost": cost,
        "cost_month": rnd(total * cost, 2) if cost is not None else None,
        "cost_month_double": rnd(total_double * cost, 2) if cost is not None else None,
    }


def hours_join(values, lang):
    return " + ".join(num(v, 1, lang) for v in values) if values else "0"


def task_label(r, lang):
    """The user's own task name. Without one: the step's name for the main task, else the task id in words."""
    if r["label"]:
        return r["label"]
    return STEP_LABEL[lang][r["step"]] if r["name"] == "main" else r["name"].replace("_", " ")


def gaps_lines(led, lang):
    """Steps not asked yet and tasks without a count or minutes, so a sparse ledger never reads as complete."""
    t, out = T[lang], []
    steps = [s for s in STEPS if not led["tasks"].get(s)]
    if steps:
        out.append("- " + t["gaps_steps"].format(
            s=", ".join("%d. %s" % (STEPS.index(s) + 1, STEP_LABEL[lang][s]) for s in steps)))
    open_rows = [r for r in task_rows(led) if not r["complete"]]
    if open_rows:
        out.append("- " + t["gaps_tasks"].format(
            s=", ".join("%d. %s" % (STEPS.index(r["step"]) + 1, task_label(r, lang)) for r in open_rows)))
    return out


def process_map(led, lang, claims=None):
    t, tot = T[lang], totals(led)
    covered = set(s for c in (claims or {}).values() for s in c.get("steps", []))
    lines = [t["map_title"], ""]
    width = max(len(v) for v in STEP_LABEL[lang].values())
    rows = []
    for step in STEPS:
        tasks = led["tasks"].get(step, {})
        modes = sorted(set(x.get("mode") for x in tasks.values() if x.get("mode")), key=MODES.index)
        mode = "[" + ", ".join(MODE_LABEL[lang][m] for m in modes) + "]" if modes else ""
        if step in tot["step_hours"]:
            hours = num(tot["step_hours"][step], 1, lang) + " " + t["h"]
        else:
            hours = t["not_asked"] if not tasks else "?"
        rows.append((step, mode, hours))
    mode_width = max(len(r[1]) for r in rows)
    hours_width = max(len(r[2]) for r in rows)
    for i, (step, mode, hours) in enumerate(rows, 1):
        mark = " *" if claims is not None and step in covered and led["tasks"].get(step) else ""
        lines.append(("%d. %-*s  %-*s  %*s%s" % (i, width, STEP_LABEL[lang][step], mode_width, mode, hours_width,
                                                hours, mark)).rstrip())
        if i < len(STEPS):
            lines.append("   |")
    lines.append("")
    lines.append(kv(lang, t["total"], "%s %s" % (num(tot["total"], 1, lang), t["h"])))
    if claims is not None:
        lines.append("* " + t["map_cov"])
    return "\n".join(lines)


def process_table(led, lang):
    t, tot = T[lang], totals(led)
    out = ["| %s | %s | %s | %s | %s | %s | %s | %s |" % (t["step"], t["task"], t["how"], t["who"], t["a_month"],
                                                          t["min_each"], t["hours_month"], t["double"]),
           "|---|---|---|---|---:|---:|---:|---:|"]
    for r in tot["rows"]:
        count = "?" if r["count"] is None else (
            "%s = %s" % (pretty_expr(r["count_expr"], lang), smart(r["count"], lang))
            if r["count_expr"] and not re.fullmatch(r"[0-9.]+", r["count_expr"].strip()) else smart(r["count"], lang))
        minutes = "?" if r["minutes"] is None else smart(r["minutes"], lang)
        if r["complete"]:
            hours = "%s × %s ÷ 60 = %s" % (smart(r["count"], lang), minutes, num(r["hours"], 1, lang))
            if r["scales"]:
                double = "%s × 2 × %s ÷ 60 = %s" % (smart(r["count"], lang), minutes, num(r["hours_double"], 1, lang))
            else:
                double = "%s (%s)" % (num(r["hours_double"], 1, lang), t["fixed"])
        else:
            hours = double = "?"
        out.append("| %d. %s | %s | %s | %s | %s | %s | %s | %s |" % (
            STEPS.index(r["step"]) + 1, STEP_LABEL[lang][r["step"]], task_label(r, lang),
            MODE_LABEL[lang].get(r["mode"], "-") if r["mode"] else "-", r["who"] or "-", count, minutes, hours, double))
    return "\n".join(out)


def process_formulas(led, lang):
    t, tot = T[lang], totals(led)
    done = tot["done"]
    lines = ["- " + t["f_task"],
             "- " + kv(lang, t["f_total"], "%s %s" % (sum_text([num(r["hours"], 1, lang) for r in done],
                                                               num(tot["total"], 1, lang)), t["h"]))]
    week = smart(tot["fte_week"], lang)
    basis = (t["fte_given"] if tot["fte_week_given"] else t["fte_default"]).format(n=week)
    lines.append("- " + kv(lang, t["f_fte"], "%s ÷ %s = %s (%s = %s × 52 ÷ 12 = %s, %s)" % (
        num(tot["total"], 1, lang), num(tot["fte_month"], 1, lang), num(tot["fte"], 2, lang),
        t["f_fte_month"], week, num(tot["fte_month"], 1, lang), basis)))
    if tot["hourly_cost"] is not None:
        c = tot["hourly_cost"]
        lines.append("- " + kv(lang, t["f_cost"], "%s × %s = %s (%s)" % (
            num(tot["total"], 1, lang), eur(c, lang), eur(tot["cost_month"], lang),
            kv(lang, t["f_year"], "%s × 12 = %s" % (eur(tot["cost_month"], lang),
                                                    eur(rnd(tot["cost_month"] * 12, 2), lang))))))
    else:
        lines.append("- " + t["no_cost"])
    double = [kv(lang, t["f_double"], "%s %s" % (sum_text([num(r["hours_double"], 1, lang) for r in done],
                                                          num(tot["total_double"], 1, lang)), t["h"])),
              kv(lang, t["f_fte"], "%s ÷ %s = %s" % (num(tot["total_double"], 1, lang),
                                                     num(tot["fte_month"], 1, lang), num(tot["fte_double"], 2, lang)))]
    if tot["hourly_cost"] is not None:
        double.append(kv(lang, t["f_cost"], "%s × %s = %s" % (num(tot["total_double"], 1, lang),
                                                              eur(tot["hourly_cost"], lang),
                                                              eur(tot["cost_month_double"], lang))))
    lines.append("- " + ". ".join(double))
    return "\n".join(lines)


def cmd_process(led, lang):
    if not led["tasks"]:
        return T[lang]["no_tasks"]
    parts = ["```\n%s\n```" % process_map(led, lang), process_table(led, lang),
             "\n".join(mix_lines(led, lang) + gaps_lines(led, lang)), process_formulas(led, lang)]
    return "\n\n".join(p for p in parts if p)


def mix_lines(led, lang):
    """Two neutral lines: the hours by how the work is done today, and the hours that grow with volume."""
    t, tot = T[lang], totals(led)
    done = tot["done"]
    if not done:
        return []
    groups = []
    for mode in MODES + (None,):
        rows = [r for r in done if r["mode"] == mode]
        if rows:
            label = MODE_LABEL[lang][mode] if mode else t["mode_none"]
            total = rnd(sum(r["hours"] for r in rows), 1)
            groups.append("%s %s %s" % (label, sum_text([num(r["hours"], 1, lang) for r in rows],
                                                        num(total, 1, lang)), t["h"]))
    fixed = rnd(sum(r["hours"] for r in done if not r["scales"]), 1)
    today = num(tot["total"], 1, lang)
    double = num(tot["total_double"], 1, lang)
    if fixed:
        f = num(fixed, 1, lang)
        today = "%s − %s = %s" % (today, f, num(rnd(tot["total"] - fixed, 1), 1, lang))
        double = "%s − %s = %s" % (double, f, num(rnd(tot["total_double"] - fixed, 1), 1, lang))
    groups = groups[:1] + [g[0].upper() + g[1:] for g in groups[1:]]  # one sentence per sum
    return ["- " + kv(lang, t["modes_today"], ". ".join(groups)) + ".",
            "- %s. %s." % (kv(lang, t["grows"], "%s %s" % (today, t["h"])),
                           kv(lang, t["f_double"], "%s %s" % (double, t["h"])))]


# ---------------------------------------------------------------- methods

def has_fees(m):
    """A method has fees when the user gave a fixed or a percentage fee (0 counts as given). Fees are optional."""
    return "fee_fixed" in m or "fee_pct" in m


def method_calc(m, avg, hourly):
    """Per 100 payments of one method, from the user's own numbers. Hours stay exact (100 × minutes ÷ 60) and are
    rounded only where they are printed. Each money line is rounded to the cent once. A fee the user did not give
    is left out of the formulas, and without an hourly cost the time is not priced."""
    g = lambda k: m.get(k, 0.0)
    h = hourly or 0.0
    fee_each = g("fee_fixed") + (g("fee_pct") / 100.0 * avg if avg is not None else 0.0)
    fees = rnd(100 * fee_each, 2)
    hours = 100 * g("minutes") / 60.0
    time_cost = rnd(hours * h, 2)
    fails = rnd(100 * g("fail_pct") / 100.0, 2)
    fail_each = rnd(g("fail_fee") + g("fail_minutes") / 60.0 * h, 2)
    fail_cost = rnd(fails * fail_each, 2)
    disputes = rnd(100 * g("dispute_pct") / 100.0, 2)
    disp_each = rnd(g("dispute_fee") + g("dispute_minutes") / 60.0 * h, 2)
    disp_cost = rnd(disputes * disp_each, 2)
    full = rnd(fees + time_cost + fail_cost + disp_cost, 2)
    hours_all = hours + fails * g("fail_minutes") / 60.0 + disputes * g("dispute_minutes") / 60.0
    return {"fee_each": fee_each, "fees": fees, "hours": hours, "time_cost": time_cost, "fails": fails,
            "fail_each": fail_each, "fail_cost": fail_cost, "disputes": disputes, "disp_each": disp_each,
            "disp_cost": disp_cost, "full": full, "hours_all": hours_all}


def per_year(full_per_100, payments_month):
    return rnd(full_per_100 * payments_month * 12 / 100.0, 2)


def methods_state(led, shares=None):
    p = led["payments"]
    per_month, avg = p.get("per_month"), p.get("avg_amount")
    hourly = led["company"].get("hourly_cost")
    out = []
    for mid in METHODS:
        m = led["methods"].get(mid)
        if m is None:
            continue
        share = (shares or {}).get(mid, m.get("share", 0.0))
        k = rnd(per_month * share / 100.0, 2)
        c = method_calc(m, avg, hourly)
        hours_month = rnd(c["hours_all"] * k / 100.0, 1)
        fees = has_fees(m) and ("fee_pct" not in m or avg is not None)  # a percentage fee needs the average payment
        out.append({"id": mid, "m": m, "share": share, "payments": k, "calc": c, "fees": fees,
                    "year": per_year(c["full"], k) if fees else None, "hours_month": hours_month,
                    "fails_month": rnd(k * m.get("fail_pct", 0.0) / 100.0, 2),
                    "disputes_month": rnd(k * m.get("dispute_pct", 0.0) / 100.0, 2),
                    "time_cost": rnd(hours_month * hourly, 2) if hourly is not None else None})
    return out


TIME_FIELDS = ("minutes", "fail_pct", "fail_minutes", "dispute_pct", "dispute_minutes", "days")


def missing_time(m):
    """The time fields not given (counted as zero). Minutes per failure or dispute only matter with a rate."""
    return [f for f in TIME_FIELDS if f not in m
            and not (f == "fail_minutes" and not m.get("fail_pct"))
            and not (f == "dispute_minutes" and not m.get("dispute_pct"))]
BRANDS = ("bancontact", "wero", "paypal", "wallet")


def method_mid(mid, lang):
    """A method's name inside a sentence: common nouns lowercase (bank transfer, virement), brands and SEPA as is."""
    label = METHOD_LABEL[lang][mid]
    if mid in BRANDS or len(label) < 2 or not label[1].islower():
        return label
    return label[0].lower() + label[1:]


def method_rules(mid, claims):
    """The Twikey rule lines for one method (the general orchestration line excluded)."""
    return [cid for cid in claims_for("methods", mid, claims) if "all" not in claims[cid]["methods"]]


def method_volume(s, per_month, lang):
    return T[lang]["m_payments"].format(share=pct(s["share"], lang), n=smart(per_month, lang),
                                        pn=payments_word(per_month, lang), k=smart(s["payments"], lang),
                                        pk=payments_word(s["payments"], lang))


def year_formula(s, lang):
    return "%s × %s × 12 ÷ 100 = %s" % (eur(s["calc"]["full"], lang), smart(s["payments"], lang), eur(s["year"], lang))


def hours_formula(s, lang):
    """Hours a month of one method, from the exact inputs, so the line recomputes to what it prints."""
    m, c, L = s["m"], s["calc"], lambda x: smart(x, lang)
    return "(100 × %s ÷ 60 + %s × %s ÷ 60 + %s × %s ÷ 60) × %s ÷ 100 = %s %s" % (
        L(m.get("minutes", 0)), L(c["fails"]), L(m.get("fail_minutes", 0)), L(c["disputes"]),
        L(m.get("dispute_minutes", 0)), L(s["payments"]), num(s["hours_month"], 1, lang), T[lang]["h"])


def fees_formula(m, avg, c, lang):
    """100 × €0.15, 100 × 1.4% × €850.00 or 100 × (€0.25 + 1.4% × €850.00): only the fees the user gave."""
    parts = ([eur(m["fee_fixed"], lang)] if "fee_fixed" in m else []) + (
        ["%s × %s" % (pct(m["fee_pct"], lang), eur(avg, lang))] if "fee_pct" in m else [])
    inner = parts[0] if len(parts) == 1 else "(%s)" % " + ".join(parts)
    return "100 × %s = %s" % (inner, eur(c["fees"], lang))


def incident_line(lang, label, rate, n, fee, minutes, hc, each, cost):
    """Failures or disputes per 100, one statement per equality: 100 × 3% = 3. Cost of one: ... Per 100: ...
    fee is None when the user gave none, hc is None without an hourly cost: those parts are left out."""
    t = T[lang]
    parts = ([fee] if fee is not None else []) + (["%s min ÷ 60 × %s" % (minutes, hc)] if hc is not None else [])
    one = each if not parts or parts == [each] else "%s = %s" % (" + ".join(parts), each)
    return kv(lang, label, "100 × %s = %s. %s. %s" % (
        rate, n, kv(lang, t["m_one"], one), kv(lang, t["m_per100"], "%s × %s = %s" % (n, each, cost))))


def method_block(s, per_month, avg, hourly, lang, days=True):
    """One method: its volume (the heading), then time (hours, failures, disputes, days, time cost) and, only when
    the user gave fees, the euro lines. Every line with its formula."""
    t, m, c, L = T[lang], s["m"], s["calc"], (lambda x: smart(x, lang))
    hc = eur(hourly, lang) if hourly is not None else None
    head = kv(lang, "**%s**" % METHOD_LABEL[lang][s["id"]], method_volume(s, per_month, lang))
    lines = [
        kv(lang, t["m_hours"], hours_formula(s, lang)),
        kv(lang, t["m_fails_month"], "%s × %s = %s" % (L(s["payments"]), pct(m.get("fail_pct", 0), lang),
                                                        L(s["fails_month"]))),
        kv(lang, t["m_disp_month"], "%s × %s = %s" % (L(s["payments"]), pct(m.get("dispute_pct", 0), lang),
                                                       L(s["disputes_month"]))),
    ]
    if days:
        lines.append(kv(lang, t["m_days"], L(m["days"]) if "days" in m else t["m_days_none"]))
    if hourly is not None:
        lines.append(kv(lang, t["m_time_cost_month"], "%s %s × %s = %s" % (
            num(s["hours_month"], 1, lang), t["h"], hc, eur(s["time_cost"], lang))))
    missing = missing_time(m)
    if missing:
        lines.append(t["m_missing"].format(f=", ".join(FIELD_LABEL[lang][f] for f in missing)))
    if s["fees"]:
        lines.append(kv(lang, t["m_fees"], fees_formula(m, avg, c, lang)))
        if hourly is not None:
            lines.append(kv(lang, t["m_time_cost"], "100 × %s min ÷ 60 × %s = %s" % (
                L(m.get("minutes", 0)), hc, eur(c["time_cost"], lang))))
        lines.append(incident_line(
            lang, t["m_fail"], pct(m.get("fail_pct", 0), lang), L(c["fails"]),
            eur(m["fail_fee"], lang) if "fail_fee" in m else None, L(m.get("fail_minutes", 0)), hc,
            eur(c["fail_each"], lang), eur(c["fail_cost"], lang)))
        lines.append(incident_line(
            lang, t["m_disp"], pct(m.get("dispute_pct", 0), lang), L(c["disputes"]),
            eur(m["dispute_fee"], lang) if "dispute_fee" in m else None, L(m.get("dispute_minutes", 0)), hc,
            eur(c["disp_each"], lang), eur(c["disp_cost"], lang)))
        terms = [eur(c["fees"], lang)] + ([eur(c["time_cost"], lang)] if hourly is not None else []) + [
            eur(c["fail_cost"], lang), eur(c["disp_cost"], lang)]
        lines.append(kv(lang, t["m_full"], sum_text(terms, eur(c["full"], lang))))
        lines.append(kv(lang, t["m_year"], year_formula(s, lang)))
    return head, lines


def cmd_methods(led, lang, claims=None, summary_only=False):
    t = T[lang]
    if not led["methods"]:
        return t["m_no_methods"]
    p = led["payments"]
    if p.get("per_month") is None:
        return t["m_no_volume"]
    claims = claims if claims is not None else load_claims()[0]
    per_month, avg = p["per_month"], p.get("avg_amount")
    hourly = led["company"].get("hourly_cost")
    state = methods_state(led)
    out = []
    if not summary_only:
        out += ["## " + t["methods_title"], ""]
        if hourly is None:
            out += [t["no_cost"], ""]
        for s in state:
            head, lines = method_block(s, per_month, avg, hourly, lang)
            out.append(head)
            out.extend("- " + x for x in lines)
            out.append("")
        out += ["### " + t["m_table"], ""]
    cols = [t["m_method"], t["m_share"], t["m_pay_col"], t["m_hours_col"], t["m_fails_month"], t["m_days_col"]]
    cols += [t["m_time_cost_month"]] if hourly is not None else []
    out.append("| %s |" % " | ".join(cols))
    out.append("|---|" + "---:|" * (len(cols) - 1))
    for s in state:
        row = [METHOD_LABEL[lang][s["id"]], pct(s["share"], lang), smart(s["payments"], lang),
               num(s["hours_month"], 1, lang), smart(s["fails_month"], lang),
               smart(s["m"]["days"], lang) if "days" in s["m"] else "?"]
        row += [eur(s["time_cost"], lang)] if hourly is not None else []
        out.append("| %s |" % " | ".join(row))
    hours_today = rnd(sum(s["hours_month"] for s in state), 1)
    out.append("")
    out.append("- " + kv(lang, t["m_hours_diff"], "%s %s" % (
        sum_text([num(s["hours_month"], 1, lang) for s in state], num(hours_today, 1, lang)), t["h"])))
    out.append("- " + t["m_overlap"])
    out.append("- " + avg_days_line(state, lang))
    share_sum = rnd(sum(s["share"] for s in state), 2)
    if abs(share_sum - 100) > 0.01:
        out.append("- " + t["m_share_sum"].format(f=sum_text([pct(s["share"], lang) for s in state],
                                                             pct(share_sum, lang))))
    out.extend(euro_lines(state, lang))
    if led.get("whatif"):
        out.append("")
        out.extend(whatif_lines(led, lang, state))
    if not summary_only:  # the Twikey lines come last, never in the body
        rules = method_claim_lines(state, claims, lang)
        if rules:
            out += ["", "## " + t["fits"], ""] + rules
    return "\n".join(out)


def method_claim_lines(state, claims, lang):
    """The Twikey rule lines for the methods in play, then the general orchestration line."""
    out = []
    for s in state:
        out.extend("- %s. %s" % (METHOD_LABEL[lang][s["id"]], x)
                   for x in claim_lines(method_rules(s["id"], claims), claims, lang, pkg=False))
    general = [cid for cid, c in claims.items() if "all" in c.get("methods", [])]
    out.extend("- " + x for x in claim_lines(general, claims, lang, pkg=False))
    return out


def euro_lines(state, lang):
    """Euro only for methods with fees. A total across methods only when every method in play has fees."""
    t = T[lang]
    with_fees = [s for s in state if s["fees"]]
    no_fees = [s for s in state if not has_fees(s["m"])]
    need_avg = [s for s in state if has_fees(s["m"]) and not s["fees"]]
    out = []
    if with_fees:
        out += ["", "| %s | %s | %s |" % (t["m_method"], t["m_full"], t["m_year"]), "|---|---:|---:|"]
        out += ["| %s | %s | %s |" % (METHOD_LABEL[lang][s["id"]], eur(s["calc"]["full"], lang), eur(s["year"], lang))
                for s in with_fees]
        out.append("")
        if len(with_fees) == len(state):
            total_year = rnd(sum(s["year"] for s in state), 2)
            out.append("- " + kv(lang, t["m_total_year"], sum_text([eur(s["year"], lang) for s in state],
                                                                   eur(total_year, lang))))
        if no_fees:
            out.append("- " + t["m_no_fees"].format(m=", ".join(METHOD_LABEL[lang][s["id"]] for s in no_fees)))
    if need_avg:
        out += ([] if with_fees else [""]) + ["- " + t["m_need_avg"].format(
            m=", ".join(METHOD_LABEL[lang][s["id"]] for s in need_avg))]
    return out


def avg_days(state, lang):
    """(formula, value) of the average days until the money is in, weighted by share. None without days."""
    known = [s for s in state if "days" in s["m"] and s["share"] > 0]
    if not known:
        return None
    if len(known) == 1:  # one method with days: its own days, no one-term weighted average
        value = smart(known[0]["m"]["days"], lang)
        return value, value
    total_share = sum(s["share"] for s in known)
    value = num(rnd(sum(s["share"] * s["m"]["days"] for s in known) / total_share, 1), 1, lang)
    terms = " + ".join("%s × %s" % (pct(s["share"], lang), smart(s["m"]["days"], lang)) for s in known)
    return "(%s) ÷ %s = %s" % (terms, pct(total_share, lang), value), value


def avg_days_line(state, lang, today=None):
    t = T[lang]
    got = avg_days(state, lang)
    text = got[0] if got else t["m_days_none"]
    if today is not None:
        before = avg_days(today, lang)
        text += " (%s %s)" % (t["m_today"], before[1] if before else t["m_days_none"])
    return kv(lang, t["m_avg_days"], text)


def whatif_lines(led, lang, state):
    """The shift, time first: hours, failures, days and time cost today and after. Euro only with fees for both."""
    t = T[lang]
    w = led["whatif"]
    a, b, share_pct = w["from"], w["to"], w["pct"]
    la, lb = METHOD_LABEL[lang][a], METHOD_LABEL[lang][b]
    out = ["### " + t["m_whatif"].format(pct=pct(share_pct, lang), a=method_mid(a, lang), b=method_mid(b, lang)), ""]
    if b not in led["methods"] or a not in led["methods"]:
        return out + [t["m_whatif_none"].format(b=lb if b not in led["methods"] else la)]
    per_month = led["payments"]["per_month"]
    shares = {s["id"]: s["share"] for s in state}
    moved = rnd(shares[a] * share_pct / 100.0, 2)
    new = dict(shares)
    new[a] = rnd(shares[a] - moved, 2)
    new[b] = rnd(shares.get(b, 0.0) + moved, 2)
    after = methods_state(led, new)
    hourly = led["company"].get("hourly_cost")
    hours_today = rnd(sum(s["hours_month"] for s in state), 1)
    hours_after = rnd(sum(s["hours_month"] for s in after), 1)
    fails_today = rnd(sum(s["fails_month"] for s in state), 2)
    fails_after = rnd(sum(s["fails_month"] for s in after), 2)
    signed = lambda d: ("−" if d < 0 else "+") + eur(abs(d), lang)
    out.append("- %s. %s" % (
        kv(lang, la, "%s − %s × %s = %s" % (pct(shares[a], lang), pct(shares[a], lang), pct(share_pct, lang),
                                           pct(new[a], lang))),
        kv(lang, lb, "%s + %s = %s" % (pct(shares.get(b, 0.0), lang), pct(moved, lang), pct(new[b], lang)))))
    for s in after:
        if s["id"] in (a, b):
            parts = [kv(lang, METHOD_LABEL[lang][s["id"]], method_volume(s, per_month, lang)),
                     kv(lang, t["m_hours"], hours_formula(s, lang))]
            out.append("  - " + ". ".join(parts))
    out.append("- " + kv(lang, t["m_hours_diff"], "%s %s (%s %s %s)" % (
        sum_text([num(s["hours_month"], 1, lang) for s in after], num(hours_after, 1, lang)), t["h"], t["m_today"],
        sum_text([num(s["hours_month"], 1, lang) for s in state], num(hours_today, 1, lang)), t["h"])))
    out.append("- " + kv(lang, t["m_fails_month"], "%s (%s %s)" % (
        sum_text([smart(s["fails_month"], lang) for s in after], smart(fails_after, lang)), t["m_today"],
        sum_text([smart(s["fails_month"], lang) for s in state], smart(fails_today, lang)))))
    out.append("- " + avg_days_line(after, lang, today=state))
    if hourly is not None:
        hc = eur(hourly, lang)
        cost_after, cost_today = rnd(hours_after * hourly, 2), rnd(hours_today * hourly, 2)
        out.append("- " + kv(lang, t["m_time_cost_month"], "%s %s × %s = %s (%s %s %s × %s = %s)" % (
            num(hours_after, 1, lang), t["h"], hc, eur(cost_after, lang), t["m_today"], num(hours_today, 1, lang),
            t["h"], hc, eur(cost_today, lang))))
        out.append("- " + kv(lang, t["m_time_diff"], "%s − %s = %s" % (
            eur(cost_after, lang), eur(cost_today, lang), signed(rnd(cost_after - cost_today, 2)))))
    now = {s["id"]: s for s in state}
    then = {s["id"]: s for s in after}
    ma, mb = method_mid(a, lang), method_mid(b, lang)
    if now[a]["fees"] and now[b]["fees"]:  # only the two methods change, so their per-year lines carry the change
        pair_after = rnd(then[a]["year"] + then[b]["year"], 2)
        pair_today = rnd(now[a]["year"] + now[b]["year"], 2)
        out.append("- " + kv(lang, t["m_pair_year"].format(a=ma, b=mb), "%s (%s %s)" % (
            sum_text([eur(then[a]["year"], lang), eur(then[b]["year"], lang)], eur(pair_after, lang)), t["m_today"],
            sum_text([eur(now[a]["year"], lang), eur(now[b]["year"], lang)], eur(pair_today, lang)))))
        out.append("  - %s. %s" % (kv(lang, METHOD_LABEL[lang][a], year_formula(then[a], lang)),
                                   kv(lang, METHOD_LABEL[lang][b], year_formula(then[b], lang))))
        out.append("- " + kv(lang, t["m_diff"], "%s − %s = %s" % (
            eur(pair_after, lang), eur(pair_today, lang), signed(rnd(pair_after - pair_today, 2)))))
    else:
        out.append("- " + t["m_whatif_no_fees"].format(a=ma, b=mb))
    out.append("- " + t["m_switch_note"])
    return out


# ---------------------------------------------------------------- report

def covered_steps(claims):
    """Steps a Twikey line lists under `steps`: the steps Twikey's site says it automates."""
    return set(s for c in claims.values() for s in c.get("steps", []))


def by_step(pairs):
    return sorted(pairs, key=lambda p: STEPS.index(p[0]))


def cmd_report(led, lang, today=None):
    t = T[lang]
    claims, pricing = load_claims()
    tot = totals(led)
    today = today or datetime.date.today()
    out = ["# " + t["rep_title"], "", t["rep_as_of"].format(d=date_text(today, lang)), ""]
    if not tot["done"]:
        return "\n".join(out + [t["no_tasks"]])
    covered = covered_steps(claims)
    total = tot["total"]
    asked = [s for s in STEPS if led["tasks"].get(s)]
    if len(asked) == len(STEPS):
        head = t["found_all"].format(h=num(total, 1, lang))
    elif len(asked) == 1:
        head = t["found_one"].format(h=num(total, 1, lang))
    else:
        head = t["found_some"].format(n=NUMBER_WORDS[lang][len(asked)], h=num(total, 1, lang))
    if tot["hourly_cost"] is not None:
        tail = t["found_fte_cost"].format(f=num(tot["fte"], 2, lang), c=eur(tot["cost_month"], lang))
    else:
        tail = t["found_fte"].format(f=num(tot["fte"], 2, lang))
    out += ["## " + t["found"], "", kv(lang, head, tail) + ".", ""]
    # The biggest steps first. Steps with 0.0 hours (and so a zero total) give no line: no "0% (0.0 ÷ 0.0)".
    ranked = sorted([p for p in tot["step_hours"].items() if p[1] > 0], key=lambda p: (-p[1], STEPS.index(p[0])))
    for i, (step, h) in enumerate(ranked[:3], 1):
        share = pct(rnd(100.0 * h / total, 0), lang)
        out.append("%d. %s" % (i, t["found_line"].format(
            s=STEP_LABEL[lang][step], h=num(h, 1, lang), p=share, t=num(total, 1, lang))))
    # The body stays neutral: no Twikey line before the final section.
    out += ["", "## " + t["map"], "", "```", process_map(led, lang), "```", "",
            "## " + t["table"], "", process_table(led, lang), ""]
    out += mix_lines(led, lang) + gaps_lines(led, lang) + ["", t["no_saving"], ""]
    p = led["payments"]
    with_methods = bool(led["methods"]) and p.get("per_month") is not None
    if with_methods:
        out += ["## " + t["methods"], "", cmd_methods(led, lang, claims, summary_only=True), ""]
    out += ["## " + t["assumptions"], "", "- " + t["a_answers"], "- " + t["a_ranges"], process_formulas(led, lang)]
    if with_methods:
        hourly = led["company"].get("hourly_cost")
        for s in methods_state(led):
            head, lines = method_block(s, p["per_month"], p.get("avg_amount"), hourly, lang, days=False)
            out.append("- " + head)
            out.extend("  - " + x for x in lines)
    for _, note in sorted(led["notes"].items()):  # the user's own words only: the keys are English ids
        out.append("- " + note)
    # Where Twikey fits: once, at the end. Steps a Twikey line lists under `steps` that have hours, their sum,
    # the note on what counts, the rule lines for the methods in play, then the demo link.
    auto = by_step((s, h) for s, h in tot["step_hours"].items() if s in covered and h > 0)
    out += ["", "## " + t["fits"], ""]
    for step, h in auto:
        out.append(kv(lang, "**%d. %s**" % (STEPS.index(step) + 1, STEP_LABEL[lang][step]),
                      "%s %s" % (num(h, 1, lang), t["h"])))
        out.extend("- " + x for x in claim_lines(claims_for("steps", step, claims), claims, lang, pkg=False))
        out.append("")
    if auto:
        a_sum = rnd(sum(h for _, h in auto), 1)
        terms = " (%s)" % hours_join([h for _, h in auto], lang) if len(auto) > 1 else ""
        out += [t["auto_sum"].format(a=num(a_sum, 1, lang), t=num(total, 1, lang), f=terms), ""]
    else:
        out += [t["none_steps"], ""]
    out += [t["auto_note"], ""]
    if with_methods:
        rules = method_claim_lines(methods_state(led), claims, lang)
        if rules:
            out += rules + [""]
    out += [claims["demo"][lang], "", "---", t["footer"].format(v=VERSION), ""]
    return "\n".join(out)


# ---------------------------------------------------------------- command line

def utf8_output():
    """Print UTF-8 whatever the console's code page (Windows cp1252, LANG=C): the output holds €, ×, ÷ and é."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    utf8_output()
    ap = argparse.ArgumentParser(prog="hours.py", description="Twikey Payment Hours calculator")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--lang", choices=LANGS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("pairs", nargs="+", metavar="KEY=VALUE")
    u = sub.add_parser("unset")
    u.add_argument("keys", nargs="+")
    sub.add_parser("show")
    sub.add_parser("process")
    sub.add_parser("methods")
    r = sub.add_parser("report")
    r.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        led = load(args.ledger)
        lang = args.lang or led["company"].get("lang", "en")
        if args.cmd == "set":
            for pair in args.pairs:
                if "=" not in pair:
                    raise UserError("expected KEY=VALUE, got %r" % pair)
                k, v = pair.split("=", 1)
                set_value(led, k.strip(), v)
            save(args.ledger, led)
            print("saved %d answer(s) to %s" % (len(args.pairs), args.ledger))
        elif args.cmd == "unset":
            for k in args.keys:
                unset_value(led, k.strip())
            save(args.ledger, led)
            print("removed %s from %s" % (", ".join(args.keys), args.ledger))
        elif args.cmd == "show":
            print(json.dumps(led, indent=2, ensure_ascii=False, sort_keys=True))
        elif args.cmd == "process":
            print(cmd_process(led, lang))
        elif args.cmd == "methods":
            print(cmd_methods(led, lang))
        elif args.cmd == "report":
            text = cmd_report(led, lang)
            if args.out:
                with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                print("report written to %s" % args.out)
            else:
                print(text)
    except UserError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    except OSError as e:
        print("error: cannot read or write a file: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
