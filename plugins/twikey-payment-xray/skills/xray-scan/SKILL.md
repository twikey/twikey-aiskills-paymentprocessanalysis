---
name: xray-scan
description: Runs the full Twikey Payment X-ray on the coded ledger, failed collections first, then mandates, unmatched payments, payment terms and the manual work they cause, counted from the files, and writes findings.md with customer codes. Then offers the report with the names put back and this month's work, prepared. Use when the user says "run the x-ray", "scan my payments", "full payment scan", "where do we lose money on payments", "show me the leaks", "maak de scan", "waar verliezen we geld op betalingen", "lance l'analyse", "analyse mes paiements", or after xray-setup has read the exports.
---

# Payment X-ray scan

## Before you start

- The workspace is `twikey-xray-workspace/` in the current folder (else use the **xray-setup** skill).
  Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en status`
  with `en`, `nl` or `fr` for the user's language.
- Run every command exactly in that form: `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home
  twikey-xray-workspace --lang <en|nl|fr> <command> ...`, with no pipes, redirects, `cd` or other commands around
  it. In this folder the X-ray guard lets the shell run only X-ray's own commands. Read workspace files with the
  Read tool.
- Never open, read, search or list the raw export folder or the key file. Only the script reads them.
- Answer in the user's language. Use only numbers from the script output, exactly as printed. Write dates out in
  the user's language.
- The scan asks the user nothing. Run every check straight away.

## Steps

1. Run each check with `--json` (same script, same `--home`, same `--lang`):
   1. `decode` (failed collections by bank reason code)
   2. `mandates` (36-month rule and other mandate checks)
   3. `match` (bank payments against invoices)
   4. `terms` (agreed terms against days to pay, payer profiles)
   5. `steps` (the manual steps each finding asks for, counted from the files)
   When the export a check needs is missing (for example no bank statement), the output says it was not checked:
   `checked: false` with a `not_checked` line that names the missing export (in `steps`, per item type, and the
   top-level `not_checked` lists those item types). Write that line in its section, as given. Never write "none"
   or zero for something that was not checked.
2. Write `twikey-xray-workspace/findings.md` with the template below, in the user's language. Codes only, never a
   name.
3. Give the user the three lines of "What we found". Tell the user that customers are codes here and that the
   report puts the names back on their own computer.
4. Offer the report with the names put back: `report` writes it next to the raw exports and prints only its path.
   Run it when the user says yes, and give the path. Do not open the report: it holds names.
5. Offer this month's work, prepared (the **month-prep** skill): collections worth a new attempt with a suggested
   day, customer mail drafts, mandates to renew and match suggestions. Drafts only, nothing is sent.
6. Then offer the go-live plan (the **go-live-plan** skill).

## findings.md

The same structure in every language. Use these headings and labels exactly:

| Part | English | Dutch | French |
|---|---|---|---|
| Title | # Where your payment process leaks | # Waar je betaalproces lekt | # Où votre processus de paiement fuit |
| Summary | ## What we found | ## Wat we vonden | ## Ce que nous avons trouvé |
| Date line | As of <date>. | Stand op <datum>. | Situation au <date>. |
| 1 | ## 1. Failed collections | ## 1. Mislukte domiciliëringen | ## 1. Prélèvements échoués |
| 2 | ## 2. Mandates | ## 2. Mandaten | ## 2. Mandats |
| 3 | ## 3. Payments that match no invoice | ## 3. Betalingen zonder factuur | ## 3. Paiements sans facture |
| 4 | ## 4. Payment terms against reality | ## 4. Betaaltermijn tegenover de praktijk | ## 4. Délais de paiement et réalité |
| 5 | ## 5. Manual work in your files | ## 5. Handwerk in je bestanden | ## 5. Travail manuel dans vos fichiers |
| Twikey label | What Twikey does: | Wat Twikey doet: | Ce que fait Twikey : |

```markdown
<Title>

<Summary>
- <the biggest finding in euros, one line>
- <the second biggest, one line>
- <the third, one line>

<Date line, the as-of date written out in the user's language>

<1>
<count and euros, the split by `by_category`: worth a new attempt / needs a new mandate / needs a
conversation, the failure rate per collection day from `days_of_month` against the rate for all days
(`days_of_month_overall`), the customers with repeated failures, the codes not on Twikey's reason-code
page (`unknown_codes`)>
<Twikey label> <the Twikey line from the decode output> (<its link>, <its package>)

<2>
<the mandates to renew (`to_renew`): expired under the 36-month rule, then expiring within 90 days, each
with its date. Then apart, never counted as to renew: never used since signing, last collection unknown,
incomplete, duplicates, account changes, B2B mandates not confirmed at the customer's bank>
<Twikey label> <Twikey line from the mandates output> (<link>, <package>)

<3>
<paid but still open in the books, partial (with what is still open), bundled (credit notes netted),
paid twice, no match. Other receipts (not invoice payments) in one line apart>
<Twikey label> <Twikey line from the match output> (<link>)

<4>
<payer profiles with open and overdue euros, DSO (days sales outstanding) against the invoices' own terms>
<Twikey label> <the Twikey lines from the terms output> (<links>, <packages>)

<5>
<from the steps output, per item type with a count above zero, biggest steps_total first, one line each:
the count and what it is, then count × (the checklist) = steps_total steps, and the count per month when
the output gives one. Then total_items and total_steps, adding that the lines cover different periods.
Then per_month_total items and per_month_steps_total steps a month when given, for the item types counted
over a period. The item types with a count of zero in one line. The item types not checked, because
their export is missing, in one line with their not_checked line. Then the basis sentence from the
output, as given>
```

Name the item types in section 5 as the output does: `label` for a count above one, `label_one` for a count
of one. These are the labels:

| Item type | English | Dutch | French |
|---|---|---|---|
| `failed_new_attempt` | failed collections worth a new attempt | mislukte domiciliëringen die heraangeboden kunnen worden | prélèvements échoués à présenter à nouveau |
| `failed_new_mandate` | failed collections that need a new mandate | mislukte domiciliëringen die een nieuw mandaat vragen | prélèvements échoués qui demandent un nouveau mandat |
| `failed_conversation` | failed collections that need a conversation | mislukte domiciliëringen die een gesprek met de klant vragen | prélèvements échoués qui demandent un échange avec le client |
| `failed_own_setup` | failed collections caused by your own file or setup | mislukte domiciliëringen door je eigen bestand of instellingen | prélèvements échoués dus à votre propre fichier ou paramétrage |
| `failed_unknown` | failed collections to ask your bank about | mislukte domiciliëringen om na te vragen bij je bank | prélèvements échoués à vérifier auprès de votre banque |
| `mandate_renew` | mandates to renew | te vernieuwen mandaten | mandats à renouveler |
| `mandate_fix` | mandates to correct | te corrigeren mandaten | mandats à corriger |
| `unmatched` | payments to book by hand (no match, partial or bundled) | betalingen om met de hand te boeken (niet gekoppeld, gedeeltelijk of gebundeld) | paiements à comptabiliser à la main (sans correspondance, partiels ou groupés) |
| `double_payment` | invoices paid twice | dubbel betaalde facturen | factures payées deux fois |
| `paid_but_open` | paid invoices still open in your books | betaalde facturen die nog openstaan in je boekhouding | factures payées encore ouvertes dans votre comptabilité |
| `late_invoice` | invoices more than seven days late | facturen die meer dan zeven dagen te laat zijn | factures en retard de plus de sept jours |

The summary comes first, biggest numbers first: the report puts that section at the top. Lead the body with
failed collections. Section 5 takes no Twikey line: the lines in the `steps` output are the ones sections 1 to 3
already carry, so do not repeat them. Do not write in findings.md that the customers are coded: the report puts
the names back, and the sentence would be wrong there. Do not add the demo link: the report ends with it, once.

## Copy rules

- Twikey lines come only from the script output (`"twikey"` fields, or the Twikey lines of the text output),
  exactly as given. They are already in the workspace language, quoted from twikey.com. Keep a line's `mark`
  when it has one, right after the label, the way the text output prints it: "(vertaald uit het Engels)" marks a
  translation of the English page, not a quote, and links that English page. "(Engels)" or "(anglais)" marks a
  line with no text in that language, shown in English. Never translate or reword a Twikey line yourself. Keep
  its link, and its package (`package_label`: Package, Pakket, Formule) when it has one.
- Say nothing else about Twikey. No prices, no customer counts, no success rates.
- Call it automatic payments, never by a brand name. Frame it as getting paid. The customer signs once, and
  the company can collect when the invoice is due.
- Twikey is not a payment provider. The money lands on the company's own bank account.
- Section 5 counts steps, nothing else. Never turn steps into time or money, and do not judge whether the work is
  a lot or a little.
- Dutch: "je" and "je" as the possessive, never "u" or "uw". Belgium "domiciliëring", the Netherlands "incasso".
- A failed collection is "heraangeboden" in Dutch, never "herprobeerd". English: US spelling.
- Numbers one to ten in words in sentences ("three customers", "one more time"), larger numbers in digits. The
  same in the summary. The count × steps lines in section 5 keep the digits.
- Amounts and percentages exactly as the script prints them in text mode for the user's language: the euro sign
  first, then the number written 41,417.50 and 22.6% in English, 41.417,50 and 22,6% in Dutch and French. Never
  "EUR".
- No em-dashes, no semicolons, no hype words. Never say a company is too small for Twikey.
