# Twikey Payment X-ray

macOS and Linux. Windows is not supported yet.

A free Claude Code plugin, made by Twikey, for companies that collect by direct debit. It reads your own exports
on your own computer.

> **What it does for you.** It shows where your payment process leaks, in euros, counted from your own exports:
> collections that failed and why, mandates expired under the 36-month rule, payments that match no invoice,
> invoices paid twice or paid but still open in your books, and customers who pay later than agreed. It counts the
> manual steps each finding asks for. Then it prepares this month's work: the collections worth a new attempt with
> a suggested collection day, one mail draft per customer, the mandates to renew and match suggestions for your
> books.
>
> **What it needs.** Claude Code 2.1.139 or later on your own computer (macOS or Linux, not claude.ai, Claude Code
> on the web or Cowork), Python 3.8 or later, and exports from your accounting software and your bank.
>
> **What it never does.** It never sends anything: no mails, no collections, no bank files. It does not contact
> your customers and does not change your exports. Twikey receives nothing. Claude works with codes instead of
> names and numbers, and that coded data goes to your AI provider, like everything Claude reads.

## Before you start

- Claude Code 2.1.139 or later, on your own computer, on macOS or Linux.
- Python 3.8 or later, available as `python3`. On macOS, open Terminal and run `python3 --version`. If macOS
  offers to install the developer tools, accept, or install Python from python.org, then run `python3 --version`
  again. Most Linux distributions ship `python3`.
- A new, empty folder to start Claude in, for example `~/payment-xray`.
- Exports from your accounting software and your bank, see "Exports it reads".

## Install

The plugin is in Twikey's public repository on GitHub:
https://github.com/twikey/twikey-aiskills-paymentprocessanalysis. Its marketplace is called `twikey-xray`. In a
terminal, run:

```
claude plugin marketplace add twikey/twikey-aiskills-paymentprocessanalysis
claude plugin install twikey-payment-xray@twikey-xray
```

Or download the repository as a ZIP from that GitHub page, unzip it, open a terminal in the folder that holds the
unzipped folder, and run:

```
claude plugin marketplace add ./<unzipped folder>
claude plugin install twikey-payment-xray@twikey-xray
```

Then start Claude Code in your new, empty folder. The plugin has nine skills. You do not need to remember their
names: ask in your own words.

## Try the demo

Say **"try the payment x-ray demo"**. It loads the exports of a fictional Belgian wholesaler with 41 fictional
customers and one fictional landlord (November 2025 to October 2026) and runs the scan. Every name, address and
IBAN in the demo is made up.

## Use your own exports

1. Make a folder for the exports outside the folder you start Claude in, for example `~/Documents/payment-exports`.
2. Save your exports there with your own file manager.
3. In Claude Code, started in a new, empty folder, say **"set up the payment x-ray"** and give the export folder.
   Claude shows the data notice first.
4. Say **"run the x-ray"**. Claude writes the findings with codes, including the manual work, then offers the
   report with the names put back.
5. Say **"prepare this month"** for this month's work, prepared.
6. Say **"make a go-live plan"** for five questions and a plan for switching to Twikey.

If a file has a layout the script does not know, it stops. It shows each column by position, with its header only
when the header is a column name it knows, and the shape of its values ("date", "amount", "IBAN-like",
"text, 12 chars"). It never shows a cell. Then it asks you which column is which. Nothing is read until every
file is clear.

## What the scan shows

The scan starts with the collections that failed.

- **Failed collections** by bank reason code (MS03, MD01, MS02, MD06, AC04 and the rest), in plain language:
  what is worth a new attempt, what needs a new mandate, what needs a conversation, and the failure rate per
  collection day.
- **Mandate health**: the mandates to renew, which are the mandates expired under the 36-month rule (no
  collection presented for 36 months, the SEPA rule for Core and B2B) and the ones expiring within 90 days. Apart
  from those: mandates never used and signed more than 36 months ago, missing references, dates or signatures,
  duplicates, account changes, B2B mandates not confirmed at the customer's bank.
- **Unmatched payments**: payments that match no invoice, partial and bundled payments (credit notes netted),
  invoices paid twice, and invoices still open in your books that were already paid. Receipts that are not invoice
  payments are listed apart.
- **Terms against reality**: the agreed term against the days each customer takes to pay, with payer profiles
  (clockwork, pays after failed collections, late but pays, drifting, at risk), aging and DSO (days sales
  outstanding) against each invoice's own term.
- **Manual work**: per finding, how many items your files hold and the manual steps one item asks for when it is
  done by hand, with the checklist. Biggest first. Counted from your files.

When a check needs an export you did not give, the scan says "Not checked" and names the missing export. It never
reports "none" for something it could not check. With failed collections of one kind only (rejections from a
pain.002, or returns from a camt.053 or camt.054 statement), it names the kind it could not count.

Where a finding has a matching line on twikey.com, it ends with that line, quoted with its page. Some Dutch lines
are translated from the English page, not quoted, and are marked "(vertaald uit het Engels)". The report ends with
one link to ask Twikey for a demo.

## This month's work

Say **"prepare this month"** and the script writes two files:

| File | What it holds |
|---|---|
| `month.json` in `twikey-xray-workspace/` | The prepared work with codes only. This is the file Claude reads. |
| `twikey-xray-month-<date>.md` in your export folder | The work pack: the same work with names, amounts and invoice numbers put back on your computer. Claude gets only its path and never opens it. |

The work pack has four parts:

1. **Collections worth a new attempt**: failed in the last 90 days with a reason worth a new attempt and still
   open, with the reason in plain words. Repeated failures on one invoice are one item, with the number of
   attempts and the date of the last one. A failure that was paid since in another way is not here (when your
   books still show that invoice open, it is under the invoices to close in your books), and a part paid since is
   never asked again. With a suggested collection day: the day of the month with the lowest
   failure rate in your own data. A day counts only with 20 or more collections presented over two months or
   more, and a day is suggested only when two or more days count and the best one fails less often than all your
   collections together. The suggested date is at least 14 days from today, the usual SEPA pre-notification
   period: check what your mandate terms say. With too little history, or no day that fails less often, no day is
   suggested and the drafts say "[date of the new collection]" for you to fill in.
2. **Customer mail drafts**: one per customer, never two, with all of that customer's open items from the last 90
   days, by reason: how they would like to pay, a new mandate is needed, their bank has to register the B2B
   mandate, or a new collection is coming. In English, Dutch or French. The drafts do not mention Twikey. Older
   failed collections whose invoice is still open are counted apart, and a collection without a known invoice
   comes with a line asking you to check your books first.
3. **Mandates to renew**: expired under the 36-month rule or expiring within 90 days, customers who are still
   active first. An expired mandate comes with a renewal mail draft. An expiring mandate is still valid and gets
   no mail: for a customer who is still active, the work pack says a collection on it before its expiry date
   keeps it valid.
4. **Match suggestions**: for each payment that matches no invoice, up to three open invoices that could fit, with
   how strong the match is. A suggestion on the amount only is marked: check it before you book. One invoice is
   never suggested on the amount only for two payments. Plus the invoices paid twice, to refund or credit, and the
   paid invoices still open in your books.

A part that needs an export you did not give says "Not checked" and names it. Where an amount is unknown, the
drafts say "[amount]", never zero.

Every mail is a draft, and every draft section starts with a line asking you to check it and send it yourself.
X-ray writes no bank file: no pain.008, no XML, no CSV laid out for a bank tool. You present the collections in
your own bank tool. Claude prepares the work once, from the exports you give it.

## Exports it reads

| Export | Formats |
|---|---|
| Open invoices, invoice history | CSV with a header row in English, Dutch or French, with a status, a paid date or an open amount |
| Bank statement | camt.053 (ISO 20022 XML), CSV |
| Returns and refunds | camt.054, or the returns inside camt.053 (only returns of direct debits you collected) |
| Rejected collections | pain.002 status report on a collection file (pain.008), or a failed-collections CSV |
| Mandate list | CSV |

The CSV reader was tested on the layouts of the demo exports. It recognizes columns by their names in English,
Dutch and French, not by bank. Any other layout, including your bank's own CSV, may need you to say which
column is which: intake asks. Not supported yet: CODA, MT940, Excel and PDF files (export camt.053 or CSV
instead). pain.008 is the file you send to the bank, not a result, so it is not read.

## Commands

The skills run one script, by its full path. Claude Code fills in `${CLAUDE_PLUGIN_ROOT}` with the plugin's
folder:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace [--lang en|nl|fr] <command> [--json]
  init --raw FOLDER            set the export folder (outside the folder Claude works in)
  demo [--raw FOLDER]          load the fictional demo company
  intake [--map N:COLUMN=FIELD ...] [--skip N ...]
                               N is the file number intake shows, COLUMN a header or #position
  decode                       failed collections by reason code
  mandates [--on YYYY-MM-DD]   the 36-month rule and other mandate checks
  match                        bank payments against invoices
  terms                        agreed terms against days to pay
  steps                        the manual steps per finding, counted
  month [--mail-lang en|nl|fr] [--since-days N]
                               this month's work, prepared: month.json and the work pack
  golive [--tool NAME]         facts for the go-live plan
  report [--findings FILE]     the report with names, written next to your exports
  status                       what the workspace holds
```

In the X-ray folder, Claude can run the script only in this form, with the full path that reaches the plugin's
own script. A relative path is refused there. To run it yourself in a terminal, put the full path of the plugin's
folder in place of `${CLAUDE_PLUGIN_ROOT}`.

Every command prints counts, amounts, dates and codes only. `report` prints only the path of the report, and
`month` only the path of the work pack (with `--json`, the coded work as well). `--lang` works before or after
the command. Put all column maps after one `--map`, and all file numbers after one `--skip`. `-B` keeps Python
from writing `.pyc` files next to the plugin.

## Sources

- **Reason codes**: `data/rcodes_{en,nl,fr}.json` hold the texts of Twikey's 25 reason codes, as on
  https://www.twikey.com/product/r-codes. The plugin also knows the SEPA Direct Debit reason codes of the EPC
  guidance on reason codes for SDD R-transactions (EPC173-14). The scan lists the codes not on Twikey's
  reason-code page, with the EPC reason where the EPC list has one. A code on neither list is unknown: ask your
  bank.
- **The 36-month rule**: the EPC SEPA Direct Debit Core and B2B rulebooks, section 4.2.
- **Payment calculations**: standard aging and DSO formulas.
- **Checklists and mail drafts**: `data/manual_steps.json` holds the manual steps per item type and
  `data/mail_templates.json` the mail drafts, in English, Dutch and French, as plain text you can review.
- **Twikey lines**: `data/twikey-claims.md` holds every line the plugin may print about Twikey, each with its page
  on twikey.com, checked on November 3, 2026. French lines are quoted from the French pages. Dutch lines are
  quoted from the Belgian Dutch pages, except six where that page addresses the reader with "u": those six are
  translated from the English page, not quoted, are marked "(vertaald uit het Engels)" and link the English page. A
  line with no text in a language is printed in English and marked as English.

## Limits

- Customers in different files are linked by customer number, by IBAN, or by the exact name after removing case,
  accents and legal forms. Two customers with the same name count as one.
- Matching uses the Belgian structured communication (with its check digits), the amount and the customer. It
  never settles an invoice issued after the payment and never guesses: a payment that fits nothing stays
  unmatched. Other references (the RF creditor reference, the Dutch payment reference) are shown as "other
  reference (not checked)".
- The manual steps are counted from your files. The checklists are the usual steps when the work is done by hand,
  and your own process may have more or fewer. The plugin gives no verdict on whether Twikey fits your company.
- The suggested collection day comes from your own failure rates, nothing else. Match suggestions on the amount
  only can be wrong: check them before you book.
- The guard is a guard against accidents, not a lock. See "How your data stays on your computer".

## How your data stays on your computer

- **Twikey receives nothing.** The plugin makes no network calls.
- You keep your exports in a folder **outside** the folder Claude works in. Only a local script opens them. It
  keeps a fixed list of fields, drops addresses, email addresses, phone numbers and the free text payers write,
  and replaces names, customer numbers, IBANs, mandate references, invoice numbers and payment references
  (structured communications and the end-to-end references of collections) with codes such as C001 and R0001.
  It checks a structured communication's check digits before it codes it. Files are shown as "file 1",
  "file 2", never by name. A reason field that holds anything other than a known SEPA reason code is shown as
  "proprietary reason (not shown)".
- **What Claude sees:** amounts, dates, counts, statuses from a fixed list (such as paid, open, active), Core or
  B2B, the currency, SEPA reason codes, file numbers, the column names the script knows, and the codes. Nothing
  else from your exports.
- The key that turns codes back into names and numbers stays in your export folder. The final report with names
  and numbers is written there too, on your computer.
- **Coded data does go to your AI provider.** Claude reads amounts and dates per customer code, like everything
  Claude reads in a session. Coded data is pseudonymized, not anonymous.
- **Supported only in Claude Code on your own computer.** Not in claude.ai, not in Claude Code on the web, not in
  Cowork: there your files would be uploaded before the script could code them.

### What stays on your computer

| Where | What |
|---|---|
| `twikey-xray-workspace/` in your project | `config.json` and the coded ledger: `store.json`, `mandates.json`, `collections.json`, `bank.json`, `intake.json`, plus `findings.md`, `month.json` and `go-live-plan.md`. Codes, amounts, dates and the other values listed under "What Claude sees". `config.json` also holds the path of your export folder. |
| Your export folder | Your exports, `twikey-xray-key.json` (the key), `twikey-xray-report-<date>.md` (the report with names) and `twikey-xray-month-<date>.md` (the work pack with names) |
| `~/.twikey-xray/raw-folders.json` | The list of export folders the guard protects |

Delete `twikey-xray-workspace/`, the key, the report and the work packs when you are done.

### The guard

The plugin adds a guard (a `PreToolUse` hook) that runs before every Claude tool call, MCP tools included. It
works in two zones.

**In the X-ray folder** (the new, empty folder you started Claude in for the X-ray), Claude can only run X-ray's
commands in the shell: the plugin's own script, in its exact form (see "Commands"), with no pipes, redirects or
other commands. Every other shell command is refused, and Claude reads the results with its Read tool.

**Everywhere else**, the guard stops Claude's tools from naming the export folder, a folder above it or a
wildcard over it, including after a `cd` in the same command. The key file is refused wherever it is. Only
X-ray's own script may name the export folder, as the value of `--raw` when it sets up the X-ray.

It is a guard against accidents, not a lock. A command or script built to reach the folder another way can still
get past it, and so can a determined user. Run X-ray from its own folder, where Claude can only run X-ray's
commands. An MCP tool that gets the folder and the file name as separate fields is not caught, in either zone.
You can switch the guard off by disabling the plugin. The real protection is keeping the exports outside the
folder Claude works in, and starting Claude in a new, empty folder: setup stops when Claude was started in your
home folder or in a folder above your exports.

When Python is missing, the guard does not start and Claude Code goes on without it. Without Python the plugin
cannot read any export either, so there is nothing to protect. The guard needs Claude Code 2.1.139 or later (the
hook uses the `args` form introduced in that version).

## For developers

```
cd plugins/twikey-payment-xray
python3 -B -m unittest         # all tests
python3 -B tests/make_demo.py  # rebuild the demo exports from their spec
```

Python standard library only. `tests/expected_demo.json` holds the demo results, written by hand from the spec in
`tests/make_demo.py`.

## License

MIT, see `LICENSE`.

Twikey Payment X-ray 0.2.1, made by Twikey.
