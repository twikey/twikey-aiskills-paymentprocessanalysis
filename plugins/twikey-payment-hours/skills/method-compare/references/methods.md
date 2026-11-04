# Payment methods: what to ask and where the numbers are

Method ids for `method.METHOD.FIELD`: `transfer`, `sdd_core`, `sdd_b2b`, `card`, `card_recurring`, `bancontact`,
`wero`, `paypal`, `wallet` (Apple Pay / Google Pay), `link` (payment link), `qr` (QR code), `other`.

Every number is the user's own. Never fill one in for them and never say what a method usually costs. Time comes
first: most finance teams do not know their fees per method by heart, and the comparison works without them. A
time field not given counts as zero and the output names it. A fee not given stays out of the euro comparison.

## Before the methods

| Key | Ask | Where the user finds it |
|---|---|---|
| `payments.per_month` | How many payments come in a month, all methods together? | Accounting software or bank statements |
| `company.hourly_cost` | What does one hour of the people doing this cost you, charges included? (optional) | Their own payroll figure. No default. Only needed for "time cost" |
| `payments.avg_amount` | Only when the user gives a percentage fee: the average amount of one payment | Money received in a month ÷ payments that month |

## Time fields, asked first for every method

| Field | Ask | Where the user finds it |
|---|---|---|
| `share` | Out of every 100 payments, how many come in this way? | Accounting software or bank statements, counted per method. The shares add up to 100. A method only considered: 0 |
| `minutes` | Manual minutes per payment: taking it in, checking it came in, matching it to the invoice | process-map steps `collect` and `match` if they ran, as a sum averaged over the method's payments. 0 when nobody touches it |
| `fail_pct` | Out of every 100 payments, how many fail (declined, bounced, returned)? | The provider's or bank's report of failed payments, or the user's own count |
| `fail_minutes` | Minutes of work per failed payment | process-map step `failed` if it ran, else the user's estimate |
| `dispute_pct` | Out of every 100 payments, how many are disputed, refunded or charged back? | The provider's dispute or chargeback report, refund requests on the bank statements |
| `dispute_minutes` | Minutes of work per dispute, refund or chargeback | process-map step `refunds` if it ran, else the user's estimate |
| `days` | Days from the invoice or payment request until the money is on your account | Accounting software (average days to pay), bank statements, the provider's payout schedule |

## Fees, one optional question at the end

Ask once, for all methods together: "Do you know your fees per method? If not, we compare on time and days to
cash." Set only the fees the user gives. A method with no fee set simply has no euro block.

| Field | What | Where the user finds it |
|---|---|---|
| `fee_fixed` | Fixed fee per payment, in euros | Cards, Bancontact, Wero, PayPal, Apple Pay / Google Pay, payment links, QR codes: the payment provider's monthly invoice or statement. Direct debits and transfers: the bank's tariff list or invoice. A method only considered: the offer the bank or provider quoted |
| `fee_pct` | Percentage of the amount per payment | Same place as the fixed fee. Needs `payments.avg_amount` |
| `fail_fee` | Fee per failed payment | The provider's invoice or the bank's tariff list |
| `dispute_fee` | Fee per dispute, refund or chargeback | The provider's invoice or the bank's tariff list |

A method counts as one with fees when `fee_fixed` or `fee_pct` is set (0 counts). The calculator compares euro
totals only between methods with fees and names the methods without.

## Per method

The lines named below are ids in `references/twikey-claims.md`. The calculator prints them under the method, word
for word with their link. Use them as they are and add nothing to them.

### Bank transfer (`transfer`)

- Ask: share, manual minutes per payment, days until the money is in (late payers included), and whether any
  transfers come back.
- Trade-off: no Twikey line. Let the user's numbers show it: days until the money is in, minutes per payment,
  and the share paid late if chasing-check left a note in the ledger (`show`, under notes). Say nothing else
  about transfers.

### SEPA Direct Debit Core (`sdd_core`)

- Ask: minutes per payment, failed collections and minutes each, refund requests as `dispute_pct`, days until
  the money is in.
- Lines: `collect-when-due`, `core-refund`, `core-b2b`.

### SEPA Direct Debit B2B (`sdd_b2b`)

- Ask: as Core.
- Lines: `b2b-registered`, `core-b2b`.
- For a what-if towards B2B, ask whether the payers who would move are businesses. The `core-b2b` line is the
  reason to ask.

### Card, one-off (`card`)

- Ask: minutes per payment, declined payments and minutes each, chargebacks and minutes each, days until the
  payout is on the account.
- Lines: `card-chargebacks`.

### Stored card for recurring payments (`card_recurring`)

- Ask: as a one-off card, and count expired or replaced cards among the failed payments.
- Lines: `card-chargebacks`, `tokenization`, `card-expiry`.

### Bancontact, Wero, PayPal, Apple Pay / Google Pay (`bancontact`, `wero`, `paypal`, `wallet`)

- Ask: as a one-off card.
- Trade-off: no Twikey line. The user's numbers show it.

### Payment link (`link`) and QR code (`qr`)

- Ask first what the payer does behind the link or code (card, Bancontact, Wero, a transfer). Count each payment
  once: under that method when the user can split them, else under `link` or `qr`.
- Trade-off: no Twikey line. The user's numbers show it.

### Other (`other`)

- Anything else the user names. The same fields, no Twikey line.

### All methods

- `orchestration` prints once at the end of the comparison.

## Worked example

Made-up answers, to show the commands. Never offer these numbers to a user as typical values.

A company receives 400 payments a month, at an hourly cost of 45. Out of every 100 payments, 60 come in by
transfer and 40 by card. It considers B2B direct debit. It knows its card fees only.

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'company.lang=en' 'company.hourly_cost=45' 'payments.per_month=400'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'method.transfer.share=60' 'method.transfer.minutes=3' 'method.transfer.fail_pct=0' 'method.transfer.dispute_pct=0' 'method.transfer.days=24'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'method.card.share=40' 'method.card.minutes=0.5' 'method.card.fail_pct=2' 'method.card.fail_minutes=10' 'method.card.dispute_pct=0.5' 'method.card.dispute_minutes=30' 'method.card.days=2'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'method.sdd_b2b.share=0' 'method.sdd_b2b.minutes=0.5' 'method.sdd_b2b.fail_pct=1' 'method.sdd_b2b.fail_minutes=10' 'method.sdd_b2b.dispute_pct=0' 'method.sdd_b2b.days=5'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'payments.avg_amount=180' 'method.card.fee_fixed=0.25' 'method.card.fee_pct=1.4' 'method.card.dispute_fee=15'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" methods
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'whatif=card:sdd_b2b:40'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" methods
```

The first `methods` prints per method the hours a month, failures a month, days until the money is in and time
cost, each with its formula, then the euro block for card only, and says that transfer and B2B have no fees.
The second adds the what-if: card 40% − 40% × 40% = 24%, B2B 0% + 16% = 16%, then hours, failures, average days
and time cost before and after. No euro difference, because B2B has no fees.
