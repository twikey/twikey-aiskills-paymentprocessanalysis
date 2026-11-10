---
name: month-prep
description: Prepares this month's direct debit work from the coded ledger read from camt.053 bank statements, once. Failed collections worth a new attempt with a suggested day from the company's own failure rates, and one mail draft per customer by reason. Writes month.json with codes and a work pack with the names put back, next to the statements. Drafts only. It sends nothing, contacts no one and writes no bank file. Use when the user says "prepare this month", "what do I do this month", "help me with this month's collections", "bereid deze maand voor", "wat moet ik deze maand doen", "help me met de domiciliëringen van deze maand", "prépare le mois", "qu'est-ce que je dois faire ce mois-ci".
---

# Month prep

Claude prepares this month's direct debit work once, from the camt.053 bank statements the user gave. The user
checks every item, sends the mails and presents the collections in their own bank tool.

## Before you start

- Workspace `twikey-xray-workspace/` (else **xray-setup**). Never open, read, search or list the statement
  folder, the key file or the work pack `twikey-xray-month-<date>.md`. The work pack sits in the statement folder
  and holds names, amounts per customer and mandate references. Only the script writes it.
- Answer in the user's language. In Dutch write "je", never "u" or "uw", and "domiciliëring" in Belgium. Write the
  numbers one to ten in words in sentences.
- Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en month --json`
  exactly like this, with `en`, `nl` or `fr` for the user's language. No pipes, redirects or other commands: in
  this folder the X-ray guard runs only X-ray's own commands.
- The mail drafts come in the workspace language. When the user wants them in another language, add
  `--mail-lang` with `en`, `nl` or `fr`, for example
  `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en month --mail-lang fr --json`.
- New attempts and mails cover failures from the last 90 days. Add `--since-days` with another number only when
  the user asks for another window.
- Every run writes a new work pack. The earlier one stays where it is.

## What the run writes

1. `twikey-xray-workspace/month.json`: the prepared work with codes only. The `--json` output holds the same
   content, so there is no need to read the file as well.
2. The work pack `twikey-xray-month-<date>.md` in the statement folder: the same work with names and mandate
   references put back, on the user's computer. The output gives only its path, in `paths.month_report`.

## What the output holds

- `as_of`, `period` (`from`, `to`), `window` (the failures it looks at), `since_days`, `language`,
  `mail_language`.
- `counts`: `new_attempts` and `mails`.
- `new_attempts`: failed collections worth a new attempt, whose last failure is within `since_days` of the as-of
  date and that are still open. Per item: `customer` and `mandate` by code, `amount`, `failure_date` (the last
  failure), `first_failure_date`, `attempts`, `reason_code`, `meaning`, `page`, `new_date` and `mail_reason` (the
  reason of the one mail that covers it). A collection presented again and failed again is one item with its
  number of attempts, and its amount counts once. A failure on a mandate that later got MD01 is not here: it
  needs a new mandate or, on a B2B mandate, a registration at the customer's bank.
- `closed` (`collected_later`, `paid_by_transfer`): failures left out because they are no longer owed: a later
  collection on the same mandate, or a later transfer from that customer that covers the amount. They get no
  mail.
- `suggested_day`: `day`, `presented` (the collections presented on that day), `failed`, `months`, `rate_pct`,
  `overall_rate_pct` (all collections together), `qualifying_days`, `date`, `earliest`, `moved_to_working_day`,
  `notice` and `basis`. A day counts only with 20 or more collections presented over two months or more, a
  collection presented again after a failure left out. A day is suggested only when two or more days count and
  the best one fails less often than all collections together. `date` is the first time that day falls on or
  after `earliest`, 14 days after today or after the as-of date, whichever is later. `notice` is the line about
  the SEPA pre-notification period. `null` means no day, and `day_statistics.no_day_reason` says why:
  `too_little_history` or `no_better_day` (no day fails less often than all collections together).
- `mails`: one draft per customer, never two, with codes where the names go: `customer`, `reason`, `template`,
  `subject`, `body`, `amount` (the total of the open items), `failure_dates` and `items` (all of that customer's
  open items, each with its `category` and `amount`). `reason` is one of `conversation` (how would they like to
  pay), `new_mandate` (a new mandate is needed), `b2b_register` (the customer's bank does not know the B2B
  mandate: the customer asks their bank to register it) and `new_attempt` (a new collection is coming). With
  several reasons, the first in that order wins, and the work pack says what else to add to that mail.
  `template` is the reason, except `new_attempt_neutral`: a new attempt for another reason than insufficient
  funds, with a neutral line instead of a request for funds. Without a suggested day, a new-attempt draft holds
  the placeholder "[date of the new collection]", "[datum van de nieuwe domiciliëring]" or "[date du nouveau
  prélèvement]" for the user to fill in.
- `closing`: `text` (Claude prepared this once, nothing was sent, no bank file was written), `twikey` (the Twikey
  lines) and `demo`.

## How to present it

Name the sections as the work pack does, in its order:

| Section | English | Dutch | French |
|---|---|---|---|
| `new_attempts` | Collections worth a new attempt | Domiciliëringen die heraangeboden kunnen worden | Prélèvements à présenter à nouveau |
| `mails` | Customer mail drafts | Conceptmails voor klanten | Brouillons de mails aux clients |

1. One line per section with its count from `counts`. Counts and codes only, never a name. Then how many failures
   were left out as no longer owed (`closed`).
2. The suggested day with its basis, in one or two sentences: the day of the month, the collections presented on
   that day (`presented`) and the months they cover (`months`), its failure rate (`rate_pct`) against the rate
   for all collections (`overall_rate_pct`), and `date`, written out in the user's language. Then `notice`, as
   given. When `suggested_day` is `null`, say why from `day_statistics.no_day_reason` (too little history, or no
   day fails less often than all collections together), and that the new-attempt drafts hold the date
   placeholder for the user to fill in. Never invent a rule of your own, such as a payday.
3. The path of the work pack, exactly as printed. Say it holds the names, amounts and mail drafts, ready to
   read, and that Claude did not open it.
4. `closing.text`, as given. Then one sentence: every draft is for the user to check and send, after checking in
   the books that the amount is still owed.
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
  written 8,508.50 and 20.2% in English, 8.508,50 and 20,2% in Dutch and French.
- A failed collection is "heraangeboden" in Dutch, never "herprobeerd". English: US spelling.
- No em-dashes, no semicolons, no hype words.
