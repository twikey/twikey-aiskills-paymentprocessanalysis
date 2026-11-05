# Twikey Payment X-ray

A free plugin for Claude Code that shows where your direct debit process leaks and how much manual work each leak
causes, counted from your own bank and accounting exports. Then it prepares this month's work for you: the
collections worth a new attempt, one mail draft per customer, the mandates to renew and match suggestions for your
books. It runs on your own computer. It sends no mails and no collections, and Twikey receives nothing.

Made by Twikey for finance teams that already collect by SEPA (Single Euro Payments Area) Direct Debit.

## Why we made this

When a direct debit collection fails, someone looks up the bank's reason code, mails the customer, presents the
collection again in the bank tool and checks whether it came through. An expired mandate means a new signature. A
payment without a usable reference means a search through open invoices. That work is spread over several people
and several months, so the total is hard to see. X-ray counts it from the exports you already have.

## What you get

### 1. The scan: where your process leaks

- **Failed collections** by bank reason code (MS03, MD01, AM04 and the rest), in plain language and in euros:
  which ones are worth a new attempt, which need a new mandate and which need a conversation with the customer.
  Plus the failure rate per collection day.
- **Mandates** that expired under the SEPA 36-month rule or expire within 90 days, and mandates with missing or
  wrong data.
- **Payments** that match no invoice, partial and bundled payments, invoices paid twice, and invoices paid at the
  bank but still open in your books.
- **Payment terms against reality**: how many days each customer really takes to pay, with Days Sales
  Outstanding (DSO) and payer profiles from "clockwork" to "at risk".

When a check needs an export you did not give, the scan says "Not checked" and names the export.

### 2. The manual work, counted

For each finding: how many items your files hold, and the steps one item takes when it is done by hand. The items
are counted from your files. The steps come from a fixed checklist in `data/manual_steps.json`, and your own
process may have more or fewer. From the demo:

```
168 invoices more than seven days late: 168 × (send a reminder · follow up) = 336 steps
9 failed collections worth a new attempt: 9 × (look up what the reason code means · tell the customer ·
  present the collection again in your bank tool · check whether it came through) = 36 steps
7 failed collections that need a conversation: 7 × (look up the reason code · contact the customer ·
  agree on how they will pay · record the outcome) = 28 steps
4 mandates to renew: 4 × (check which mandates have expired or will expire · send the customer a new mandate ·
  follow up until it is signed · record it) = 16 steps
(six more lines)
Total: 205 items, 462 steps (the lines cover different periods).
```

### 3. This month's work, prepared

A work pack, written next to your exports, with:

- **Collections worth a new attempt**: failed in the last 90 days and still open, with a suggested collection
  day. That is the day of the month that fails least often in your own data, at least 14 days out for the usual
  SEPA pre-notification.
- **One mail draft per customer**, in English, Dutch or French, covering that customer's failed collections of
  the last 90 days that are still open: a new collection is coming, how they would like to pay, a new mandate is
  needed, or their bank has to register the B2B (business-to-business) mandate.
- **Mandates to renew**, with a renewal mail draft for each expired one.
- **Match suggestions**: for each payment that matches no invoice, up to three open invoices that could fit.

A Dutch draft from the demo, for a fictional customer. The date is the suggested collection day, so it moves with
the day you run it.

```
Subject: Nieuwe domiciliëring van €550,50 op 25 november 2026

Beste Garage Testmans BV,

We konden het volgende niet innen via domiciliëring:
- factuur VF-0399: €550,50, domiciliëring van 5 oktober 2026

We bieden de domiciliëring van €550,50 opnieuw aan op 25 november 2026.
Wil je ervoor zorgen dat er die dag voldoende saldo op je rekening staat?

Bedankt,
[naam van je bedrijf]
```

Every mail is a draft for you to check and send yourself. The drafts do not mention Twikey.

### 4. A report and a go-live plan

The report is the scan with the customer names put back in, written next to your exports. If you want, Claude
also writes a go-live plan for switching to Twikey, from the scan and five questions.

## What the demo shows

Say "try the payment x-ray demo" and X-ray runs on the exports of a fictional Belgian wholesaler: 41 customers,
473 invoices and exports from November 2025 to October 2026. Every name, address and IBAN in it is made up.

```
Failed collections in 12 months    19, €12,484.50
Worth a new attempt                9 in 12 months, €5,104.50 (2 still open from the last 90 days)
Mandates to renew                  4 (3 expired, 1 expiring within 90 days)
Payments to book by hand           5
Invoices paid twice                1, €825.50
Suggested collection day           the 25th: 0 of its 21 collections failed, against 21.7% of all
                                   collections (August to October)
Manual work in the files           205 items, 462 steps
```

## What is in this download

```
.claude-plugin/marketplace.json    Tells Claude Code which plugin this repository holds
plugins/twikey-payment-xray/
  skills/                          Nine skills: the instructions Claude follows for each task
  scripts/                         The Python program that reads your exports, codes them, does every count
                                   and runs the guard
  hooks/                           Switches on the guard before every tool call Claude makes
  data/                            Reason codes, checklists and mail templates in English, Dutch and French,
                                   plus every line about Twikey the plugin may quote, with its source page
  demo/                            Exports of the fictional company
  tests/                           250 automated tests
  README.md                        The full documentation
LICENSE                            MIT
```

The program uses the Python standard library only and makes no network calls. The checklists, mail templates and
reason codes are plain text files you can read before you run anything.

You do not need to remember the skill names. Ask in your own words:

| Skill | What it does | Say, for example |
|---|---|---|
| `xray-setup` | Shows the data notice, creates the workspace and reads your exports | "set up the payment x-ray" |
| `xray-scan` | Runs the full scan, failed collections first | "run the x-ray" |
| `failure-decoder` | Failed collections by reason code | "why did these collections fail?" |
| `mandate-health` | The 36-month rule and other mandate checks | "which mandates do I need to renew?" |
| `unmatched-payments` | Bank payments against invoices | "which payments match no invoice?" |
| `terms-vs-reality` | Agreed terms against days to pay | "who pays later than agreed?" |
| `manual-steps` | The manual work per finding, counted | "how much manual work is in my files?" |
| `month-prep` | This month's work, prepared | "prepare this month" |
| `go-live-plan` | A plan for switching to Twikey | "make a go-live plan" |

## What happens to your data

- **Twikey receives nothing.** The plugin makes no network calls.
- You keep your exports in a folder outside the folder Claude works in. Only the local script opens them.
- Before Claude sees anything, the script replaces names, customer numbers, IBANs, mandate references, invoice
  numbers and payment references with codes such as C001. It drops addresses, email addresses, phone numbers and
  the free text payers write.
- The key that turns the codes back into names stays next to your exports. The report and the work pack with
  names are written there too. Claude gets only their path, not their content.
- **The coded data does go to your AI provider**, like everything Claude reads: amounts, dates, statuses and
  codes. That is Anthropic, or the cloud provider you run Claude through. Coded data is pseudonymized, not
  anonymous, so under the GDPR it is still personal data. Check with whoever handles data protection in your
  company before you run it on real exports.
- A guard stops Claude's tools from naming your export folder. It protects against accidents and is not a lock.
  The real protection is keeping your exports outside the folder Claude works in.

## What it never does

- It never sends mails or collections and never contacts your customers.
- It writes no bank file: no pain.008, no XML, no CSV laid out for a bank tool. You present collections in your
  own bank tool.
- It never changes your exports.
- It gives no verdict on whether Twikey fits your company.

## What you need

- **Claude Code 2.1.139 or later**: Anthropic's AI assistant that runs in a terminal on your own computer, on
  macOS or Linux. It needs a paid Claude plan or an Anthropic API account. Not claude.ai, Claude Code on the web
  or Cowork: there your files would be uploaded before the script could code them. Windows is not supported.
- **Python 3.8 or later**, available as `python3`.
- **Your exports**. The more you give, the more X-ray checks:

| Export | Formats |
|---|---|
| Open invoices or invoice history | CSV with column names in English, Dutch or French |
| Bank statement | camt.053 (ISO 20022 XML) or CSV |
| Returns and refunds | camt.054, or the returns inside camt.053 |
| Rejected collections | pain.002, or a failed-collections CSV |
| Mandate list | CSV |

CODA, MT940, Excel and PDF files are not supported. If your bank gives you CODA, ask it for camt.053 or a CSV
export instead.

## Install

The plugin is in Twikey's public repository on GitHub:
https://github.com/twikey/twikey-aiskills-paymentprocessanalysis. Its marketplace is called `twikey-xray`. In a
terminal, add it as a marketplace, then install the plugin:

```
claude plugin marketplace add twikey/twikey-aiskills-paymentprocessanalysis
claude plugin install twikey-payment-xray@twikey-xray
```

Or download the repository as a ZIP from that GitHub page and unzip it. It unzips to a folder called
`twikey-aiskills-paymentprocessanalysis-main`. Open a terminal in the folder that holds it and run:

```
claude plugin marketplace add ./twikey-aiskills-paymentprocessanalysis-main
claude plugin install twikey-payment-xray@twikey-xray
```

To try the plugin for one session without installing it, start Claude Code with the plugin's folder:

```
claude --plugin-dir ./twikey-aiskills-paymentprocessanalysis-main/plugins/twikey-payment-xray
```

## Get started

1. Make a new, empty folder, for example `~/payment-xray`, and start Claude Code in it.
2. Say **"try the payment x-ray demo"** to see a full run on the fictional company.
3. For your own data, save your exports in a folder outside the folder you start Claude in, for example
   `~/Documents/payment-exports`. Then say **"set up the payment x-ray"**, **"run the x-ray"** and
   **"prepare this month"**.
4. When you are done, delete the `twikey-xray-workspace` folder, and the key, the report and the work pack in
   your export folder.

If a file has a layout the script does not know, it stops and asks you which column is which. It shows each
column by position with the shape of its values ("date", "amount"), never the values themselves.

## Questions

**Is it free?** The plugin is free and open source under the MIT license. Claude Code itself needs your own
Claude plan or API account.

**Do I need to be a Twikey customer?** No. X-ray works on the exports from your own accounting software and bank.

**Does it work with my bank?** It reads the standard ISO 20022 files (camt.053, camt.054, pain.002) and CSV files
with column names in English, Dutch or French. Its CSV reader was tested on the demo layouts, so a CSV layout it
has not seen may need you to say which column is which.

**Which languages?** The scan, the report and the mail drafts are in English, Dutch or French.

**Does it work outside Belgium?** The reason codes and the 36-month rule are the same across SEPA. Payment
matching uses the Belgian structured communication. Other references, such as the RF creditor reference, are
shown but not checked.

**Does it mention Twikey?** Yes, in the scan and the report, never in the mail drafts. Where a finding has a
matching line on twikey.com, the scan quotes it with its page and, where twikey.com names one, the Twikey package it is in. The report ends
with a link to ask Twikey for a demo.

**Can I read what it does?** Yes. Everything is in this repository, and the full documentation is in
[plugins/twikey-payment-xray/README.md](plugins/twikey-payment-xray/README.md): every command, source and limit.

## About Twikey

X-ray prepares this month's work once, from the exports you give it. Twikey describes its follow-up of failed
payments on twikey.com: "This allows us to take immediate action, including customer notifications, reattempting
collections for insufficient funds, initiating payments through alternative methods, or seeking renewed consent
for expired cards or mandates." In the packages: "Transaction failure management" in Professional, "Advanced
failure management" in Premium. ([Follow-up payments](https://www.twikey.com/product/follow-up-payments.html))

[Ask Twikey for a demo](https://www.twikey.com/demo.html?utm_source=github&utm_medium=readme&utm_campaign=payment-xray)

## License

MIT, see `LICENSE`. Twikey Payment X-ray 0.2.1, made by Twikey.
