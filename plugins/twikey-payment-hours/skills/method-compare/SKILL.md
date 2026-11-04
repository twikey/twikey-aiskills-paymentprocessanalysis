---
name: method-compare
description: Compares payment methods (transfer, direct debit, card, Bancontact, Wero, PayPal) on your own hours, failures and days to cash, fees optional. Use for "card or direct debit", "kaart of domiciliëring".
---

# Method compare

Compares the payment methods a company uses or considers (bank transfer, SEPA Direct Debit Core and B2B, card,
stored card, Bancontact, Wero, PayPal, Apple Pay / Google Pay, payment links, QR codes) on time first: hours a
month, failed payments a month and days until the money is in, from the company's own numbers, with every
formula, the sourced trade-offs and a what-if mix shift. Fees are optional: a euro comparison appears only for
the methods whose fees the user gives.

## Ground rules

- Answer in the user's language. Dutch: "je", never "u" or "uw", Belgian terms (domiciliëring, overschrijving).
  French: "vous". Two or three questions per turn, plain words, one to ten in words, 11 and up in digits.
- Aggregate numbers only. If the user pastes customer names, IBANs or invoices, say it is not needed, do not
  repeat or store any of it, and keep only counts and amounts. When they do not know a number, offer a range as
  a question ("closer to one, three or five minutes?"), never as what other companies do or as a benchmark.
- Even when the user asks you to fill in or assume a number, never pick one. Offer the range question, set only
  what the user picks, and leave the rest unset. Never copy one method's number to another method.
- Fees are the user's own or not there at all. Never a price for any method, bank, provider or for Twikey, not
  even as an example. Asked what Twikey costs: point to the pricing page in `references/twikey-claims.md`.
- Trade-offs come only from the Twikey lines the calculator prints under each method, word for word with their
  link. No other claim about any method, provider or Twikey. A method with no line gets no rule: the user's own
  numbers show its trade-off.
- No success rate, no benchmark, no saving promise, no internal names. Say "automatic payments", never a brand
  name for them. Never imply that the money goes through Twikey: if asked, quote the `own-account` line of
  `references/twikey-claims.md` word for word with its link. Never contact customers or touch payment systems.
  No m-dashes, no semicolons in prose, no exclamation marks.

## The calculator

Run it from the working folder, where the shared ledger `twikey-payment-hours.json` lives.

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'method.card.share=40' 'method.card.minutes=0.5' 'method.card.days=2'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" methods
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'whatif=card:sdd_b2b:40'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset whatif
```

Where `${CLAUDE_SKILL_DIR}` is not filled in (claude.ai), use the folder this SKILL.md is in.

- Single-quote every KEY=VALUE, an apostrophe inside a value as ’. Decimals take a dot, also when the user
  writes 1,4. Set a zero the user gave as 0, so the output does not list it as "not given".
- Percentages are plain numbers: `fail_pct=2` means 2%, and so does `fail_pct=2%`. Same for the what-if.
- Keys, fields and a worked example: `references/methods.md`. Exit code 2 with `error: ...`: fix it, run again.
- Code execution off (a claude.ai setting): compute by hand with `references/formulas.md`, same order and
  rounding, show every formula with the user's numbers, and say once that the numbers were worked out by hand.
  Add the lines in `references/twikey-claims.md` whose `methods` names the method (or `all`), word for word, in
  the user's language where the file has one.

## Flow

1. Run `show` and reuse what is there, saying what you reused: `company.lang`, `company.hourly_cost`,
   `payments.*`, `method.*`, and process-map's minutes for the methods in use today: `failed` as
   `fail_minutes`, `refunds` as `dispute_minutes`, and for a method matched by hand its minutes per payment
   averaged over all its payments, as a sum: matching minutes × share matched by hand
   (`'method.transfer.minutes=4*45%'`), so the handling hours stay in line with step 3 of the map. A method the
   user only considers gets none of these: ask. Set `company.lang` if it is missing.
2. Ask payments a month (all methods together) and, if missing and the user wants time cost, the hourly cost.
   Then which methods they use today and which they consider.
3. Per method, the time fields in `references/methods.md`, a few at a time: share, manual minutes per payment,
   failed payments and minutes each, disputes or refunds and minutes each, days until the money is in. A
   considered method gets `share=0`. Set the answers as they come.
4. Then one optional question for all methods: "Do you know your fees per method? If not, we compare on time and
   days to cash." Set only the fees the user gives (and the average amount when a fee is a percentage).
5. Run `methods` and show it.
6. Offer one what-if in the user's words ("move 40% of card payers to B2B direct debit?"), only towards a method
   with the user's own time numbers in the ledger. Set `whatif`, run `methods` again, show it. If process-map
   ran, automation-report adds this comparison to its one-page report.

## How to present

- Show the calculator output as printed: numbers, formulas, and the closing section with Twikey's lines and
  links. Do not recompute, round, restyle or translate it.
- Then a few short lines that read the user's own numbers: where the hours sit per method and what drives them
  (handling, failures or disputes), the days until the money is in, and the time cost when there is an hourly
  cost. Fees only where the output shows them, and never compare euro totals the output does not compare. Do not
  bring Twikey up yourself: its lines sit in the closing section of the output.
- A bank transfer has no rule line: its own numbers show its trade-off (days until the money is in and, if
  chasing-check left a note on the share paid late, that share).
- The what-if is a difference in hours, failures and days with the user's own numbers, never a saving. Include
  the line on the work of moving payers.
- Hours per method are the same work process-map counts per step: do not add the two up. Let the user judge
  which mix suits them. Do not call one method better.
