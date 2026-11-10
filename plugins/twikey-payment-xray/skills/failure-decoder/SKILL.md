---
name: failure-decoder
description: Explains the failed SEPA direct debit collections on a company's camt.053 bank statements by bank reason code (MS03, MD01, MS02, MD06, AC04 and the rest of Twikey's reason-code list) in plain language and in euros, splits them into what is worth a new attempt, what needs a new mandate and what needs a conversation, and shows the failure rate per collection day. Use when the user asks "why do my direct debits fail", "what does MS03 mean", "decode my return codes", "failed collections", "storno's", "mislukte domiciliëringen", "waarom mislukken mijn domiciliëringen", "pourquoi mes prélèvements sont-ils rejetés", "prélèvements rejetés", or "R-transactions".
---

# Failure decoder

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the statement folder or the key file.
Answer in the user's language. In Dutch write "je", never "u" or "uw", and "domiciliëring" in Belgium. Write the
numbers one to ten in words.

Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en decode --json`
exactly like this, with `en`, `nl` or `fr` for the user's language: reason-code texts, links, dates and amounts
come in that language. No pipes, redirects or other commands: in this folder the X-ray guard runs only X-ray's
own commands.

## What the output holds

- `total`: failed collections (`count`) and euros (`amount`) over `period`. A `count` of zero means no direct
  debit came back on the statements that were read.
- `basis`: one sentence on what was counted, the direct debits returned or refunded on the camt.053 statements.
  Give it as it is.
- `by_code`: per reason code the count, euros, `meaning` (Twikey's own text from twikey.com/product/r-codes),
  `categories` and a `page` link in the user's language. `known: false` with a `meaning_source` is a code not on
  Twikey's reason-code page but on the EPC list of SEPA reason codes: give the EPC reason as written (English).
  `known: false` without one is on neither list: say so and suggest asking the bank. `unknown_codes` lists the
  codes not on Twikey's page, under the label "Codes not on Twikey's reason-code page". A row labeled
  "proprietary reason (not shown)" is bank text the script did not keep. "reason not on the statement" is a
  returned collection without a reason. Never invent a meaning.
- `by_category`: per category the count, euros, `meaning` and `customers`. `new_attempt` (worth a new attempt,
  for example MS03 or AM04), `new_mandate` (a new or amended mandate first, for example AC04, or MD01 on a Core
  mandate), `conversation` (talk to the customer, for example MD06 refunds, MS02 refusals, MD01 on a B2B mandate
  the customer has not registered at their bank), `own_setup`, `bank`, `unknown`, `unreadable`. In this month's
  work (the **month-prep** skill) MD01 on a B2B mandate gets its own mail: the customer asks their bank to
  register the mandate.
- `days_of_month`: per usual collection day the failed collections (`failed`), the collections presented
  (`presented`), the months (`months`), the failure rate (`rate_pct`), the runs moved by a weekend or bank
  holiday (`moved_runs`) and `qualifies` (enough collections to count for a suggested day). Only days with two
  months of data or more, over `days_of_month_period`, with new presentations of a failed collection left out
  (`days_of_month_basis`). `days_of_month_overall`: the rate for all days together. Show each rate with the
  collections presented, not the failures alone. When `days_of_month` is empty, leave the day pattern out. That
  happens with less than two months of collections, or when the bank books a direct debit batch as one line
  without the collections in it.
- `days_of_month_return_booked`: returns whose collection is not on the statements, by booking day. They do not
  count for the rate per day.
- `repeat_customers`: per customer code with two or more failures, the number of failures.

## How to present it

1. One line: how many collections failed and how many euros, then the `basis` sentence.
2. A table per reason code: code, count, euros, what it means in plain words, with the page link.
3. Short lines for the split: what is worth a new attempt (euros), what needs a new mandate first, what needs a
   conversation, what to ask the bank. Use "heraangeboden" in Dutch for a new attempt, never "herprobeerd".
4. The failure rate per collection day against the rate for all days, the repeat customers by code, and the codes
   not on Twikey's reason-code page.
5. Offer the **month-prep** skill for the work itself: this month's new attempts with a suggested day, and a
   mail draft per customer.
6. End with the Twikey line from the output (`twikey`), exactly as given, with its link and package. Keep its
   `mark` when it has one ("(Engels)", "(anglais)" or "(vertaald uit het Engels)"). Never translate it yourself.

No prices, no success rates, no other claims about Twikey. Call it automatic payments, never by a brand name.
