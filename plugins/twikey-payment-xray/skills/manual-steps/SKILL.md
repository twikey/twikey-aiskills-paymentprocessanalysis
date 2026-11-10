---
name: manual-steps
description: Shows the manual work in a company's payment process, counted from its camt.053 bank statements. Per finding (failed collections by what they need, incoming payments to book by hand) it shows how many items the statements hold and the checklist of manual steps one item asks for when it is done by hand, biggest first. Counted, never turned into time or money. Use when the user asks "how much manual work", "what do we do by hand", "how many manual steps", "hoeveel handwerk", "wat doen we nog manueel", "combien de travail manuel", "qu'est-ce qu'on fait encore à la main".
---

# Manual steps

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the statement folder or the key file.
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
- `count`: the items found on the statements. `months`: the period the count covers. `per_month`: the count per
  month.
- `checklist`: the manual steps one item asks for when it is done by hand, in the workspace language.
  `steps_each`: how many steps that is. `steps_total`: count times steps each.
- `examples`: up to 12 customer or payer codes.

Then `total_items` and `total_steps`, `per_month_total` and `per_month_steps_total`, `basis` (one sentence: the
counts come from the statements, the checklists are the usual steps when the work is done by hand) and `twikey`
(the Twikey lines that fit). Item types with no items are listed with a count of zero.

## Names of the item types

Use `label` and `label_one` from the output. These are the labels:

| Item type | English | Dutch | French |
|---|---|---|---|
| `failed_new_attempt` | failed collections worth a new attempt | mislukte domiciliëringen die heraangeboden kunnen worden | prélèvements échoués à présenter à nouveau |
| `failed_new_mandate` | failed collections that need a new mandate | mislukte domiciliëringen die een nieuw mandaat vragen | prélèvements échoués qui demandent un nouveau mandat |
| `failed_conversation` | failed collections that need a conversation | mislukte domiciliëringen die een gesprek met de klant vragen | prélèvements échoués qui demandent un échange avec le client |
| `failed_own_setup` | failed collections caused by your own file or setup | mislukte domiciliëringen door je eigen bestand of instellingen | prélèvements échoués dus à votre propre fichier ou paramétrage |
| `failed_unknown` | failed collections to ask your bank about | mislukte domiciliëringen om na te vragen bij je bank | prélèvements échoués à vérifier auprès de votre banque |
| `book_by_hand` | incoming payments to book by hand (no valid structured communication) | inkomende betalingen om met de hand te boeken (geen geldige gestructureerde mededeling) | paiements entrants à comptabiliser à la main (sans communication structurée valable) |

## How to present it

1. One line: the total items and the total steps, then the items and steps a month (`per_month_total`,
   `per_month_steps_total`).
2. One line per item type with items, biggest `steps_total` first: the count and its label, then count ×
   (the checklist) = steps total, for example "9 failed collections worth a new attempt: 9 × (look up what
   the reason code means · tell the customer · present the collection again in your bank tool · check whether
   it came through) = 36 steps". Use the checklist exactly as the output gives it, so the user sees what one
   item asks for. Add the count per month, and the example codes when they help.
3. The item types with a count of zero in one line.
4. The `basis` sentence from the output, as given.
5. Offer to prepare this month's part of the work (the **month-prep** skill): collections worth a new attempt
   with a suggested day, and customer mail drafts. Drafts only, nothing is sent.
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
