---
name: manual-steps
description: Shows the manual work in a company's payment process, counted from its own exports. Per finding (failed collections by what they need, mandates to renew or correct, payments to book by hand, invoices paid twice, paid invoices still open in the books, late invoices) it shows how many items the files hold and the checklist of manual steps one item asks for when it is done by hand, biggest first. Counted, never turned into time or money. Use when the user asks "how much manual work", "what do we do by hand", "how many manual steps", "hoeveel handwerk", "wat doen we nog manueel", "combien de travail manuel", "qu'est-ce qu'on fait encore à la main".
---

# Manual steps

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the raw export folder or the key file.
Answer in the user's language. In Dutch write "je", never "u" or "uw", and "domiciliëring" in Belgium. Write the
numbers one to ten in words in sentences.

Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en steps --json`
exactly like this, with `en`, `nl` or `fr` for the user's language: the checklists come in that language. No
pipes, redirects or other commands: in this folder the X-ray guard runs only X-ray's own commands. The command
needs no input from the user. Run it straight away.

## What the output holds

`items`, one per item type (`id`, in the table below):
- `label` (for a count above one) and `label_one` (for a count of one): the name of the item type in the
  workspace language.
- `count`: the items found in the files. `months`: the period the count covers. `per_month`: the count per
  month, null when the period is unknown.
- `checklist`: the manual steps one item asks for when it is done by hand, in the workspace language.
  `steps_each`: how many steps that is. `steps_total`: count times steps each.
- `examples`: up to 12 customer codes.
- `checked`: `false` when the export this item type needs is missing. Then `not_checked` holds the line that
  names it, and the count is not a count of zero.

Then `total_items` and `total_steps` (the lines cover different periods), `per_month_total` and
`per_month_steps_total` (when they can be computed, over the item types counted over a period, leaving out the
ones in `per_month_left_out`), `not_checked` (the item types not checked), `basis` (one sentence: the counts
come from the files, the checklists are the usual steps when the work is done by hand) and `twikey` (the Twikey
lines that fit). Item types with no items are listed with a count of zero.

## Names of the item types

Use `label` and `label_one` from the output. These are the labels:

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

## How to present it

1. One line: the total items and the total steps, adding that the lines cover different periods. Then, when the
   output gives them, the items and steps a month (`per_month_total`, `per_month_steps_total`) for the item types
   counted over a period.
2. One line per item type with items, biggest `steps_total` first: the count and its label, then count ×
   (the checklist) = steps total, for example "9 failed collections worth a new attempt: 9 × (look up what
   the reason code means · tell the customer · present the collection again in your bank tool · check whether
   it came through) = 36 steps", or "1 invoice paid twice: 1 × (contact the customer · refund or credit the
   amount · record it) = 3 steps". Use the checklist exactly as the output gives it, so the user sees what one
   item asks for. Add the count per month when the output gives one, and the example customers by code when
   they help.
3. The item types with a count of zero in one line. The item types not checked, because their export is missing,
   in another line with their `not_checked` line. Never call those zero.
4. The `basis` sentence from the output, as given.
5. Offer to prepare this month's part of the work (the **month-prep** skill): collections worth a new attempt
   with a suggested day, customer mail drafts, mandates to renew and match suggestions. Drafts only, nothing is
   sent.
6. End with the Twikey lines from the output (`twikey`), exactly as given, with their links and packages. Keep a
   line's `mark` when it has one ("(Engels)", "(anglais)" or "(vertaald uit het Engels)"). Never translate a line
   yourself.

## Copy rules

- Count steps, nothing else. Never turn steps into time or money, and never ask the user how long a step takes.
- Do not judge whether the work is a lot or a little. Never say a company is too small (or big enough) for
  Twikey.
- Twikey lines only from the output, word for word. No prices, no customer counts, no success rates.
- Call it automatic payments, never by a brand name.
- A failed collection is "heraangeboden" in Dutch, never "herprobeerd". English: US spelling.
- The count × steps lines keep the digits. Everywhere else, numbers one to ten in words.
- No em-dashes, no semicolons, no hype words.
