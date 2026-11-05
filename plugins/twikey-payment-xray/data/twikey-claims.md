# Twikey lines the plugin may print

This file is the only source for anything Twikey Payment X-ray says about Twikey. The script
`twikey_xray.py` reads the lines below by ID and prints them word for word, each with its page on
twikey.com. Where the pricing page ties a feature to a package, the line names the package as the
pricing page row says. The pricing page itself is linked once, in the go-live facts.

Dutch and French lines are quoted word for word from the Belgian Dutch (www.twikey.com/be/) and the
French (www.twikey.com/fr/) pages. A Dutch quote is used only when it addresses the reader with "je"
or not at all. Where the Dutch page addresses the reader with "u", the Dutch line is Twikey's
translation of the English quote, marked `nl-kind: translation (nl) of <English page>`, and links
that English page. A line with neither is printed in English, marked "(Engels)" in Dutch and
"(anglais)" in French.

Checked on www.twikey.com on November 3, 2026.

## Lines

### failure-decoder
- en: “This allows us to take immediate action, including customer notifications, reattempting collections for insufficient funds, initiating payments through alternative methods, or seeking renewed consent for expired cards or mandates.”
- nl: “Dit stelt ons in staat om meteen actie te ondernemen zoals: meldingen uitsturen, opnieuw incasseren bij onvoldoende saldo, betalingen initiëren via alternatieve methoden, vernieuwde toestemming vragen voor verlopen kaarten of mandaten”
- fr: « Cela nous permet d’intervenir directement, notamment en informant les clients, en tentant à nouveau de recouvrer les créances impayées, en initiant des paiements par des méthodes alternatives ou en demandant un renouvellement du consentement pour les cartes et les mandats expirés. »
- source: https://www.twikey.com/product/follow-up-payments.html
- source-nl: https://www.twikey.com/be/product/opvolging-betalingen.html
- source-fr: https://www.twikey.com/fr/product/suivi-des-paiements.html
- package: “Transaction failure management”: Professional. “Advanced failure management”: Premium
- package-nl: “Beheer van mislukte transacties”: Professional. “Geavanceerd beheer van mislukte transacties”: Premium
- package-fr: « Gestion des échecs de transaction » : Professional. « Gestion avancée des échecs » : Premium

### mandate-health
- en: “seeking renewed consent for expired cards or mandates”
- nl: “vernieuwde toestemming vragen voor verlopen kaarten of mandaten”
- fr: « en demandant un renouvellement du consentement pour les cartes et les mandats expirés »
- source: https://www.twikey.com/product/follow-up-payments.html
- source-nl: https://www.twikey.com/be/product/opvolging-betalingen.html
- source-fr: https://www.twikey.com/fr/product/suivi-des-paiements.html
- package: “Transaction failure management”: Professional. “Advanced failure management”: Premium
- package-nl: “Beheer van mislukte transacties”: Professional. “Geavanceerd beheer van mislukte transacties”: Premium
- package-fr: « Gestion des échecs de transaction » : Professional. « Gestion avancée des échecs » : Premium

### unmatched-payments
- en: “Our dashboards and APIs offer you real-time updates on the status of incoming payments, regardless of your chosen payment method.”
- nl: “Onze dashboards en API's bieden je realtime updates over de status van binnenkomende betalingen, ongeacht de betalingsmethode die je gekozen hebt.”
- nl-kind: translation (nl) of https://www.twikey.com/product/reconciliation.html
- fr: « Nos tableaux de bord et API vous offrent des mises à jour en temps réel sur l'état des paiements entrants, quel que soit le mode de paiement choisi. »
- source: https://www.twikey.com/product/reconciliation.html
- source-fr: https://www.twikey.com/fr/product/reconciliation.html

### terms-vs-reality
- en: “Once authorized, you can collect payments from your customer’s account whenever they’re due.”
- nl: “Na autorisatie kun je betalingen van de rekening van je klant innen op het moment dat ze verschuldigd zijn.”
- nl-kind: translation (nl) of https://www.twikey.com/product/detail/core-direct-debit.html
- fr: « Une fois le prélèvement automatique autorisé, vous pouvez prélever les paiements sur le compte de votre client à chaque échéance. »
- source: https://www.twikey.com/product/detail/core-direct-debit.html
- source-fr: https://www.twikey.com/fr/product/detail/prelevement-sepa-core.html
- package: “Create & manage SEPA Core mandates”: Lite
- package-nl: “SEPA Core-mandaten aanmaken & beheren”: Lite
- package-fr: « Créer et gérer des mandats SEPA Core » : Lite

### payer-profiles
- en: “Experience the ease of recurring payments with our conversion campaign, designed to guide clients to your preferred recurring payment method.”
- nl: “Ontdek het gemak van terugkerende betalingen met onze conversiecampagne, ontworpen om klanten naar de terugkerende betaalmethode van je voorkeur te leiden.”
- nl-kind: translation (nl) of https://www.twikey.com/product/conversion-campaign.html
- fr: « Découvrez la facilité des paiements récurrents grâce à notre campagne de conversion, conçue pour guider vos clients vers votre mode de paiement récurrent préféré. »
- source: https://www.twikey.com/product/conversion-campaign.html
- source-fr: https://www.twikey.com/fr/product/campagne-de-conversion.html

### about
- en: 10+ years of experience. 10M+ active mandates.
- nl: 10+ jaar ervaring. 10M+ actieve mandaten.
- fr: 10+ ans d'expérience. 10M+ mandats actifs.
- source: https://www.twikey.com/about.html
- source-nl: https://www.twikey.com/be/about.html
- source-fr: https://www.twikey.com/fr/about.html

### core-b2b
- en: “B2B used exclusively between businesses, while CORE can be used for both consumers and businesses.”
- nl: “B2B wordt uitsluitend gebruikt tussen bedrijven, terwijl CORE kan worden gebruikt voor zowel consumenten als bedrijven.”
- fr: « B2B utilisé exclusivement entre entreprises, tandis que CORE peut être utilisé pour les consommateurs et les entreprises. »
- source: https://www.twikey.com/start/index.html
- source-nl: https://www.twikey.com/be/start/
- source-fr: https://www.twikey.com/fr/start/
- package: “Create & manage SEPA B2B mandates (other)”: Professional
- package-nl: “SEPA B2B-mandaten aanmaken & beheren (overige)”: Professional
- package-fr: « Créer et gérer des mandats SEPA B2B (autres) » : Professional

### b2b-registered
- en: “B2B mandates don't have a refund right, but have to be registered at the bank of your end-customer”
- nl: “B2B-mandaten hebben geen recht op terugbetaling, maar moeten worden geregistreerd bij de bank van je eindklant”
- nl-kind: translation (nl) of https://www.twikey.com/start/index.html
- fr: « Les mandats B2B n'ont pas de droit de remboursement, mais doivent être enregistrés auprès de la banque de votre client final »
- source: https://www.twikey.com/start/index.html
- source-fr: https://www.twikey.com/fr/start/

### core-refund
- en: “A CORE mandate on the other hand doesn't need this registration but allows the customer to request a refund within 8 weeks.”
- nl: “Een CORE-mandaat daarentegen heeft deze registratie niet nodig, maar laat de klant toe om binnen 8 weken een terugbetaling aan te vragen.”
- fr: « Un mandat CORE en revanche ne nécessite pas cet enregistrement mais permet au client de demander un remboursement dans les 8 semaines. »
- source: https://www.twikey.com/start/index.html
- source-nl: https://www.twikey.com/be/start/
- source-fr: https://www.twikey.com/fr/start/

### own-bank
- en: “Collect through your own bank” “Use your own creditor number, account and bank.”
- nl: “Innen via je eigen bank” “Gebruik je eigen schuldeisernummer, rekening en bank.”
- nl-kind: translation (nl) of https://www.twikey.com/product/detail/b2b-direct-debit.html
- fr: « Encaissez par l'intermédiaire de votre propre banque » « Utilisez votre propre numéro de créancier, compte et banque. »
- source: https://www.twikey.com/product/detail/b2b-direct-debit.html
- source-fr: https://www.twikey.com/fr/product/detail/prelevement-sepa-b2b.html

### creditor-id
- en: “Contact the business or corporate banking department at your bank.” “Once your application is approved and the creditor contract is signed, you will receive a unique creditor ID.”
- nl: “Neem contact op met de zakelijke of corporate banking afdeling van je bank.” “Zodra je aanvraag is goedgekeurd en het schuldeisercontract is ondertekend, ontvang je een uniek schuldeisernummer.”
- nl-kind: translation (nl) of https://www.twikey.com/start/index.html
- fr: « Contactez le service bancaire entreprises ou corporate de votre banque. » « Une fois votre demande approuvée et le contrat de créancier signé, vous recevrez un identifiant de créancier unique. »
- source: https://www.twikey.com/start/index.html
- source-fr: https://www.twikey.com/fr/start/

### demo
- en: Ask Twikey for a demo: https://www.twikey.com/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin&utm_campaign=payment-xray
- nl: Vraag Twikey een demo: https://www.twikey.com/be/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin&utm_campaign=payment-xray
- fr: Demandez une démo à Twikey : https://www.twikey.com/fr/demo.html?utm_source=twikey-xray&utm_medium=claude-plugin&utm_campaign=payment-xray
- source: https://www.twikey.com/demo.html
- source-nl: https://www.twikey.com/be/demo.html
- source-fr: https://www.twikey.com/fr/demo.html

## Pricing page

- en: https://www.twikey.com/pricing.html
- nl: https://www.twikey.com/be/pricing.html
- fr: https://www.twikey.com/fr/pricing.html

## Partners page

- en: https://www.twikey.com/partners.html
- nl: https://www.twikey.com/be/partners.html
- fr: https://www.twikey.com/fr/partners.html

## Partners page list

Names as shown on https://www.twikey.com/partners.html on November 3, 2026, software and service
partners only (the page also lists banks and payment providers). The go-live facts say a tool is
"Listed on Twikey's partners page" only when it matches a name below, with the page link and nothing
more. Any other tool: not listed on the partners page, ask Twikey.

- Aangetekend
- AdminPulse
- Alfa-Zet
- Bankswitching
- Billtrust
- Carwise
- Chargebee
- Cipal Schaubroeck
- Civadis
- COEO
- Cox Automotive
- CrediSolv
- Debitan
- Denovit
- Dynamics 365 Business Central
- Easypost
- Exact
- Fid-Manager
- FinBuddy
- Five Degrees
- Gantner Recreatex
- GridHub
- Hubspot
- Icasa
- Informat
- IPEX
- Intrum
- Isabel
- Koalect
- Microsoft Dynamics
- MoveYou
- Nymus
- Odoo
- Onfact
- Optimile
- Palmki
- Payt
- Playpass
- PropPlanner
- Recurly
- ResalePartners
- Salesdock
- Salesforce
- SAP
- SAP Business One
- Signhost
- Smartschool
- SportAlliance
- Starnet
- Surepay
- Teamleader
- Twinfield
- Woocommerce
- Zapfloor
- Zero Friction
- Zoho
- Zuora

## SEPA rules the scripts apply (not Twikey statements)

| Rule | Source |
|---|---|
| “If a Creditor does not present a Collection under a Mandate for a period of 36 months (starting from the date of the latest Collection presented, even if rejected, returned or refunded), the Creditor must cancel the Mandate and is no longer allowed to initiate Collections based on this cancelled Mandate.” Same text in the Core and the B2B rulebook. | EPC SEPA Direct Debit Core Rulebook and SEPA Direct Debit B2B Rulebook, section 4.2. Twikey's MD01 page: “The mandate has not been used for more than 36 months and the bank has cancelled it.” (https://www.twikey.com/product/r-codes/MD01.html) |
| The unique mandate reference “must be unique for each Mandate in combination with the identifier of the Creditor”. | EPC SEPA Direct Debit Core Rulebook, section 4.8.2 (AT-M001) |
| A mandate carries the date of signing (M008) and the signature of the debtor (M009). | EPC SEPA Direct Debit Core Rulebook, section 4.7.2 (DS-01) |
| A change of account by the debtor (“another account within the same PSP or in another PSP”) is a mandate amendment, sent “as part of the next Collection”. | EPC SEPA Direct Debit Core Rulebook, section 4.6.2 (PT-02.02) |
| B2B: the debtor's bank checks the first collection against mandate data “received from or confirmed by the Debtor”. | EPC SEPA Direct Debit B2B Rulebook, section 4.1 |
| SEPA Direct Debit R-transaction reason codes: the codes the plugin shows besides Twikey's 25 (in `scripts/xray/reasons.py`). | EPC Guidance on reason codes for SDD R-transactions, EPC173-14 version 8.0, November 28, 2024, section 3 |
| Belgian structured communication (OGM/VCS): 12 digits, the last two are the first ten modulo 97 (97 when the remainder is 0). | Belgian banking convention, implemented and tested in `scripts/xray/ogm.py` |

