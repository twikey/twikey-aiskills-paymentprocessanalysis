"""The text lines twikey_xray.py prints, in English, Dutch and French. Dutch says "je" and "domiciliëring",
French says "vous". Numbers, dates and amounts are filled in by the caller in the same language."""

# Intake prints what the statement reader says about a statement (its description and why entries were skipped).
# It says it in English. These patterns put it in Dutch and French, in this order.
INTAKE_PHRASES = {
    "nl": [
        (r"debit \(payment out\)", "debet (uitgaande betaling)"), (r"entry not booked", "niet-geboekte boeking"),
        (r"transaction without amount or direction", "verrichting zonder bedrag of richting"),
        (r"direct debit batch without details", "domiciliëringsbatch zonder details"),
        (r"returned payment that is not a collection of yours", "teruggestorte betaling die geen domiciliëring van "
                                                                "jou is"),
        (r"\bfile (\d+)\b", r"bestand \1"), (r"\b1 entry\b", "1 boeking"), (r"\b(\d+) entries\b", r"\1 boekingen"),
    ],
    "fr": [
        (r"debit \(payment out\)", "débit (paiement sortant)"), (r"entry not booked", "écriture non comptabilisée"),
        (r"transaction without amount or direction", "opération sans montant ni sens"),
        (r"direct debit batch without details", "lot de prélèvements sans détail"),
        (r"returned payment that is not a collection of yours", "paiement retourné qui n'est pas un de vos "
                                                                "prélèvements"),
        (r"\bfile (\d+)\b", r"fichier \1"), (r"\b1 entry\b", "1 écriture"), (r"\b(\d+) entries\b", r"\1 écritures"),
    ],
}

NOUNS = {
    "en": {"statement": ("statement", "statements"), "record": ("record", "records"),
           "customer": ("customer", "customers"), "payer": ("payer", "payers"), "code": ("code", "codes"),
           "mandate": ("mandate", "mandates"), "payment": ("payment", "payments"),
           "transfer": ("transfer", "transfers"), "copy": ("copy", "copies"), "month": ("month", "months")},
    "nl": {"statement": ("afschrift", "afschriften"), "record": ("item", "items"),
           "customer": ("klant", "klanten"), "payer": ("betaler", "betalers"), "code": ("code", "codes"),
           "mandate": ("mandaat", "mandaten"), "payment": ("betaling", "betalingen"),
           "transfer": ("overschrijving", "overschrijvingen"), "copy": ("kopie", "kopieën"),
           "month": ("maand", "maanden")},
    "fr": {"statement": ("relevé", "relevés"), "record": ("enregistrement", "enregistrements"),
           "customer": ("client", "clients"), "payer": ("payeur", "payeurs"), "code": ("code", "codes"),
           "mandate": ("mandat", "mandats"), "payment": ("paiement", "paiements"),
           "transfer": ("virement", "virements"), "copy": ("copie", "copies"), "month": ("mois", "mois")},
}

TEXT = {
    "en": {
        "none": "none", "and_more": " and %s more", "yes": "yes", "no": "no",
        "init": "Workspace: {workspace}\nRaw folder: {raw}\nThe X-ray guard now keeps Claude's file and shell tools "
                "out of the raw folder.\nNext: put your camt.053 bank statements in the raw folder and run intake.",
        "demo": "Demo: camt.053 bank statements of a fictional Belgian wholesaler ({start} to {end}) copied to "
                "{raw}. As-of date {as_of}.",
        # intake
        "intake": "Intake: {files} read from the raw folder.",
        "kept": "  {desc}: {n} kept", "kept_one": "  {desc}: {n} kept",
        "skipped": "      skipped: {n} ({why})",
        "skip_not_camt053": "  {file} is not a camt.053 bank statement, skipped.",
        "skip_doctype": "  {file} declares a DOCTYPE or ENTITY and is not read, skipped.",
        "skip_too_large": "  {file} is larger than 200 MB, skipped.",
        "skip_unreadable": "  {file} could not be opened (check that it is not open in another program and that "
                           "you may read it), skipped.",
        "ledger": "Ledger: {customers} paying by direct debit and {payers} paying by transfer ({codes}), {mandates}.",
        "bank_in": "Incoming payments: {n}{span}", "coll_in": "Direct debit collections: {n}{span}",
        "failed_in": "Failed collections: {n}{span}", "span": " ({start} to {end})",
        "not_in_ledger": "Not in the ledger: {out} out, {own} between your own accounts, {dups} of the same "
                         "transaction in two files.",
        "bad_ogm": "Structured communications with wrong check digits: {n} (kept without it).",
        "other_refs": "Other references (not checked): {n}.",
        "coded": "Names, IBANs, mandate references, payment references and file names are codes now. The key that "
                 "turns them back is in your raw folder.",
        # decode
        "dec_total": "Failed collections: {n}, {amount} ({start} to {end}, {months}).",
        "dec_none": "Failed collections: none in your bank statements.",
        "by_code": "By reason code:", "no_code": "no reason code on the statement",
        "epc": "not on Twikey's reason-code page. EPC rulebook reason: {meaning}",
        "points_to": "What the codes point to:",
        "cat": {"new_attempt": "new attempt", "new_mandate": "new mandate", "conversation": "conversation",
                "own_setup": "own setup", "bank": "bank", "unknown": "unknown", "unreadable": "unreadable"},
        "rate_head": "Failure rate by usual collection day of the month (collection date, {start} to {end}, days "
                     "with at least two months of data, retries left out, runs moved by a weekend or bank holiday "
                     "counted under their usual day):",
        "rate_line": "  day {day} {rate}  ({failed} failed of {presented} presented, {months}){few}",
        "few": ", fewer than 20 collections, too few to compare",
        "rate_all": "  all days: {rate} ({failed} failed of {presented} presented)",
        "booked": "Returns without a known collection date, by booking day: {list}",
        "repeat": "Customers with two or more failures: {list}",
        "not_on_page": "Codes not on Twikey's reason-code page: {list}",
        "epc_short": "{code} (EPC rulebook reason: {meaning})",
        # payments
        "pay_head": "Incoming payments: {n}, {amount} ({start} to {end}, {months}).",
        "pay_none": "Incoming payments: none in your bank statements.",
        "pay_groups": {"valid": "With a valid structured communication",
                       "invalid": "Structured communication with wrong check digits",
                       "other": "Another reference (not checked)", "absent": "No structured communication"},
        "pay_line": "  {label}: {n}, {amount}{codes}",
        "by_hand": "To book by hand: {n} of {total} ({share}), {amount}, {per_month} a month.",
        "by_hand_most": "Most often from: {list}",
        "method": "Method: {method}",
        # golive
        "golive_head": "Facts for the go-live plan:",
        "gl_dd": "  Customers paying by direct debit: {n} ({core} Core, {b2b} B2B), {mandates}",
        "gl_collections": "  Collections a month: {n}, failed a month: {failed} ({rate} of all collections)",
        "gl_transfers": "  Payers by transfer: {n}, {transfers} incoming payments a month, {by_hand} of them to book "
                        "by hand",
        "gl_tool_yes": "  Accounting tool {tool}: Listed on Twikey's partners page ({names}): {page}",
        "gl_tool_no": "  Accounting tool {tool}: not listed on Twikey's partners page, ask Twikey",
        "gl_questions": "Questions for the user: {list}.",
        "gl_existing": "Existing mandates: {text}",
        "gl_lines": "Twikey lines for the plan:",
        "gl_pricing": "Packages and pricing: {page}",
        "gl_cta": "Call to action (the report ends with it): {text}",
        # status
        "st_title": "Twikey Payment X-ray {version}", "st_stop": "Stop: {problem}",
        "st_ws": "Workspace: {ws}{extra}", "st_not_set_up": " (not set up yet)",
        "st_raw": "Raw folder: {raw}{extra}", "st_not_set": "not set", "st_demo": " (demo data)",
        "st_as_of": "As-of date: {date}", "st_today": "today",
        "st_ledger": "Ledger (intake {date}): {statements}, {customers} paying by direct debit, {payers} paying by "
                     "transfer.",
        "st_no_ledger": "Ledger: no intake yet",
        "st_files": "findings.md: {findings}, go-live-plan.md: {plan}",
        "st_reports": "Reports in the raw folder: {n}{latest}", "st_latest": " (latest {name})",
    },
    "nl": {
        "none": "geen", "and_more": " en nog %s", "yes": "ja", "no": "nee",
        "init": "Werkmap: {workspace}\nExportmap: {raw}\nDe X-ray-bewaking houdt de bestands- en shelltools van "
                "Claude nu uit de exportmap.\nVolgende stap: zet je camt.053-bankafschriften in de exportmap en voer "
                "intake uit.",
        "demo": "Demo: camt.053-bankafschriften van een fictieve Belgische groothandel ({start} tot {end}) "
                "gekopieerd naar {raw}. Stand op {as_of}.",
        "intake": "Intake: {files} gelezen uit de exportmap.",
        "kept": "  {desc}: {n} bewaard", "kept_one": "  {desc}: {n} bewaard",
        "skipped": "      overgeslagen: {n} ({why})",
        "skip_not_camt053": "  {file} is geen camt.053-bankafschrift, overgeslagen.",
        "skip_doctype": "  {file} declareert een DOCTYPE of ENTITY en wordt niet gelezen, overgeslagen.",
        "skip_too_large": "  {file} is groter dan 200 MB, overgeslagen.",
        "skip_unreadable": "  {file} kon niet geopend worden (kijk na of het niet open staat in een ander programma "
                           "en of je het mag lezen), overgeslagen.",
        "ledger": "Grootboek: {customers} die via domiciliëring betalen en {payers} die per overschrijving betalen "
                  "({codes}), {mandates}.",
        "bank_in": "Inkomende betalingen: {n}{span}", "coll_in": "Domiciliëringen: {n}{span}",
        "failed_in": "Mislukte domiciliëringen: {n}{span}", "span": " ({start} tot {end})",
        "not_in_ledger": "Niet in het grootboek: {out} uitgaand, {own} tussen je eigen rekeningen, {dups} van "
                         "dezelfde verrichting in twee bestanden.",
        "bad_ogm": "Gestructureerde mededelingen met foute controlecijfers: {n} (bewaard zonder mededeling).",
        "other_refs": "Andere referenties (niet nagekeken): {n}.",
        "coded": "Namen, IBAN's, mandaatreferenties, betaalreferenties en bestandsnamen zijn nu codes. De sleutel "
                 "om ze terug te zetten staat in je exportmap.",
        "dec_total": "Mislukte domiciliëringen: {n}, {amount} ({start} tot {end}, {months}).",
        "dec_none": "Mislukte domiciliëringen: geen in je bankafschriften.",
        "by_code": "Per redencode:", "no_code": "geen redencode op het afschrift",
        "epc": "niet op de redencodepagina van Twikey. Reden volgens het EPC-rulebook (Engels): {meaning}",
        "points_to": "Waar de codes op wijzen:",
        "cat": {"new_attempt": "heraanbieden", "new_mandate": "nieuw mandaat", "conversation": "gesprek",
                "own_setup": "eigen instellingen", "bank": "bank", "unknown": "onbekend", "unreadable": "onleesbaar"},
        "rate_head": "Percentage mislukt per gewone domiciliëringsdag van de maand (domiciliëringsdatum, {start} tot "
                     "{end}, dagen met minstens twee maanden gegevens, heraanbiedingen niet meegeteld, reeksen die "
                     "door een weekend of feestdag verschoven zijn op hun gewone dag):",
        "rate_line": "  dag {day} {rate}  ({failed} mislukt van {presented} aangeboden, {months}){few}",
        "few": ", minder dan 20 domiciliëringen, te weinig om te vergelijken",
        "rate_all": "  alle dagen: {rate} ({failed} mislukt van {presented} aangeboden)",
        "booked": "Terugboekingen zonder bekende domiciliëringsdatum, per boekingsdag: {list}",
        "repeat": "Klanten met twee of meer mislukkingen: {list}",
        "not_on_page": "Codes die niet op de redencodepagina van Twikey staan: {list}",
        "epc_short": "{code} (reden volgens het EPC-rulebook, in het Engels: {meaning})",
        "pay_head": "Inkomende betalingen: {n}, {amount} ({start} tot {end}, {months}).",
        "pay_none": "Inkomende betalingen: geen in je bankafschriften.",
        "pay_groups": {"valid": "Met een geldige gestructureerde mededeling",
                       "invalid": "Gestructureerde mededeling met foute controlecijfers",
                       "other": "Een andere referentie (niet nagekeken)", "absent": "Geen gestructureerde mededeling"},
        "pay_line": "  {label}: {n}, {amount}{codes}",
        "by_hand": "Met de hand te boeken: {n} van {total} ({share}), {amount}, {per_month} per maand.",
        "by_hand_most": "Het vaakst van: {list}",
        "method": "Methode: {method}",
        "golive_head": "Feiten voor het opstartplan:",
        "gl_dd": "  Klanten die via domiciliëring betalen: {n} ({core} Core, {b2b} B2B), {mandates}",
        "gl_collections": "  Domiciliëringen per maand: {n}, mislukt per maand: {failed} ({rate} van alle "
                          "domiciliëringen)",
        "gl_transfers": "  Betalers per overschrijving: {n}, {transfers} inkomende betalingen per maand, waarvan "
                        "{by_hand} met de hand te boeken",
        "gl_tool_yes": "  Boekhoudpakket {tool}: Staat op de partnerpagina van Twikey ({names}): {page}",
        "gl_tool_no": "  Boekhoudpakket {tool}: staat niet op de partnerpagina van Twikey, vraag het aan Twikey",
        "gl_questions": "Vragen voor de gebruiker: {list}.",
        "gl_existing": "Bestaande mandaten: {text}",
        "gl_lines": "Twikey-regels voor het plan:",
        "gl_pricing": "Pakketten en prijzen: {page}",
        "gl_cta": "Oproep tot actie (het rapport eindigt ermee): {text}",
        "st_title": "Twikey Payment X-ray {version}", "st_stop": "Stop: {problem}",
        "st_ws": "Werkmap: {ws}{extra}", "st_not_set_up": " (nog niet ingesteld)",
        "st_raw": "Exportmap: {raw}{extra}", "st_not_set": "niet ingesteld", "st_demo": " (demogegevens)",
        "st_as_of": "Stand op: {date}", "st_today": "vandaag",
        "st_ledger": "Grootboek (intake {date}): {statements}, {customers} via domiciliëring, {payers} per "
                     "overschrijving.",
        "st_no_ledger": "Grootboek: nog geen intake",
        "st_files": "findings.md: {findings}, go-live-plan.md: {plan}",
        "st_reports": "Rapporten in de exportmap: {n}{latest}", "st_latest": " (laatste {name})",
    },
    "fr": {
        "none": "0", "and_more": " et %s autres", "yes": "oui", "no": "non",
        "init": "Espace de travail : {workspace}\nDossier des exports : {raw}\nLa protection X-ray tient désormais "
                "les outils de fichiers et de shell de Claude à l'écart du dossier des exports.\nÉtape suivante : "
                "placez vos relevés bancaires camt.053 dans le dossier et lancez intake.",
        "demo": "Démo : relevés bancaires camt.053 d'un grossiste belge fictif ({start} à {end}) copiés dans {raw}. "
                "Situation au {as_of}.",
        "intake": "Intake : {files} lus dans le dossier des exports.",
        "kept": "  {desc} : {n} conservés", "kept_one": "  {desc} : {n} conservé",
        "skipped": "      ignorés : {n} ({why})",
        "skip_not_camt053": "  {file} n'est pas un relevé bancaire camt.053, ignoré.",
        "skip_doctype": "  {file} déclare un DOCTYPE ou une ENTITY et n'est pas lu, ignoré.",
        "skip_too_large": "  {file} dépasse 200 Mo, ignoré.",
        "skip_unreadable": "  {file} est impossible à ouvrir (vérifiez qu'il n'est pas ouvert dans un autre "
                           "programme et que vous pouvez le lire), ignoré.",
        "ledger": "Registre : {customers} qui paient par prélèvement et {payers} qui paient par virement ({codes}), "
                  "{mandates}.",
        "bank_in": "Paiements entrants : {n}{span}", "coll_in": "Prélèvements : {n}{span}",
        "failed_in": "Prélèvements échoués : {n}{span}", "span": " ({start} à {end})",
        "not_in_ledger": "Hors registre : {out} sortants, {own} entre vos propres comptes, {dups} de la même "
                         "opération dans deux fichiers.",
        "bad_ogm": "Communications structurées avec des chiffres de contrôle erronés : {n} (conservées sans "
                   "communication).",
        "other_refs": "Autres références (non vérifiées) : {n}.",
        "coded": "Les noms, IBAN, références de mandat, références de paiement et noms de fichier sont désormais des "
                 "codes. La clé qui permet de les retrouver se trouve dans votre dossier des exports.",
        "dec_total": "Prélèvements échoués : {n}, {amount} ({start} à {end}, {months}).",
        "dec_none": "Prélèvements échoués : aucun dans vos relevés bancaires.",
        "by_code": "Par code motif :", "no_code": "pas de code motif sur le relevé",
        "epc": "absent de la page des codes motif de Twikey. Motif selon le rulebook de l'EPC (anglais) : {meaning}",
        "points_to": "Ce qu'indiquent les codes :",
        "cat": {"new_attempt": "nouvelle présentation", "new_mandate": "nouveau mandat", "conversation": "échange",
                "own_setup": "propre paramétrage", "bank": "banque", "unknown": "inconnu", "unreadable": "illisible"},
        "rate_head": "Taux d'échec par jour de prélèvement habituel du mois (date de prélèvement, {start} à {end}, "
                     "jours avec au moins deux mois de données, nouvelles présentations non comptées, séries "
                     "décalées par un week-end ou un jour férié comptées pour leur jour habituel) :",
        "rate_line": "  jour {day} {rate}  ({failed} en échec sur {presented} présentés, {months}){few}",
        "few": ", moins de 20 prélèvements, trop peu pour comparer",
        "rate_all": "  tous les jours : {rate} ({failed} en échec sur {presented} présentés)",
        "booked": "Retours sans date de prélèvement connue, par jour de comptabilisation : {list}",
        "repeat": "Clients avec deux échecs ou plus : {list}",
        "not_on_page": "Codes absents de la page des codes motif de Twikey : {list}",
        "epc_short": "{code} (motif selon le rulebook de l'EPC, en anglais : {meaning})",
        "pay_head": "Paiements entrants : {n}, {amount} ({start} à {end}, {months}).",
        "pay_none": "Paiements entrants : aucun dans vos relevés bancaires.",
        "pay_groups": {"valid": "Avec une communication structurée valable",
                       "invalid": "Communication structurée aux chiffres de contrôle erronés",
                       "other": "Une autre référence (non vérifiée)", "absent": "Sans communication structurée"},
        "pay_line": "  {label} : {n}, {amount}{codes}",
        "by_hand": "À comptabiliser à la main : {n} sur {total} ({share}), {amount}, {per_month} par mois.",
        "by_hand_most": "Le plus souvent de : {list}",
        "method": "Méthode : {method}",
        "golive_head": "Faits pour le plan de démarrage :",
        "gl_dd": "  Clients qui paient par prélèvement : {n} ({core} Core, {b2b} B2B), {mandates}",
        "gl_collections": "  Prélèvements par mois : {n}, échoués par mois : {failed} ({rate} de l'ensemble des "
                          "prélèvements)",
        "gl_transfers": "  Payeurs par virement : {n}, {transfers} paiements entrants par mois, dont {by_hand} à "
                        "comptabiliser à la main",
        "gl_tool_yes": "  Logiciel comptable {tool} : Figure sur la page partenaires de Twikey ({names}) : {page}",
        "gl_tool_no": "  Logiciel comptable {tool} : ne figure pas sur la page partenaires de Twikey, demandez à "
                      "Twikey",
        "gl_questions": "Questions pour l'utilisateur : {list}.",
        "gl_existing": "Mandats existants : {text}",
        "gl_lines": "Lignes Twikey pour le plan :",
        "gl_pricing": "Formules et prix : {page}",
        "gl_cta": "Appel à l'action (le rapport se termine par celui-ci) : {text}",
        "st_title": "Twikey Payment X-ray {version}", "st_stop": "Arrêt : {problem}",
        "st_ws": "Espace de travail : {ws}{extra}", "st_not_set_up": " (pas encore configuré)",
        "st_raw": "Dossier des exports : {raw}{extra}", "st_not_set": "non défini", "st_demo": " (données de démo)",
        "st_as_of": "Situation au : {date}", "st_today": "aujourd'hui",
        "st_ledger": "Registre (intake du {date}) : {statements}, {customers} par prélèvement, {payers} par virement.",
        "st_no_ledger": "Registre : pas encore d'intake",
        "st_files": "findings.md : {findings}, go-live-plan.md : {plan}",
        "st_reports": "Rapports dans le dossier des exports : {n}{latest}", "st_latest": " (le dernier : {name})",
    },
}
