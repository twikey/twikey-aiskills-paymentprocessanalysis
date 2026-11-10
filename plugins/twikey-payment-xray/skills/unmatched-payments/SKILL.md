---
name: unmatched-payments
description: Sorts the incoming payments on a company's camt.053 bank statements by their structured communication (the Belgian OGM, check digits verified) and finds the payments someone books by hand, without a structured communication or with wrong check digits, with the payers who send them most often. Use when the user asks "which payments can't we match", "which payments do we book by hand", "unmatched payments", "payments without a reference", "afletteren", "betalingen koppelen", "welke betalingen vinden we niet terug", "lettrage", "rapprochement bancaire", "quels paiements ne retrouve-t-on pas".
---

# Unmatched payments

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the statement folder or the key file.
Answer in the user's language. In Dutch write "je", never "u" or "uw". Write the numbers one to ten in words.

Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en payments --json`
exactly like this, with `en`, `nl` or `fr` for the user's language. No pipes, redirects or other commands: in this
folder the X-ray guard runs only X-ray's own commands.

## What the output holds

- `credit_lines`: incoming payments (`count`) and euros (`amount`) over `period`, direct debit collections left
  out.
- `groups`, each with `count`, `amount` and `customers` (payer codes, most payments first):
  - `valid`: a Belgian structured communication with the right check digits. The accounting can book these on
    their own.
  - `invalid`: a structured communication with wrong check digits, often a typo by the payer.
  - `other`: another reference, such as an RF creditor reference. Not checked, so counted apart.
  - `absent`: no structured communication, only free text or nothing.
- `by_hand`: the `invalid` and `absent` payments together, with `count`, `amount`, `share_pct` (of all incoming
  payments), `per_month` and `customers` (payer codes, most payments first).
- `method`: how the payments are sorted.

## How to present it

1. One line: the incoming payments in the period, and how many of them are to book by hand, with their share and
   the count per month.
2. The groups in euros, with the payer codes for `invalid` and `absent`, the payers with the most payments
   first.
3. Payments with another reference in one line apart: they were not checked.
4. End with the Twikey line from the output (`twikey`), exactly as given, with its link. Keep its `mark` when it
   has one ("(Engels)", "(anglais)" or "(vertaald uit het Engels)"). Never translate it yourself.

No prices, no other claims about Twikey. Call it automatic payments, never by a brand name.
