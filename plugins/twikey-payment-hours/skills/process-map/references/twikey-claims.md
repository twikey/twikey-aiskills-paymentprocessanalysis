# Twikey lines the skills may use

This file is the only source for anything Twikey Payment Hours says about Twikey. The calculator
`scripts/hours.py` reads the lines below by ID and prints them word for word, each with its page on
twikey.com. Claude quotes them as they are and adds no other claim about Twikey.

- `steps`: the steps of getting paid the line speaks to. Only a line that says the work is automated (or done
  by Twikey) carries `steps`. A step with such a line counts as a step a Twikey page says it automates. A step
  with no line does not.
- `methods`: the payment methods the line is a rule or trade-off for (method-compare).
- Dutch and French lines are quoted word for word from the Belgian Dutch (www.twikey.com/be/) and French
  (www.twikey.com/fr/) pages. Where the Dutch page addresses the reader with "u", or has no Dutch page, the
  Dutch line is a translation of the English quote in the "je" form, marked `nl-kind: translation (nl) of
  <English page>`, and prints as a translation. A line with no French page prints in English, marked
  "(anglais)".
- `package`: the row of the pricing page that names the feature, with its package. Never a price.

Checked on www.twikey.com on November 4, 2026.

## Lines

### auto-collect
- steps: collect
- en: “Recurring payments provide your company with predictable cash flow as payments are automatically collected at regular intervals.”
- nl: “Terugkerende betalingen geven je bedrijf een voorspelbare cashflow, omdat betalingen automatisch geïnd worden op regelmatige tijdstippen.”
- nl-kind: translation (nl) of https://www.twikey.com/product/all-recurring-payment-methods.html
- fr: « les paiements récurrents fournissent à votre entreprise des flux de trésorerie prévisibles, car les paiements sont automatiquement collectés à intervalles réguliers. »
- source: https://www.twikey.com/product/all-recurring-payment-methods.html
- source-fr: https://www.twikey.com/fr/product/tous-les-modes-de-paiement-recurrents.html

### reconciliation
- steps: match
- en: “In addition, you no longer need to perform reconciliation by hand, either, because Twikey does that for you.”
- nl: “Bovendien hoef je afstemming niet meer handmatig te doen, want Twikey doet dit automatisch.”
- fr: « De plus, vous n’avez plus besoin d’effectuer le rapprochement manuellement, Twikey le fait pour vous. »
- source: https://www.twikey.com/
- source-nl: https://www.twikey.com/be/
- source-fr: https://www.twikey.com/fr/

### reminders
- steps: chase
- en: “For non-payment, we can send reminders or forward the invoice to debt management or collection.”
- nl: “Bij niet-betaling kunnen we herinneringen sturen of de factuur doorsturen naar debiteurenbeheer of incasso.”
- fr: « En cas de non-paiement, nous pouvons envoyer des rappels ou transmettre la facture au service de gestion des dettes ou de recouvrement. »
- source: https://www.twikey.com/product/getting-invoices-paid-online.html
- source-nl: https://www.twikey.com/be/product/betaalpagina-facturen.html
- source-fr: https://www.twikey.com/fr/product/encaissement-de-factures.html
- package: “Invoice paypage”: Professional
- package-nl: “Factuurbetalingspagina”: Professional
- package-fr: « Page de paiement par facture » : Professional

### failed-auto
- steps: failed
- en: “If a payment fails, it can automatically recognize a particular error code and act accordingly.”
- nl: “Als een betaling mislukt, kan het automatisch een specifieke foutcode herkennen en daarop handelen.”
- fr: « Si un paiement échoue, il peut reconnaître automatiquement un code d’erreur particulier et agir en conséquence. »
- source: https://www.twikey.com/
- source-nl: https://www.twikey.com/be/
- source-fr: https://www.twikey.com/fr/
- package: “Transaction failure management”: Professional. “Advanced failure management”: Premium
- package-nl: “Beheer van mislukte transacties”: Professional. “Geavanceerd beheer van mislukte transacties”: Premium
- package-fr: « Gestion des échecs de transaction » : Professional. « Gestion avancée des échecs » : Premium

### orchestration
- methods: all
- en: “Payment orchestration with 3,500 banks, all major PSPs and payment methods”
- nl: “Betalingsorkestratie met 3.500 banken, alle grote PSP’s en betaalmethoden”
- fr: « Orchestration des paiements avec 3 500 banques, tous les principaux PSP et méthodes de paiement »
- source: https://www.twikey.com/
- source-nl: https://www.twikey.com/be/
- source-fr: https://www.twikey.com/fr/

### collect-when-due
- methods: sdd_core
- en: “Once authorized, you can collect payments from your customer’s account whenever they’re due.”
- nl: “Na autorisatie kun je betalingen van de rekening van je klant innen op het moment dat ze verschuldigd zijn.”
- nl-kind: translation (nl) of https://www.twikey.com/product/detail/core-direct-debit.html
- fr: « Une fois le prélèvement automatique autorisé, vous pouvez prélever les paiements sur le compte de votre client à chaque échéance. »
- source: https://www.twikey.com/product/detail/core-direct-debit.html
- source-fr: https://www.twikey.com/fr/product/detail/prelevement-sepa-core.html
- package: “Create & manage SEPA Core mandates”: Lite
- package-nl: “SEPA Core-mandaten aanmaken & beheren”: Lite
- package-fr: « Créer et gérer des mandats SEPA Core » : Lite

### tokenization
- methods: card_recurring
- en: “Tokenization for recurring credit and debit card”
- nl: “Tokenisatie voor terugkerende credit- en debetkaarten”
- fr: « Tokenisation pour cartes de crédit et de débit récurrentes »
- source: https://www.twikey.com/
- source-nl: https://www.twikey.com/be/
- source-fr: https://www.twikey.com/fr/
- package: “Recurring credit cards & PayPal”: Professional
- package-nl: “Terugkerende kredietkaarten & PayPal”: Professional
- package-fr: « Cartes de crédit récurrentes & PayPal » : Professional

### core-refund
- methods: sdd_core
- en: “A CORE mandate on the other hand doesn't need this registration but allows the customer to request a refund within 8 weeks.”
- nl: “Een CORE-mandaat daarentegen heeft deze registratie niet nodig, maar laat de klant toe om binnen 8 weken een terugbetaling aan te vragen.”
- fr: « Un mandat CORE en revanche ne nécessite pas cet enregistrement mais permet au client de demander un remboursement dans les 8 semaines. »
- source: https://www.twikey.com/start/index.html
- source-nl: https://www.twikey.com/be/start/
- source-fr: https://www.twikey.com/fr/start/

### b2b-registered
- methods: sdd_b2b
- en: “B2B mandates don't have a refund right, but have to be registered at the bank of your end-customer”
- nl: “B2B-mandaten hebben geen recht op terugbetaling, maar moeten worden geregistreerd bij de bank van je eindklant”
- nl-kind: translation (nl) of https://www.twikey.com/start/index.html
- fr: « Les mandats B2B n'ont pas de droit de remboursement, mais doivent être enregistrés auprès de la banque de votre client final »
- source: https://www.twikey.com/start/index.html
- source-fr: https://www.twikey.com/fr/start/

### core-b2b
- methods: sdd_core, sdd_b2b
- en: “B2B used exclusively between businesses, while CORE can be used for both consumers and businesses.”
- nl: “B2B wordt uitsluitend gebruikt tussen bedrijven, terwijl CORE kan worden gebruikt voor zowel consumenten als bedrijven.”
- fr: « B2B utilisé exclusivement entre entreprises, tandis que CORE peut être utilisé pour les consommateurs et les entreprises. »
- source: https://www.twikey.com/start/index.html
- source-nl: https://www.twikey.com/be/start/
- source-fr: https://www.twikey.com/fr/start/

### card-chargebacks
- methods: card, card_recurring
- en: “With a SEPA B2B mandate, the debtor cannot reverse an authorized collection afterwards. Compare that to the 8-week no-questions refund right on SEPA Core, or card chargebacks that can come in up to 120 days later.”
- nl: “Met een SEPA B2B-mandaat kan de debiteur een toegestane domiciliëring achteraf niet terugdraaien. Vergelijk dat met het onvoorwaardelijke terugbetalingsrecht van 8 weken bij SEPA Core, of met kaart-chargebacks die tot 120 dagen later kunnen binnenkomen.”
- nl-kind: translation (nl) of https://www.twikey.com/blog/sepa-direct-debit-tips-and-tricks/sepa-direct-debits-vs-recurring-credit-cards.html
- source: https://www.twikey.com/blog/sepa-direct-debit-tips-and-tricks/sepa-direct-debits-vs-recurring-credit-cards.html

### card-expiry
- methods: card_recurring
- en: “No expired or replaced cards to chase, no credit-limit declines.”
- nl: “Geen verlopen of vervangen kaarten die je moet opvolgen, geen weigeringen door een kredietlimiet.”
- nl-kind: translation (nl) of https://www.twikey.com/blog/sepa-direct-debit-tips-and-tricks/sepa-direct-debits-vs-recurring-credit-cards.html
- source: https://www.twikey.com/blog/sepa-direct-debit-tips-and-tricks/sepa-direct-debits-vs-recurring-credit-cards.html

### own-account
- en: “Leverage direct debits and recurring card payments via your own bank or preferred payment provider.”
- nl: “Maak gebruik van domiciliëringen en terugkerende kredietkaartbetalingen via je eigen bank of betaalprovider.”
- fr: « Exploitez les prélèvements automatiques et les cartes de crédit récurrentes par l'intermédiaire de votre propre banque ou de votre Prestataire de Service de Paiement (PSP) préféré. »
- source: https://www.twikey.com/
- source-nl: https://www.twikey.com/be/
- source-fr: https://www.twikey.com/fr/

### demo
- en: Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-payment-hours&utm_medium=claude-skills&utm_campaign=payment-hours
- nl: Vraag Twikey een demo: https://www.twikey.com/be/demo.html?utm_source=twikey-payment-hours&utm_medium=claude-skills&utm_campaign=payment-hours
- fr: Demandez une démo à Twikey : https://www.twikey.com/fr/demo.html?utm_source=twikey-payment-hours&utm_medium=claude-skills&utm_campaign=payment-hours
- source: https://www.twikey.com/demo.html
- source-nl: https://www.twikey.com/be/demo.html
- source-fr: https://www.twikey.com/fr/demo.html

## Pricing page

- en: https://www.twikey.com/pricing.html
- nl: https://www.twikey.com/be/pricing.html
- fr: https://www.twikey.com/fr/pricing.html
