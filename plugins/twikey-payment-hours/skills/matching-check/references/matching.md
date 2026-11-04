# Matching: questions, tasks and commands

Step 3 of getting paid: matching incoming payments to invoices. This file holds the questions in order, how the
answers become tasks in the ledger, a worked example with every command, and the edge cases.

## Words to use

| | Structured reference | Matching |
|---|---|---|
| English | structured communication, the +++123/4567/89012+++ reference on a Belgian invoice | matching, reconciliation |
| Dutch | gestructureerde mededeling (OGM) | afpunten, koppelen, afletteren, afstemmen |
| French | communication structurée | lettrage, rapprochement |

Outside Belgium the same role is played by the RF creditor reference (it starts with RF) or by an invoice number
the accounting software can read. Count those as "with a usable reference". A reference with a typo, or none at
all, counts as without.

## Questions, in order

Two or three per turn. Skip a question the user already answered. Offer a range only as a question.

**Round 1: volume and references**

1. How many payments come in a month, all together? How many of those come through a payment provider (card,
   Bancontact, PayPal and the like) instead of straight onto your bank account?
2. Of the payments straight onto the bank account, what share carries a correct structured communication? If
   they don't know: "closer to a quarter, half or three quarters?"

**Round 2: how they are matched today**

3. Do the payments with a structured communication match on their own today, does someone confirm each proposed
   match, or are they matched by hand like the rest? If someone touches them: minutes each?
4. The rest: where are they matched (accounting software, spreadsheet, bank portal), how long does one take
   ("closer to one, three or five minutes?"), and who does it?

**Round 3: payment provider payouts**

5. How many payouts a month land from the payment provider? How long does it take to split one over the invoices
   it covers ("closer to five, 15 or 30 minutes?"), and who does it? If direct debit collections land as one amount
   per batch that someone splits, count those batches here too.

**Round 4: exceptions**

6. Partial and bundled payments (one invoice paid in parts, one payment for several invoices): how many a month,
   and minutes each?
7. Payments nobody can place (unknown payer, no reference, an amount that fits no invoice): how many a month,
   minutes each until placed, and who?

Last, if the ledger has no `company.hourly_cost`: "Do you want to see the cost too? Then what does an hour of
that work cost you, all in?" Optional.

## From answers to tasks

Each kind of payment is one task in step `match`. Partial, bundled and unplaced payments get their own task and
come out of the by-hand count, so no payment counts twice. Refunds and chargebacks belong to step 7 and failed
payments to step 5, not here.

| NAME | Count (a sum the user agrees to) | mode | minutes |
|---|---|---|---|
| `auto_ref` | (all − via provider) × share with reference | automatic | 0 |
| `check_ref` | same, when someone confirms each match | partly | theirs |
| `ref_by_hand` | same, when they are matched by hand | manual | theirs |
| `by_hand` | (all − via provider) × share without − partial and bundled − unplaced | manual | theirs |
| `payouts` | payouts a month (plus direct debit batches) | manual or partly | theirs |
| `partial_bundled` | partial and bundled payments a month | manual | theirs |
| `unplaced` | payments nobody can place a month | manual | theirs |
| `review` | checking the software's matches, when done in a block | partly | theirs |

Write the share without a reference as the user agreed it: `35%`, or `(100-65)%` when 65% carry one. Use only the tasks that apply. Split a task in two when the user gives two different
minutes (partial and bundled separately, say). Another matching task the user names, such as a month-end
clean-up of the suspense account, gets its own NAME, with `scales=no` if it does not grow with volume.

Labels, in the user's language:

| NAME | English | Dutch | French |
|---|---|---|---|
| `auto_ref` | Payments with a structured reference, matched by the software | Betalingen met gestructureerde mededeling, automatisch gekoppeld | Paiements avec communication structurée, lettrés par le logiciel |
| `check_ref` | Payments with a structured reference, match confirmed by hand | Betalingen met gestructureerde mededeling, koppeling met de hand bevestigd | Paiements avec communication structurée, lettrage confirmé à la main |
| `ref_by_hand` | Payments with a structured reference, matched by hand | Betalingen met gestructureerde mededeling, met de hand gekoppeld | Paiements avec communication structurée, lettrés à la main |
| `by_hand` | Payments without a usable reference, matched by hand | Betalingen zonder bruikbare mededeling, met de hand gekoppeld | Paiements sans référence exploitable, lettrés à la main |
| `payouts` | Payment provider payouts split over invoices | Uitbetalingen van de betaalprovider over facturen verdelen | Versements du prestataire de paiement répartis sur les factures |
| `partial_bundled` | Partial and bundled payments | Deelbetalingen en gebundelde betalingen | Paiements partiels et groupés |
| `unplaced` | Payments nobody can place | Betalingen die niemand kan plaatsen | Paiements que personne ne parvient à attribuer |
| `review` | Checking the software’s matches | Koppelingen van de software nakijken | Vérifier les lettrages du logiciel |

Write an apostrophe inside a value as ’ (the software’s matches) so the single quotes around KEY=VALUE hold.

## Worked example

The ledger holds the rough estimate from process-map: `task.match.main` with 400 payments at 2 minutes.
`process` prints step 3 as 13.3 h (400 × 2 ÷ 60).

The answers: 800 payments a month, 200 of them by card and Bancontact through a payment provider that pays out
about 22 times a month. 65% of the payments on the bank carry a structured communication, and the accounting
software matches those on its own. The rest are matched by hand in the accounting software, about three minutes
each. A payout takes about 15 minutes to split. 25 partial or bundled payments a month at ten minutes, and eight
that nobody can place at 20 minutes. All by the accounting clerk, sales helps with the unplaced ones.

Read back:

- straight onto the bank: 800 − 200 = 600
- matched by the software: (800 − 200) × 65% = 390
- matched by hand: (800 − 200) × 35% − 25 − 8 = 177, the partial, bundled and unplaced ones counted apart
- payouts 22, partial and bundled 25, unplaced 8

After a yes:

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset task.match
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set \
  'task.match.auto_ref.count=(800-200)*65%' 'task.match.auto_ref.minutes=0' \
  'task.match.auto_ref.mode=automatic' 'task.match.auto_ref.who=accounting software' \
  'task.match.auto_ref.label=Payments with a structured reference, matched by the software' \
  'task.match.by_hand.count=(800-200)*35%-25-8' 'task.match.by_hand.minutes=3' \
  'task.match.by_hand.mode=manual' 'task.match.by_hand.who=accounting clerk' \
  'task.match.by_hand.label=Payments without a usable reference, matched by hand' \
  'task.match.payouts.count=22' 'task.match.payouts.minutes=15' \
  'task.match.payouts.mode=manual' 'task.match.payouts.who=accounting clerk' \
  'task.match.payouts.label=Payment provider payouts split over invoices' \
  'task.match.partial_bundled.count=25' 'task.match.partial_bundled.minutes=10' \
  'task.match.partial_bundled.mode=manual' 'task.match.partial_bundled.who=accounting clerk' \
  'task.match.partial_bundled.label=Partial and bundled payments' \
  'task.match.unplaced.count=8' 'task.match.unplaced.minutes=20' \
  'task.match.unplaced.mode=manual' 'task.match.unplaced.who=accounting clerk and sales' \
  'task.match.unplaced.label=Payments nobody can place'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process
```

`process` then prints step 3 as 21.3 h, from the rows 0.0 + 8.9 + 4.2 + 5.5 + 2.7. What changed: 21.3 − 13.3 =
8.0 h more a month on matching, and the total grows by the same 8.0 h. The rough estimate left out the payouts and
the exceptions.

## Edge cases

**The accounting software already matches most.** Do not inflate the step. Set `auto_ref` with the large share
and keep the by-hand count small. Still ask about payouts and exceptions, where the remaining time sits. If
someone checks the software's matches in one block, add `review`: weekly for 30 minutes is
`'task.match.review.count=52/12'` with `minutes=30`. If step 3 comes out small, say so plainly.

**Payments only through a payment provider.** Nothing lands one by one on the bank, so skip `auto_ref` and
`by_hand`. The work is `payouts` (fees and refunds netted in a payout are part of its minutes) and `unplaced`
for payout lines that fit no order or invoice. If the provider's plugin books payouts in the accounting software
on its own, set `payouts` to automatic or partly, with the minutes someone still spends.

**The user knows only total hours.** Use one task, `total`: count = how often (days or sessions a month),
minutes = the length of one. Two days of about 8 hours: `'task.match.total.count=2'`
`'task.match.total.minutes=8*60'`, label "Matching, all of it (your estimate)". Offer one check as a question:
"2 × 480 ÷ 600 payments = 1.6 minutes a payment. Does that sound right?" Split it into the tasks above only if
the user wants to.

**No structured communication at all.** Share with a reference = 0%. Skip `auto_ref`. All bank payments minus the
exceptions go to `by_hand`.

**Exceptions bigger than the by-hand count.** The calculator stops with "negative value". Ask where the
exceptions sit: bundled payments often carry one valid reference. Take the rest out of the reference task
instead, for example `(800-200)*65%-10`.

**Counts per week or per day.** A week to a month: `× 52 ÷ 12`, as in `'task.match.by_hand.count=40*52/12'`. A
day to a month: ask how many working days a month and multiply.

**No rough estimate in the ledger.** Skip the comparison. Run `unset task.match` anyway, then set the tasks. At
the end offer **process-map** for the other steps.

**process-map split step 3 into several tasks.** `unset task.match` removes all of them. Compare step 3 as a
whole.
