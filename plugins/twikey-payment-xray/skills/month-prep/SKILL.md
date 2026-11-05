---
name: month-prep
description: Prepares this month's manual payment work from the coded ledger, once. Failed collections worth a new attempt with a suggested day from the company's own failure rates, one mail draft per customer by reason, mandates to renew with a renewal mail draft for each expired one, and match suggestions for payments that match no invoice. Writes month.json with codes and a work pack with the names put back, next to the exports. Drafts only. It sends nothing, contacts no one and writes no bank file. Use when the user says "prepare this month", "what do I do this month", "help me with this month's collections", "bereid deze maand voor", "wat moet ik deze maand doen", "help me met de domiciliëringen van deze maand", "prépare le mois", "qu'est-ce que je dois faire ce mois-ci".
---

# Month prep

Claude prepares this month's manual work once, from the exports the user gave. The user checks every item, sends
the mails and presents the collections in their own bank tool.

## Before you start

- Workspace `twikey-xray-workspace/` (else **xray-setup**). Never open, read, search or list the raw export
  folder, the key file or the work pack `twikey-xray-month-<date>.md`. The work pack sits in the export folder
  and holds names, amounts per customer and invoice numbers. Only the script writes it.
- Answer in the user's language. In Dutch write "je", never "u" or "uw", and "domiciliëring" in Belgium. Write the
  numbers one to ten in words in sentences.
- Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en month --json`
  exactly like this, with `en`, `nl` or `fr` for the user's language. No pipes, redirects or other commands: in
  this folder the X-ray guard runs only X-ray's own commands.
- The mail drafts come in the workspace language. When the user wants them in another language, add
  `--mail-lang` with `en`, `nl` or `fr`, for example
  `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en month --mail-lang fr --json`.
- New attempts and mails cover failures from the last 90 days. Add `--since-days` with another number only when
  the user asks for another window, or says yes to taking in the older open failures (`older_open`).
- Every run writes a new work pack. The earlier one stays where it is.

## What the run writes

1. `twikey-xray-workspace/month.json`: the prepared work with codes only. The `--json` output holds the same
   content, so there is no need to read the file as well.
2. The work pack `twikey-xray-month-<date>.md` in the export folder: the same work with names, amounts and
   invoice numbers put back, on the user's computer. The output gives only its path, in `paths.month_report`.

## What the output holds

- `as_of`, `period` (`from`, `to`), `window` (the failures it looks at), `since_days`, `language`,
  `mail_language`.
- `checked` and `not_checked`, per section (`new_attempts`, `mails`, `mandates_to_renew`, `match_suggestions`,
  `paid_but_open`, `double_payment`): `checked` is `false` when an export a section needs is missing, and then
  `not_checked` holds the line that names it, and the section and its `counts` are `null`. Match suggestions,
  paid but still open and paid twice need the bank statement and the invoices. Mandates to renew need the
  mandate list and a date of last collection. Not checked is not the same as nothing to do.
- `counts`: `new_attempts`, `mails`, `mandates_to_renew`, `match_lines`, `without_candidate`, `paid_but_open`,
  `double_payment`.
- `new_attempts`: failed collections worth a new attempt, whose last failure is within `since_days` of the as-of
  date and that are still open. Per item: `customer`, `mandate` and `invoice` by code, `amount` (the collection),
  `still_owed` (less a part paid since, by transfer or in the books: never ask that part again), `failure_date`
  (the last failure), `first_failure_date`, `attempts`, `reason_code`, `meaning`, `page`, `new_date` and
  `mail_reason` (the reason of the one mail that covers it). A collection presented again and failed again is
  one item with its number of attempts, and its amount counts once. A failure on an expired mandate, or on a
  mandate that later got MD01, is not here: it needs a new mandate.
- `closed` (`collected_later`, `invoice_closed`, `paid_at_bank`, `bank_credit`): failures left out because they
  are no longer owed: a later collection, an invoice closed (paid or canceled) in the books, a payment at the bank
  or a bank credit from that customer. They get no mail. An invoice paid at the bank but still open in the books
  is under `paid_but_open`. `null` without a file with failed collections.
- `older_open`: failed collections from before the window whose invoice is still open in the books. They are in
  no draft. `null` when the invoice list or the file with failed collections is missing.
- An item with `invoice` `null` has no invoice in the exports: the work pack asks the user to check in the books
  that the amount is still owed before sending the mail. `invoice_list` is `false` when there is no invoice list
  at all.
- `suggested_day`: `day`, `presented` (the collections presented on that day), `failed`, `months`, `rate_pct`,
  `overall_rate_pct` (all collections together), `qualifying_days`, `date`, `earliest`, `moved_to_working_day`,
  `notice` and `basis`. A day counts only with 20 or more collections presented over two months or more, a
  collection presented again after a failure left out. A day is suggested only when two or more days count and
  the best one fails less often than all collections together. `date` is the first time that day falls on or
  after `earliest`, 14 days after today or after the as-of date, whichever is later. `notice` is the line about
  the SEPA pre-notification period. `null` means no day, and `day_statistics.no_day_reason` says why:
  `too_little_history`, `no_better_day` (no day fails less often than all collections together) or
  `not_checked` (no camt.053 or camt.054 statement, so the collections presented per day are not known).
- `mails`: one draft per customer, never two, with codes where the names go: `customer`, `reason`, `template`,
  `subject`, `body`, `invoices`, `amount` (what is still owed in total, `null` when unknown), `failure_dates` and
  `items` (all of that customer's open items, each with its `category`, `amount` and `still_owed`). `reason` is one of `conversation` (how would they like to
  pay), `new_mandate` (a new mandate is needed), `b2b_register` (the customer's bank does not know the B2B
  mandate: the customer asks their bank to register it) and `new_attempt` (a new collection is coming). With
  several reasons, the first in that order wins, and the work pack says what else to add to that mail. `template`
  is the reason, except `new_attempt_neutral`: a new
  attempt for another reason than insufficient funds, with a neutral line instead of a request for funds. A
  draft can hold placeholders the user fills in, in the mail language: "[amount]", "[bedrag]" or "[montant]",
  and "[date of the new collection]", "[datum van de nieuwe domiciliëring]" or "[date du nouveau prélèvement]".
- `mandates_to_renew`: expired under the 36-month rule or expiring within 90 days. Per mandate: `customer`,
  `mandate`, `status` (`expired` or `expiring`), `last_collection`, `expiry_date`, `counted_from` (the
  collection the 36 months run from), `still_active` (an open invoice or a collection in the last 12 months,
  `null` when that is not checked because the invoice list or a file with collections is missing),
  `presented_after_expiry`, `failed_after_expiry`, `mail`, `mail_covered_by` and `advice`. Active ones come
  first. An expired mandate gets a renewal draft in `mail`, unless `mail_covered_by` names the customer's mail
  that already covers it. An expiring mandate gets no mail: `advice` is `collect_before_expiry`, a collection on
  it before `expiry_date` keeps it valid. Mandates never used since signing are not in this list.
- `match_suggestions`: `lines` (payment lines with up to three `candidates`, each with its `strength`, and for a
  partial payment `partial_of` and `still_open`), `without_candidate` (a count), `paid_but_open` (invoices to
  close in the books) and `double_payment` (invoices paid twice: contact the customer, refund or credit the
  amount, record it). Strengths, strongest first: `structured_communication` (the structured communication names
  an open invoice), `same_customer_same_amount` (the payer has exactly one open invoice with that amount),
  `amount_only` (exactly one open invoice anywhere with that amount, and no other payment line it could also
  fit: check before you book).
- `closing`: `text` (Claude prepared this once, nothing was sent, no bank file was written), `twikey` (the Twikey
  lines) and `demo`.

## How to present it

Name the sections as the work pack does, in its order:

| Section | English | Dutch | French |
|---|---|---|---|
| `new_attempts` | Collections worth a new attempt | Domiciliëringen die heraangeboden kunnen worden | Prélèvements à présenter à nouveau |
| `mails` | Customer mail drafts | Conceptmails voor klanten | Brouillons de mails aux clients |
| `mandates_to_renew` | Mandates to renew | Te vernieuwen mandaten | Mandats à renouveler |
| `match_suggestions` | Match suggestions | Koppelvoorstellen | Suggestions de rapprochement |
| `double_payment` | Paid twice | Dubbel betaald | Payées deux fois |
| `paid_but_open` | Paid, still open in your books | Betaald, nog open in je boekhouding | Payées, encore ouvertes dans votre comptabilité |

1. One line per section with its count from `counts`, in the order of the table. For match suggestions, the
   count is `match_lines` (payment lines with a candidate), then add the lines without a candidate
   (`without_candidate`). When a section was not checked (`checked` is `false`), give
   its `not_checked` line as it is, never "none" or zero. Counts and codes only, never a name. When `older_open`
   is above zero, say how many older failed collections are still open and are in no draft, and offer to prepare
   the month again with a longer window (`--since-days`, for example 365).
2. The suggested day with its basis, in one or two sentences: the day of the month, the collections presented on
   that day (`presented`) and the months they cover (`months`), its failure rate (`rate_pct`) against the rate
   for all collections (`overall_rate_pct`), and `date`, written out in the user's language. Then `notice`, as
   given. When `suggested_day` is `null`, say why from `day_statistics.no_day_reason` (too little history, no
   day fails less often than all collections together, or not checked because there is no camt.053 or camt.054
   statement), and that the new-attempt drafts hold the date placeholder for the user to fill in. Never invent a
   rule of your own, such as a payday.
3. The path of the work pack, exactly as printed. Say it holds the names, amounts and mail drafts, ready to
   read, and that Claude did not open it.
4. `closing.text`, as given. Then one sentence: every draft is for the user to check and send, and a match
   suggested on the amount only needs a check before it is booked.
5. Then the Twikey label ("What Twikey does:", "Wat Twikey doet:", "Ce que fait Twikey :") and the lines in
   `closing.twikey`, as a list like the work pack: one line each, exactly as given, with their links and
   packages, and no "Twikey:" before them (the label already says it). Keep a line's `mark` before the quote when
   it has one ("(Engels)", "(anglais)" or "(vertaald uit het Engels)"). You may close with `closing.demo` once,
   exactly as given.
6. Offer the drafts in another language (`--mail-lang`) and the go-live plan (the **go-live-plan** skill).

Show a mail draft in the chat only when the user asks, with the codes as they are. Do not rewrite the drafts: the
user edits them in the work pack.

## Copy rules

- Claude prepared this once. What Twikey does comes only from the Twikey lines in the output, word for word. Add
  no sentence of your own about Twikey. No prices, no customer counts, no success rates.
- Call it automatic payments, never by a brand name. Frame it as getting paid.
- Never say or suggest that anything was sent, collected or booked.
- Amounts and percentages the way the script prints them in text mode: the euro sign first, then the number
  written 41,417.50 and 22.6% in English, 41.417,50 and 22,6% in Dutch and French.
- A failed collection is "heraangeboden" in Dutch, never "herprobeerd". English: US spelling.
- No em-dashes, no semicolons, no hype words.
