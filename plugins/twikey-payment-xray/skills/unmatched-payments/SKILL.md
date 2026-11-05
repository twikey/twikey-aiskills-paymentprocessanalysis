---
name: unmatched-payments
description: Matches incoming bank payments to invoices on the Belgian structured communication (OGM, check digits verified), the amount and the customer code, and finds payments that match no invoice, partial payments, one payment for several invoices, invoices paid twice, and invoices still open in the books that were already paid. Use when the user asks "which payments can't we match", "reconciliation check", "unmatched payments", "paid twice", "open invoices that are already paid", "afletteren", "betalingen koppelen", "welke betalingen vinden we niet terug", "lettrage", "rapprochement bancaire", "quels paiements ne retrouve-t-on pas".
---

# Unmatched payments

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the raw export folder or the key file.
Answer in the user's language. In Dutch write "je", never "u" or "uw". Write the numbers one to ten in words.
The check needs a bank statement (camt.053 or CSV) and the invoices.

Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en match --json`
exactly like this, with `en`, `nl` or `fr` for the user's language. No pipes, redirects or other commands: in this
folder the X-ray guard runs only X-ray's own commands.

## What the output holds

- `credit_lines`: incoming payments (`count`) and euros (`amount`) over `period`.
- Each group below has `count`, `amount`, `customers` and `lines` (per payment line: `line`, `date`, `amount`,
  `customer`, `invoices`).
- `matched`: payments that match an invoice the books already show as paid.
- `paid_but_open`: paid at the bank, still open in the books (`invoices` lists the invoice codes).
- `partial` (with `still_open`, also per line), `bundled` (one payment for several invoices: `invoices` and
  `credit_notes` give how many, credit notes netted with a minus sign), `double` (paid twice), `overpaid`, and
  `unmatched` with `known_customer`, `unknown_party` and `mentions_open_invoice` (the payer's text names an open
  invoice number, so a person can probably place it). Canceled invoices and credit notes on their own are never
  matched.
- `other_receipts`: money from parties that are in none of the invoices, without a structured communication or
  an open invoice number (a deposit refund, a loan). Not invoice payments: mention them apart, never as a leak.
- `method`: how matching works. A payment never settles an invoice issued after it. X-ray never guesses: a
  payment that fits nothing stays unmatched.
- `checked`: `false` without a bank statement. Then `not_checked` holds the line that says so. Give it as it is,
  never that every payment matched.

## How to present it

1. One line: incoming payments in the period and how many matched.
2. The leaks in euros: paid but still open (the books are wrong), paid twice (to refund or credit), partial (with
   what is still open), bundled, unmatched. Use customer and invoice codes. Other receipts in one line apart.
3. Offer the **month-prep** skill for the work itself: match suggestions per payment line, the invoices to close
   in the books and the invoices paid twice.
4. End with the Twikey line from the output (`twikey`), exactly as given, with its link. Keep its `mark` when it
   has one ("(Engels)", "(anglais)" or "(vertaald uit het Engels)"). Never translate it yourself.

No prices, no other claims about Twikey.
