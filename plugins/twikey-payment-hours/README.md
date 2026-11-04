# Payment Hours

by Twikey

How many hours a month does your company spend on getting paid? Payment Hours works it out with you, step by
step, from your own answers. No exports, no files, no setup.

Getting paid, in eight steps: sending the invoice or payment request, taking in payments, matching payments to
invoices, reminders and chasing late payers, failed payments, setting up and updating payment details, refunds
and disputes, reporting and cash forecasting. Per step Claude asks how you do it today, how often, how many
minutes and who does it. A small calculator turns that into hours a month, full-time equivalents and cost at your
own hourly cost, today and at twice the volume. Every formula is shown, so you can check each number.

## The five skills

| Skill | What it does |
|---|---|
| process-map | Start here. Maps the eight steps with you and calculates hours, FTE and cost per step. |
| method-compare | Compares the payment methods you use or consider (bank transfer, SEPA Direct Debit Core and B2B, card, stored card, Bancontact, Wero, PayPal, Apple Pay and Google Pay, payment links, QR codes), time first: hours a month, failed payments and days until the money is in, and what changes when part of your customers move to another method. Fees are optional. |
| chasing-check | Goes deeper on reminders and late payers: rounds, channels, minutes, who. |
| matching-check | Goes deeper on matching payments to invoices: structured references, payouts to split, partial and bundled payments. |
| automation-report | Puts it all in a one-page report: what we found, the process map, hours per task, what is manual and what grows with volume, assumptions and formulas. |

You don't need to remember the names. Ask in your own words, in English, Dutch or French: "how many hours do
we spend on getting paid?", "hoeveel tijd kost ons betaalproces?", "combien de temps passons-nous à nous faire
payer ?".

## Install

### Claude Code

You need Claude Code 2.1.273 or later, and Python 3.8 or later available as `python3`. On macOS, open Terminal
and run `python3 --version` to check.

Install it from this repository:

```
claude plugin marketplace add twikey/twikey-aiskills-paymentprocessanalysis
claude plugin install twikey-payment-hours@twikey-skills
```

Then ask Claude: "how many hours do we spend on getting paid?"

### claude.ai, Claude Desktop and Cowork

The five skills come as five zip files in the
[`claude-ai` folder](https://github.com/twikey/twikey-aiskills-paymentprocessanalysis/tree/main/claude-ai):
`process-map.zip`, `method-compare.zip`, `chasing-check.zip`, `matching-check.zip` and `automation-report.zip`.
Download them. Skills work on the Free, Pro, Max, Ultra, Team and Enterprise plans.

1. In Settings > Capabilities, switch on "Code execution and file creation" (called "Create and edit files" in
   the updated Settings layout). The skills run a small Python calculator in the conversation's sandbox. With
   code execution off, Claude works the numbers out by hand from the same formulas and says so. On Team and
   Enterprise plans an owner first enables code execution and Skills in Organization settings > Plugins &
   skills, on the Policy tab.
2. Go to Customize > Skills, click "+", choose "+ Create skill", then "Upload a skill", and pick one zip. Repeat
   for the other four.
3. The skills share one answers file, so use them in the same conversation.

## Your data

- The skills ask for counts, minutes, amounts and rates only. They never need customer names, IBANs or invoice
  lists. If you paste them, Claude says it doesn't need them and works with the counts.
- **Your answers stay in your conversation. Nothing is sent to Twikey.** The calculator makes no network calls.
  Like anything you type in a chat, your answers do go to your AI provider.
- Your answers are kept in `twikey-payment-hours.json`, the report in `twikey-payment-hours-report.md`, both in
  the folder Claude works in (in claude.ai: the conversation's sandbox). Delete them when you are done.
- The skills calculate and explain. They never contact your customers and never touch your payment systems.

## What the numbers are

- An estimate from your own answers. Nothing is measured. Where you estimate, the result is only as good as the
  estimate.
- Fees, rates and minutes are always yours. No prices from anyone, no benchmarks, no promised savings.

## Made by Twikey

Twikey makes Payment Hours. In its own words: "Your connection for all your current and future payment needs: we
connect to over 3,500 banks and more than 10 payment service providers." (https://www.twikey.com/). The report
ends with one optional section, "Where Twikey fits", that shows which of your steps a Twikey page describes
automating, with a link to ask Twikey for a demo.

## For developers

The skills run one script, `scripts/hours.py` (keys at the top of the file, formulas in
`references/formulas.md`):

```
python3 -B scripts/hours.py [--ledger FILE] [--lang en|nl|fr] set 'KEY=VALUE' ...
python3 -B scripts/hours.py unset KEY ...
python3 -B scripts/hours.py show
python3 -B scripts/hours.py [--lang en|nl|fr] process
python3 -B scripts/hours.py [--lang en|nl|fr] methods
python3 -B scripts/hours.py [--lang en|nl|fr] report [--out FILE]
```

- Tests: `python3 -B -m unittest discover -s tests`
- Zips for claude.ai: `python3 -B build_zips.py --out ../../claude-ai` (run from `plugins/twikey-payment-hours`)
  copies the calculator and the shared references into each skill, then writes one zip per skill into the
  repository's `claude-ai` folder. `--sync` only copies.
