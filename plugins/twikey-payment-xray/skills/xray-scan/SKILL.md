---
name: xray-scan
description: Runs the full Twikey Payment X-ray on the coded ledger read from camt.053 bank statements, failed collections first, then the incoming payments booked by hand and the manual work they cause, and writes findings.md with customer codes. Then offers the report with the names put back and this month's work, prepared. Use when the user says "run the x-ray", "scan my payments", "full payment scan", "where do we lose money on direct debits", "show me the leaks", "maak de scan", "waar verliezen we geld op betalingen", "lance l'analyse", "analyse mes paiements", or after xray-setup has read the statements.
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
- Never open, read, search or list the statement folder or the key file. Only the script reads them.
- Answer in the user's language. Use only numbers from the script output, exactly as printed. Write dates out in
  the user's language.
- The scan asks the user nothing. Run every check straight away.

## Steps

1. Run each check with `--json` (same script, same `--home`, same `--lang`):
   1. `decode` (failed collections by bank reason code, the failure rate per collection day)
   2. `payments` (incoming payments, and the ones to book by hand)
   3. `steps` (the manual steps each finding asks for, counted from the statements)
2. Write `twikey-xray-workspace/findings.md` with the template below, in the user's language. Codes only, never a
   name.
3. Give the user the three lines of "What we found". Tell the user that customers are codes here and that the
   report puts the names back on their own computer.
4. Offer the report with the names put back: `report` writes it next to the statements and prints only its path.
   Run it when the user says yes, and give the path. Do not open the report: it holds names.
5. Offer this month's work, prepared (the **month-prep** skill): collections worth a new attempt with a suggested
   day, and customer mail drafts. Drafts only, nothing is sent.
6. Then offer the go-live plan (the **go-live-plan** skill).

## findings.md

The same structure in every language. Use these headings and labels exactly:

| Part | English | Dutch | French |
|---|---|---|---|
| Title | # Where your payment process leaks | # Waar je betaalproces lekt | # Où votre processus de paiement fuit |
| Summary | ## What we found | ## Wat we vonden | ## Ce que nous avons trouvé |
| Date line | As of <date>. | Stand op <datum>. | Situation au <date>. |
| 1 | ## 1. Failed collections | ## 1. Mislukte domiciliëringen | ## 1. Prélèvements échoués |
| 2 | ## 2. Payments to book by hand | ## 2. Betalingen om met de hand te boeken | ## 2. Paiements à comptabiliser à la main |
| 3 | ## 3. Manual work in your bank statements | ## 3. Handwerk in je bankafschriften | ## 3. Travail manuel dans vos relevés bancaires |
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
conversation / ask your bank, the failure rate per collection day from `days_of_month` against the rate for
all days (`days_of_month_overall`), the customers with repeated failures, the codes not on Twikey's
reason-code page (`unknown_codes`), and the `basis` sentence>
<Twikey label> <the Twikey line from the decode output> (<its link>, <its package>)

<2>
<the incoming payments in the period, then `by_hand`: how many, their share, the euros and the count per
month, and the payer codes that send them most often. The payments with another reference, apart>
<Twikey label> <the Twikey line from the payments output> (<its link>)

<3>
<from the steps output, per item type with a count above zero, biggest steps_total first, one line each:
the count and what it is, then count × (the checklist) = steps_total steps, and the count per month. Then
total_items and total_steps, and per_month_total items and per_month_steps_total steps a month. The item
types with a count of zero in one line. Then the basis sentence from the output, as given>
```

Name the item types in section 3 as the output does: `label` for a count above one, `label_one` for a count
of one. These are the labels:

| Item type | English | Dutch | French |
|---|---|---|---|
| `failed_new_attempt` | failed collections worth a new attempt | mislukte domiciliëringen die heraangeboden kunnen worden | prélèvements échoués à présenter à nouveau |
| `failed_new_mandate` | failed collections that need a new mandate | mislukte domiciliëringen die een nieuw mandaat vragen | prélèvements échoués qui demandent un nouveau mandat |
| `failed_conversation` | failed collections that need a conversation | mislukte domiciliëringen die een gesprek met de klant vragen | prélèvements échoués qui demandent un échange avec le client |
| `failed_own_setup` | failed collections caused by your own file or setup | mislukte domiciliëringen door je eigen bestand of instellingen | prélèvements échoués dus à votre propre fichier ou paramétrage |
| `failed_unknown` | failed collections to ask your bank about | mislukte domiciliëringen om na te vragen bij je bank | prélèvements échoués à vérifier auprès de votre banque |
| `book_by_hand` | incoming payments to book by hand (no valid structured communication) | inkomende betalingen om met de hand te boeken (geen geldige gestructureerde mededeling) | paiements entrants à comptabiliser à la main (sans communication structurée valable) |

The summary comes first, biggest numbers first: the report puts that section at the top. Lead the body with
failed collections. Section 3 takes no Twikey line: the lines in the `steps` output are the ones sections 1 and 2
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
- Section 3 counts steps, nothing else. Never turn steps into time or money, and do not judge whether the work is
  a lot or a little.
- Dutch: "je" and "je" as the possessive, never "u" or "uw". Belgium "domiciliëring", the Netherlands "incasso".
- A failed collection is "heraangeboden" in Dutch, never "herprobeerd". English: US spelling.
- Numbers one to ten in words in sentences ("three customers", "one more time"), larger numbers in digits. The
  same in the summary. The count × steps lines keep the digits.
- Amounts and percentages exactly as the script prints them in text mode for the user's language: the euro sign
  first, then the number written 8,508.50 and 20.2% in English, 8.508,50 and 20,2% in Dutch and French. Never
  "EUR".
- No em-dashes, no semicolons, no hype words. Never say a company is too small for Twikey.
