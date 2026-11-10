# Twikey Payment X-ray

A free Claude Code plugin, made by Twikey, for companies that get paid by direct debit. It reads your camt.053 bank
statements on your own computer.

> **What it does for you.** It shows which direct debits failed and why, from the returns and refunds on your
> camt.053 bank statements, with the failure rate per collection day. It finds the incoming payments someone books
> by hand and counts the manual steps each finding asks for. Then it prepares this month's work: the collections
> worth a new attempt, with a suggested collection day, and one mail draft per customer.
>
> **What it needs.** Claude Code 2.1.139 or later on your own computer (macOS or Linux, not claude.ai, Claude Code
> on the web or Cowork), Python 3.8 or later, and at least 12 months of camt.053 bank statements.
>
> **What it never does.** It never sends anything: no mails, no collections, no bank files. It does not contact
> your customers and does not change your statements. Twikey receives nothing. Claude works with codes instead of
> names and numbers, and that coded data goes to your AI provider, like everything Claude reads.

## Before you start

- Claude Code 2.1.139 or later, on your own computer, on macOS or Linux.
- Python 3.8 or later, available as `python3`. On macOS, open Terminal and run `python3 --version`. If macOS
  offers to install the developer tools, accept, or install Python from python.org, then run `python3 --version`
  again. Most Linux distributions ship `python3`.
- A new, empty folder to start Claude in, for example `~/payment-xray`.
- Your camt.053 bank statements, see "What to export".

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

Then start Claude Code in your new, empty folder. The plugin has seven skills. You do not need to remember their
names: ask in your own words.

## Try the demo

Say **"try the payment x-ray demo"**. It loads twelve monthly camt.053 bank statements of a fictional Belgian
wholesaler (November 2025 to October 2026) and runs the scan. On them, 14 customers pay by direct debit and 26
payers pay by transfer. Every name and IBAN in the demo is made up.

## What to export

Your camt.053 bank statements for the account your direct debits are paid into, as far back as your bank allows
and at least 12 months. X-ray reads versions .001.02 to .001.13. From them it takes:

- the direct debits you collected, one by one, with their mandate reference,
- the returns and refunds of those direct debits, with the bank's reason code,
- the incoming transfers, with their structured communication.

Payments out are skipped and counted. A file that is not a camt.053 bank statement is skipped too: intake says
"file 3 is not a camt.053 bank statement, skipped." and goes on with the others.

## Use your own statements

1. Make a folder for the statements outside the folder you start Claude in, for example
   `~/Documents/payment-exports`.
2. Save your camt.053 statements there with your own file manager.
3. In Claude Code, started in a new, empty folder, say **"set up the payment x-ray"** and give the statement
   folder. Claude shows the data notice first.
4. Say **"run the x-ray"**. Claude writes the findings with codes, including the manual work, then offers the
   report with the names put back.
5. Say **"prepare this month"** for this month's work, prepared.
6. Say **"make a go-live plan"** for five questions and a plan for switching to Twikey.

## What the scan shows

The scan starts with the collections that failed.

- **Failed collections** by bank reason code (MS03, AM04, MD01, MS02, MD06, AC04 and the others), in plain
  language and in euros: what is worth a new attempt, what needs a new mandate, what needs a conversation with the
  customer, and what to ask your bank. A return is matched to the collection it returns by its end-to-end
  reference, so it counts on the collection day.
- **The failure rate per collection day** of the month: failed collections against collections presented. A new
  presentation of a failed collection is left out, and a run moved by a weekend or bank holiday counts under its
  usual day.
- **Incoming payments to book by hand**: transfers without a Belgian structured communication, or with one whose
  check digits are wrong. Other references, such as the RF creditor reference, are counted apart.
- **Manual work**: per finding, how many items your statements hold and the manual steps one item asks for when
  it is done by hand, with the checklist. Biggest first.

Where a finding has a matching line on twikey.com, it ends with that line, quoted with its page. Some Dutch lines
are translated from the English page, not quoted, and are marked "(vertaald uit het Engels)". The report ends with
one link to ask Twikey for a demo.

## This month's work

Say **"prepare this month"** and the script writes two files:

| File | What it holds |
|---|---|
| `month.json` in `twikey-xray-workspace/` | The prepared work with codes only. This is the file Claude reads. |
| `twikey-xray-month-<date>.md` in your statement folder | The work pack: the same work with names and mandate references put back on your computer. Claude gets only its path and never opens it. |

The work pack has two parts:

1. **Collections worth a new attempt**: failed in the last 90 days with a reason worth a new attempt and not paid
   since, with the reason in plain words. A collection presented again and failed again is one item, with the
   number of attempts and the date of the last one. A failure is left out when a later collection on the same
   mandate brought the money in, or a later transfer from that customer covers the amount. With a suggested
   collection day: the day of the month with the lowest failure rate in your own statements. A day counts only
   with 20 or more collections presented over two months or more, and a day is suggested only when two or more
   days count and the best one fails less often than all your collections together. The suggested date is at
   least 14 days from today, the usual SEPA pre-notification period: check what your mandate terms say. With too
   little history, or no day that fails less often, no day is suggested and the drafts say "[date of the new
   collection]" for you to fill in.
2. **Customer mail drafts**: one per customer, never two, with all of that customer's open items from the last 90
   days, by reason: how they would like to pay, a new mandate is needed, their bank has to register the B2B
   mandate, or a new collection is coming. In English, Dutch or French. The drafts do not mention Twikey. Your
   statements show what came in at the bank, not what your books say, so check that each amount is still owed
   before you send a draft.

Every mail is a draft for you to check and send yourself. X-ray writes no bank file: you present the collections
in your own bank tool. Claude prepares the work once, from the statements you give it.

## Commands

The skills run one script, by its full path. Claude Code fills in `${CLAUDE_PLUGIN_ROOT}` with the plugin's
folder:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace [--lang en|nl|fr] <command> [--json]
  init --raw FOLDER            set the statement folder (outside the folder Claude works in)
  demo [--raw FOLDER]          load the fictional demo company
  intake                       read the camt.053 statements into the coded ledger
  decode                       failed collections by reason code, failure rate per collection day
  payments                     incoming payments, and the ones to book by hand
  steps                        the manual steps per finding, counted
  month [--mail-lang en|nl|fr] [--since-days N]
                               this month's work, prepared: month.json and the work pack
  golive [--tool NAME]         facts for the go-live plan
  report [--findings FILE]     the report with names, written next to your statements
  status                       what the workspace holds
```

In the X-ray folder, Claude can run the script only in this form, with the full path that reaches the plugin's
own script. A relative path is refused there. To run it yourself in a terminal, put the full path of the plugin's
folder in place of `${CLAUDE_PLUGIN_ROOT}`.

Every command prints counts, amounts, dates and codes only. `report` prints only the path of the report, and
`month` only the path of the work pack (with `--json`, the coded work as well). `--lang` works before or after
the command. `-B` keeps Python from writing `.pyc` files next to the plugin.

## Sources

- **Reason codes**: `data/rcodes_{en,nl,fr}.json` hold the texts of Twikey's 25 reason codes, as on
  https://www.twikey.com/product/r-codes. The plugin also knows the SEPA Direct Debit reason codes of the EPC
  guidance on reason codes for SDD R-transactions (EPC173-14). The scan lists the codes not on Twikey's
  reason-code page, with the EPC reason where the EPC list has one. A code on neither list is unknown: ask your
  bank.
- **Checklists and mail drafts**: `data/manual_steps.json` holds the manual steps per item type and
  `data/mail_templates.json` the mail drafts, in English, Dutch and French, as plain text you can review.
- **Twikey lines**: `data/twikey-claims.md` holds every line the plugin may print about Twikey, each with its page
  on twikey.com, checked on November 3, 2026. French lines are quoted from the French pages. Dutch lines are
  quoted from the Belgian Dutch pages, except four where that page addresses the reader with "u": those four are
  translated from the English page, are marked "(vertaald uit het Engels)" and link the English page. A line with
  no text in a language is printed in English and marked as English.

## Limits

- Customers are linked across statements by IBAN, or by the exact name after removing case, accents and legal
  forms. Two customers with the same name count as one.
- The failure rate per collection day needs each collection on the statement. When your bank books a direct debit
  batch as one line without the collections in it, intake counts that line as "direct debit batch without
  details": the failed collections are still counted, the rate per day is not.
- A return without the end-to-end reference of a collection on your statements keeps its booking date, and does
  not count for the rate per day.
- Only the Belgian structured communication is checked. Other references are counted apart as "other reference
  (not checked)".
- The manual steps are counted from your statements. The checklists are the usual steps when the work is done by
  hand, and your own process may have more or fewer. The plugin gives no verdict on whether Twikey fits your
  company.
- The suggested collection day comes from your own failure rates, nothing else.
- The guard is a guard against accidents, not a lock. See "How your data stays on your computer".

## How your data stays on your computer

- **Twikey receives nothing.** The plugin makes no network calls.
- You keep your statements in a folder **outside** the folder Claude works in. Only a local script opens them. It
  keeps a fixed list of fields, drops addresses and the free text payers write, and replaces names, IBANs,
  mandate references and payment references (structured communications and the end-to-end references of
  collections) with codes such as C001 and R0001. It checks a structured communication's check digits before it
  codes it. Files are shown as "file 1", "file 2", never by name. A reason field that holds anything other than a
  known SEPA reason code is shown as "proprietary reason (not shown)".
- **What Claude sees:** amounts, dates, counts, Core or B2B, the currency, SEPA reason codes, file numbers and the
  codes. Nothing else from your statements.
- The key that turns codes back into names and numbers stays in your statement folder. The final report with
  names and numbers is written there too, on your computer.
- **Coded data does go to your AI provider.** Claude reads amounts and dates per customer code, like everything
  Claude reads in a session. Coded data is pseudonymized, not anonymous.
- **Supported only in Claude Code on your own computer.** Not in claude.ai, not in Claude Code on the web, not in
  Cowork: there your files would be uploaded before the script could code them.

### What stays on your computer

| Where | What |
|---|---|
| `twikey-xray-workspace/` in your project | `config.json` and the coded ledger: `collections.json`, `bank.json`, `intake.json`, plus `findings.md`, `month.json` and `go-live-plan.md`. Codes, amounts, dates and the other values listed under "What Claude sees". `config.json` also holds the path of your statement folder. |
| Your statement folder | Your camt.053 statements, `twikey-xray-key.json` (the key), `twikey-xray-report-<date>.md` (the report with names) and `twikey-xray-month-<date>.md` (the work pack with names) |
| `~/.twikey-xray/raw-folders.json` | The list of statement folders the guard protects |

Delete `twikey-xray-workspace/`, the key, the report and the work packs when you are done.

### The guard

The plugin adds a guard (a `PreToolUse` hook) that runs before every Claude tool call, MCP tools included. It
works in two zones.

**In the X-ray folder** (the new, empty folder you started Claude in for the X-ray), Claude can only run X-ray's
commands in the shell: the plugin's own script, in its exact form (see "Commands"), with no pipes, redirects or
other commands. Every other shell command is refused, and Claude reads the results with its Read tool.

**Everywhere else**, the guard stops Claude's tools from naming the statement folder, a folder above it or a
wildcard over it, including after a `cd` in the same command. The key file is refused wherever it is. Only
X-ray's own script may name the statement folder, as the value of `--raw` when it sets up the X-ray.

It is a guard against accidents, not a lock. A command or script built to reach the folder another way can still
get past it, and so can a determined user. Run X-ray from its own folder, where Claude can only run X-ray's
commands. An MCP tool that gets the folder and the file name as separate fields is not caught, in either zone.
You can switch the guard off by disabling the plugin. The real protection is keeping the statements outside the
folder Claude works in, and starting Claude in a new, empty folder: setup stops when Claude was started in your
home folder or in a folder above your statements.

When Python is missing, the guard does not start and Claude Code goes on without it. Without Python the plugin
cannot read any statement either, so there is nothing to protect. The guard needs Claude Code 2.1.139 or later
(the hook uses the `args` form introduced in that version).

## For developers

```
cd plugins/twikey-payment-xray
python3 -B -m unittest         # all tests
python3 -B tests/make_demo.py  # rebuild the demo statements from their spec
```

Python standard library only. `tests/expected_demo.json` holds the demo results, written from the spec in
`tests/make_demo.py`.

## License

MIT, see `LICENSE`.

Twikey Payment X-ray 0.3.0, made by Twikey.
