# The eight steps

Per step: what counts as the work, what to ask, a count formula to suggest, the estimate prompts and a worked
`set`. `set` below is short for `python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set`, with the path SKILL.md
shows (in claude.ai: the folder SKILL.md is in).

The examples follow one company that sends 400 invoices a month and receives 380 payments, about 70% by bank
transfer and 30% by card. Its numbers show the syntax only. Never offer them to a user as typical. Labels are in
English here: write them in the user's language.

- Count human time only. For a step that is partly automatic, the minutes a person still spends on it.
- An estimate prompt is a question with spread-out options the user picks from or corrects. It is never what
  other companies do. If the user still cannot say, or asks you to fill one in, leave the step out rather than
  pick a number for them.
- A note prints in the report without its key, so write its text as a full phrase in the user's language.
- Ask "think of last month" when a count is hard to place. A number they remember beats a share they guess.

## Before step 1: the anchors

Ask how many invoices or payment requests go out a month, how many payments come in a month, and how customers
pay (a rough share per method). Most count formulas below start from these numbers.

If they do not know a monthly figure, build it with them: invoices a year ÷ 12 (`4800/12`), or customers ×
invoices per customer a month (`200*2`).

```
set 'company.lang=en' 'payments.per_month=380' 'note.method_mix=Payment mix: bank transfer about 70%, card about 30%'
```

## 1. invoice: sending the invoice or payment request

The work: making the invoice or payment request, checking it, sending it (mail, post, e-invoicing network,
payment link) and filing it. Not the order or the quote before it.

Ask:
- How do invoices go out today: one by one by hand, from the accounting software with some hand work, or fully
  automatic? Who sends them?
- How many minutes of someone's time does one take, from making it to sending it?

Count: invoices a month. Add credit notes or payment requests when they take the same work (`400+20`). When
invoices go out in one run a week, count the runs (`52/12`) and ask the minutes per run.

Estimate: "closer to one, three or five minutes per invoice?" When the software makes them: "closer to half a
minute, one or two minutes to check and send one?"

```
set 'task.invoice.main.label=Make and send invoices' 'task.invoice.main.mode=partly' 'task.invoice.main.who=accounting' 'task.invoice.main.count=400' 'task.invoice.main.minutes=2'
```

## 2. collect: how customers pay

The work: what someone does to take a payment in. Preparing and uploading a direct debit file to the bank,
keying in a card payment taken by phone, sending bank details or a payment link on request, checking the
account for money that came in. Money that arrives without anyone touching it is automatic.

Ask (the method mix is known from the anchors):
- Is there hand work per payment or per batch before the money is in? Who does it?
- How many minutes does one take?

Count: payments a month, or only the ones with hand work (`380*30%` for the card payments taken by phone). Per
batch: batches a month.

Estimate: per payment "closer to one, two or five minutes?", per batch "closer to 15, 30 or 60 minutes per run?"

```
set 'task.collect.main.label=Card payments taken by phone' 'task.collect.main.mode=manual' 'task.collect.main.who=customer service' 'task.collect.main.count=380*30%' 'task.collect.main.minutes=2'
```

No hand work at all: mode automatic, minutes 0. The step then shows as automatic with 0.0 hours, which is an
answer, not a gap.

```
set 'task.collect.main.label=Transfers and card payments' 'task.collect.main.mode=automatic' 'task.collect.main.who=no one' 'task.collect.main.count=380' 'task.collect.main.minutes=0'
```

## 3. match: checking incoming payments and matching them to invoices

The work: finding the invoice an incoming payment belongs to and marking it paid. The slow ones: a missing or
wrong reference, a partial payment, one transfer for several invoices, a payout from a payment provider that
bundles many payments and must be split.

Ask:
- Does the accounting software or the bank match payments on its own? What share still needs a person?
- How many minutes does one of those take? Who does it?

Count: payments a month × share matched by hand (`380*40%`). A person matches all of them: `380`, mode manual.

Estimate the share: "closer to a quarter, half or nearly all of them?" The minutes: "closer to one, three or
five minutes for one?"

```
set 'task.match.main.label=Match payments by hand' 'task.match.main.mode=partly' 'task.match.main.who=bookkeeper' 'task.match.main.count=380*40%' 'task.match.main.minutes=3'
```

matching-check goes deeper on this step afterwards.

## 4. chase: reminders and chasing late payers

The work: spotting who is late, reminder mails, phone calls, letters, formal notices, keeping track of promises
to pay. Handing a file to a collection agency counts too.

Ask:
- What share of invoices is paid late, and how many reminders does a late invoice get before it is paid?
- How many minutes for one reminder, looking up the invoice included? Who sends them? Are calls part of it?

Count: invoices a month × share paid late × reminders each (`400*25%*2`).

Estimate the share: "closer to one in ten, one in four or one in two invoices?" The reminders: "one, two, or three and a
call?" The minutes: "closer to two, five or ten minutes per reminder?"

```
set 'task.chase.main.label=Reminders and calls' 'task.chase.main.mode=manual' 'task.chase.main.who=office manager' 'task.chase.main.count=400*25%*2' 'task.chase.main.minutes=5'
```

When mails and calls take very different time and the user splits them, use two tasks instead of `main` (run
`unset task.chase.main` first if it was set, or it counts twice):

```
set 'task.chase.mail.label=Reminder mails' 'task.chase.mail.mode=partly' 'task.chase.mail.who=accounting' 'task.chase.mail.count=400*25%*2' 'task.chase.mail.minutes=2'
set 'task.chase.call.label=Reminder calls' 'task.chase.call.mode=manual' 'task.chase.call.who=office manager' 'task.chase.call.count=400*25%*30%' 'task.chase.call.minutes=10'
```

chasing-check goes deeper on this step afterwards.

## 5. failed: failed payments and retries

The work: a bounced direct debit, a declined or expired card, a payment returned by the bank. Finding out why,
contacting the customer, collecting again, booking it. A transfer that does not arrive is a late payment (step
4), not a failed one.

Ask:
- Do payments fail at all with the way you collect? Think of last month: how many did someone follow up?
- How many minutes for one, from noticing it to the money being in? Who does it?

Count: the number from last month (`6`), or payments by that method × the user's own share that failed. Do not
offer failure rates to pick from.

Estimate the minutes: "closer to five, 15 or 30 minutes for one?"

```
set 'task.failed.main.label=Follow up declined cards' 'task.failed.main.mode=manual' 'task.failed.main.who=customer service' 'task.failed.main.count=6' 'task.failed.main.minutes=15'
```

Customers only pay by transfer and nothing bounces: the step does not apply. Set it with count 0 (see "After
step 8").

## 6. details: setting up and keeping payment details

The work: everything that sets up or changes how a customer pays. A new direct debit mandate (sent, signed,
filed, entered), a stored card, a changed bank account, an expired card to replace, billing details in the
accounting software.

Ask:
- How many new customers and changes to payment details are there a month?
- How many minutes for one, paperwork included? Who does it?

Count: new customers + changes a month (`25+10`).

Estimate: "closer to two, five or ten minutes for one?"

```
set 'task.details.main.label=New customers and account changes' 'task.details.main.mode=manual' 'task.details.main.who=accounting' 'task.details.main.count=25+10' 'task.details.main.minutes=5'
```

## 7. refunds: refunds, disputes and chargebacks

The work: paying money back, a customer who disputes an invoice, a refund request on a direct debit, a card
chargeback. Gathering proof, answering, the credit note, booking it.

Ask: how many last month, how many minutes for one, who handles them?

Count: the number from last month.

Estimate the minutes: "closer to ten, 30 or 60 minutes for one?"

```
set 'task.refunds.main.label=Refunds and disputes' 'task.refunds.main.mode=manual' 'task.refunds.main.who=finance manager' 'task.refunds.main.count=4' 'task.refunds.main.minutes=30'
```

Short step: it may share a turn with step 8.

## 8. reporting: reporting and cash forecasting

The work: the overview of open invoices and who paid, the list of overdue receivables, the cash forecast,
figures for management or the bank.

Ask: how often is it made (each week, each month), how long does it take, who makes it?

Count: reports a month. Weekly: `52/12`. Weekly plus a month-end report: `52/12+1`.

Estimate: "closer to 30 minutes, an hour or half a day?" (half a day is 240 minutes).

```
set 'task.reporting.main.label=Weekly cash overview' 'task.reporting.main.mode=manual' 'task.reporting.main.who=CFO' 'task.reporting.main.count=52/12' 'task.reporting.main.minutes=60'
```

Reporting does not grow with volume by default. If the user says it does, set
`'task.reporting.main.scales=yes'`. Any other task that would stay the same at twice the volume gets
`'task.STEP.main.scales=no'`.

## After step 8

The hourly cost: ask once, the user's own figure, salary and overhead included. Do not offer a range here.

```
set 'company.hourly_cost=45'
```

A step that does not apply gets one task with count 0, so the map shows 0.0 hours instead of "not asked yet".
For a company whose customers only pay by transfer:

```
set 'task.failed.main.label=Does not apply: customers pay by transfer' 'task.failed.main.count=0' 'task.failed.main.minutes=0'
```

Then run `process` and present it as SKILL.md says.
