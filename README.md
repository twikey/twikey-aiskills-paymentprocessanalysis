# Twikey Payment X-ray

A free plugin for Claude Code that reads your camt.053 bank statements. It shows which of your direct debits
failed and why, counts the manual work that follows, and prepares this month's work: the collections worth a new
attempt, with a suggested collection day, and one mail draft per customer. It runs on your own computer. It sends
no mails and no collections, and Twikey receives nothing.

Made by Twikey for companies that get paid by SEPA (Single Euro Payments Area) Direct Debit.

## Why we made this

When a direct debit fails, someone looks up the bank's reason code, mails the customer, presents the collection
again in the bank tool and checks whether it came through. That work is spread over several people and several
months, so the total is hard to see. Your camt.053 bank statements already hold every collection and every return,
with its reason code. X-ray counts the work from them.

## What to export

Your camt.053 bank statements for the account your direct debits are paid into. Export as far back as your bank
allows, at least 12 months: the more months, the more collections each day's failure rate rests on. Save them in one
folder outside the folder you start Claude in. A file in that folder that is not a camt.053 bank statement is
skipped.

## What you get

- **Failed collections** by bank reason code (MS03, AM04, MD06 and the others), in plain language and in euros,
  split by what each one needs next: a new attempt, a new mandate or a conversation with the customer. Plus the
  customers whose collections failed more than once.
- **The failure rate per collection day** of the month, from the collections and returns on your statements.
- **Incoming payments to book by hand**: transfers without a valid Belgian structured communication.
- **The manual work, counted**: how many items your statements hold, times the steps one item takes by hand.
- **This month's work, prepared**: the collections worth a new attempt, with a suggested day, and one mail draft
  per customer in English, Dutch or French. Drafts only, for you to check and send.
- **A report** with the names put back, written on your computer, and on request a plan for switching to Twikey.

## What the demo shows

Say "try the payment x-ray demo" and X-ray reads twelve monthly camt.053 bank statements of a fictional Belgian
wholesaler, November 2025 to October 2026. Every name and IBAN in them is made up.

```
Failed collections                 17, €8,508.50 (November 5, 2025 to October 5, 2026)
Most common reason code            MS03, reason not specified: 7, €3,378.50
Failure rate on the 5th            20.2% (17 of 84 collections)
Failure rate on the 26th           0.0% (0 of 84 collections)
Incoming payments to book by hand  77 of 291, €95,713.00
Manual work on the statements      94 items, 298 steps
This month                         2 collections worth a new attempt, on the 26th, and 4 mail drafts
```

A Dutch draft from the demo. In the work pack the customer's name stands where this shows C003. The date is the
suggested collection day, so it moves with the day you run the demo.

```
Subject: Nieuwe domiciliëring van €475,50 op 26 november 2026

Beste C003,

We konden het volgende niet innen via domiciliëring:
- €475,50, domiciliëring van 5 oktober 2026

We bieden de domiciliëring van €475,50 opnieuw aan op 26 november 2026.
Wil je ervoor zorgen dat er die dag voldoende saldo op je rekening staat?

Bedankt,
[naam van je bedrijf]
```

## What is in this download

```
.claude-plugin/marketplace.json    Tells Claude Code which plugin this repository holds
plugins/twikey-payment-xray/
  skills/                          Seven skills: the instructions Claude follows for each task
  scripts/                         The Python program that reads your camt.053 statements, codes them, does
                                   every count and runs the guard
  hooks/                           Switches on the guard before every tool call Claude makes
  data/                            Reason codes, checklists and mail templates in English, Dutch and French,
                                   plus every line about Twikey the plugin may quote, with its source page
  demo/                            The camt.053 bank statements of the fictional company
  tests/                           The automated tests
  README.md                        The full documentation
LICENSE                            MIT
```

The program uses the Python standard library only and makes no network calls.

You do not need to remember the skill names. Ask in your own words:

| Skill | What it does | Say, for example |
|---|---|---|
| `xray-setup` | Shows the data notice, creates the workspace and reads your camt.053 statements | "set up the payment x-ray" |
| `xray-scan` | Runs the full scan, failed collections first | "run the x-ray" |
| `failure-decoder` | Failed collections by reason code, and the failure rate per collection day | "why did these collections fail?" |
| `unmatched-payments` | Incoming payments to book by hand | "which payments do we book by hand?" |
| `manual-steps` | The manual work, counted | "how much manual work is in my statements?" |
| `month-prep` | This month's work, prepared | "prepare this month" |
| `go-live-plan` | A plan for switching to Twikey | "make a go-live plan" |

## What happens to your data

- **Twikey receives nothing.** The plugin makes no network calls.
- You keep your camt.053 statements in a folder outside the folder Claude works in. Only the local script opens
  them.
- Before Claude sees anything, the script replaces names, IBANs, mandate references and payment references with
  codes such as C001. It drops addresses and the free text payers write.
- The key that turns the codes back into names stays next to your statements. The report and the work pack with
  names are written there too. Claude gets only their path, not their content.
- **The coded data does go to your AI provider**, like everything Claude reads: amounts, dates, reason codes and
  codes. That is Anthropic, or the cloud provider you run Claude through. Coded data is pseudonymized, not
  anonymous, so under the GDPR it is still personal data. Check with whoever handles data protection in your
  company before you run it on real statements.
- A guard stops Claude's tools from naming your statement folder. It protects against accidents and is not a lock.
  The real protection is keeping your statements outside the folder Claude works in.

## What it never does

- It never sends mails or collections and never contacts your customers.
- It writes no bank file. You present collections in your own bank tool.
- It never changes your statements.
- It gives no verdict on whether Twikey fits your company.

## What you need

- **Claude Code 2.1.139 or later**: Anthropic's AI assistant that runs in a terminal on your own computer, on
  macOS or Linux. It needs a paid Claude plan or an Anthropic API account. Not claude.ai, Claude Code on the web
  or Cowork: there your files would be uploaded before the script could code them. Windows is not supported.
- **Python 3.8 or later**, available as `python3`.
- **Your camt.053 bank statements**, at least 12 months.

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
3. For your own data, save your camt.053 statements in a folder outside the folder you start Claude in, for
   example `~/Documents/payment-exports`. Then say **"set up the payment x-ray"**, **"run the x-ray"** and
   **"prepare this month"**.
4. When you are done, delete the `twikey-xray-workspace` folder, and the key, the report and the work pack in your
   statement folder.

## Questions

**Is it free?** The plugin is free and open source under the MIT license. Claude Code itself needs your own
Claude plan or API account.

**Do I need to be a Twikey customer?** No. X-ray works on your own camt.053 bank statements.

**Does it work with my bank?** It reads camt.053 bank statements, versions .001.02 to .001.13. The failure rate
per collection day needs each collection on the statement: when your bank books a direct debit batch as one line
without the collections in it, X-ray counts the failed collections but cannot compute that rate.

**Which languages?** The scan, the report and the mail drafts are in English, Dutch or French.

**Does it work outside Belgium?** The reason codes are the same across SEPA. The structured communication check
is the Belgian one. Other references, such as the RF creditor reference, are counted apart and not checked.

**Does it mention Twikey?** Yes, in the scan and the report, never in the mail drafts. Where a finding has a
matching line on twikey.com, the scan quotes it with its page and, where twikey.com names one, the Twikey package
it is in. The report ends with a link to ask Twikey for a demo.

**Can I read what it does?** Yes. Everything is in this repository, and the full documentation is in
[plugins/twikey-payment-xray/README.md](plugins/twikey-payment-xray/README.md): every command, source and limit.

## About Twikey

X-ray prepares this month's work once, from the statements you give it. Twikey describes its follow-up of failed
payments on twikey.com: "This allows us to take immediate action, including customer notifications, reattempting
collections for insufficient funds, initiating payments through alternative methods, or seeking renewed consent
for expired cards or mandates." In the packages: "Transaction failure management" in Professional, "Advanced
failure management" in Premium. ([Follow-up payments](https://www.twikey.com/product/follow-up-payments.html))

[Ask Twikey for a demo](https://www.twikey.com/demo.html?utm_source=github&utm_medium=readme&utm_campaign=payment-xray)

## License

MIT, see `LICENSE`. Twikey Payment X-ray 0.3.0, made by Twikey.
