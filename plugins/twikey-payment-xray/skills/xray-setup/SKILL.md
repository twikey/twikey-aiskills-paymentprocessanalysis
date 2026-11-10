---
name: xray-setup
description: Sets up Twikey Payment X-ray, a read-only check of a company's camt.053 bank statements that shows where its direct debits fail. Shows the data notice, creates the workspace, points it at a folder of camt.053 statements outside the working folder (or loads the fictional demo company), and reads the statements into a coded ledger. Use when the user says "set up the payment x-ray", "x-ray my payments", "try the demo", "load demo data", "analyze my bank statements", "where do my direct debits fail", "waar lekt mijn betaalproces", "zet de payment x-ray op", "où est-ce que je perds de l'argent sur mes paiements", "analyse mes relevés bancaires", or when another x-ray skill finds no workspace.
---

# Payment X-ray setup

The X-ray works on a company's own camt.053 bank statements and never sends, collects or changes anything. Only
the script `twikey_xray.py` opens the statements. You, Claude, work only with the coded workspace and the script
output.

## Rules for every X-ray skill

- Never open, read, search, list, copy or move anything in the statement folder, and never touch the key file
  `twikey-xray-key.json`. A plugin guard blocks most attempts. If a tool call is blocked, do not look for another
  way in. The guard prevents accidental reads. It is not a lock, so the rule is yours to keep.
- Run the script exactly as the skills write it: `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py"
  --home twikey-xray-workspace --lang <en|nl|fr> <command> ...`, with no pipes, redirects, `cd` or other commands
  around it. In this folder the X-ray guard lets the shell run only X-ray's own commands. Read the files in
  `twikey-xray-workspace/` with the Read tool.
- Run the script with `--json` when you analyze further. Copy numbers exactly. Do not recompute them. Write
  amounts the way the script prints them in text mode: the euro sign first, then the number written 8,508.50 and
  20.2% in English, 8.508,50 and 20,2% in Dutch and French.
- The script prints only counts, amounts, dates, file numbers ("file 2") and codes (C001 customer or payer, A001
  account, M001 mandate, R0001 payment reference). Talk about customers by code. The names come back only in the
  final report.
- Answer in the user's language. Write dates out in that language (October 31, 2026, 31 oktober 2026,
  31 octobre 2026). Write the numbers one to ten in words in sentences, larger numbers in digits.
- Twikey lines come from the script output only, exactly as given: they are already in the workspace language,
  quoted from twikey.com. Keep a line's `mark` when it has one, as the text output prints it ("Twikey (vertaald
  uit het Engels):"): "(vertaald uit het Engels)" marks a translation of the English page, not a quote, linked to
  that English page. "(Engels)" or "(anglais)" marks a line with no text in that language, shown in English.
  Never translate or reword a Twikey line yourself.
- Call it automatic payments, never by a brand name.

## Steps

1. **Check where Claude runs.** Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace status --json`.
   If `start_problem` is set, stop and tell the user exactly that sentence. On Windows it reads "X-ray runs on macOS
   and Linux. Windows is not supported." When Claude was started in the home folder or in a folder that holds the
   statements, the user starts Claude again in a new, empty folder and asks again there.
2. **Show the data notice** and ask the user to confirm before you go on:
   - Twikey receives nothing. The plugin makes no network calls.
   - The statements stay in their own folder. A script replaces names, IBANs, mandate references, payment
     references and file names with codes before Claude reads anything. Claude sees amounts, dates, counts, Core or
     B2B, the currency, SEPA reason codes and the codes. The key that turns codes back into names stays next to the
     statements.
   - Coded data (amounts and dates per customer code) does go to the user's AI provider, like everything Claude
     reads.
   - Supported only in Claude Code on the user's own computer, on macOS or Linux, not in claude.ai, Claude Code on
     the web or Cowork. If the user is in one of those, stop and say so.
3. **Demo or own data.** Use `--lang en`, `--lang nl` or `--lang fr` for the user's language: the workspace then
   keeps it, and the Twikey lines, reason-code texts, dates and amounts come in that language.
   - Demo: `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en demo --json`.
     It copies twelve monthly camt.053 statements of a fictional Belgian wholesaler to its own demo folder and
     reads them.
   - Own data: ask for a folder **outside** the current working folder, for example `~/Documents/payment-exports`.
     The user saves the statements there with their own file manager, not through you. Ask for the camt.053 bank
     statements of the account the direct debits are paid into, as far back as the bank allows and at least 12
     months: the more months, the more collections each day's failure rate rests on. Then run
     `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en init --raw "<folder>"`
     and `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace intake --json`.
     If `init` or `intake` refuses, give the user its message as it is.
4. **Skipped files.** A file that is not a camt.053 bank statement is skipped and listed in `skipped_files` by its
   number, with the reason (`not_camt053`, `doctype`, `too_large` or `unreadable`). Tell the user which file
   numbers were skipped. Files are numbered in name order, the order the user's file manager shows. Never open a
   file to look for yourself.
5. **Show what was read** in three to five lines: the statements read, the direct debit customers and payers, and
   each kind of record with its own period (incoming payments, direct debit collections, failed collections).
   When a statement shows "direct debit batch without details", say that the bank booked a batch as one line, so
   the failure rate per collection day cannot use it. Then offer the scan (the **xray-scan** skill).

## Notes

- The workspace (`twikey-xray-workspace/`) holds `config.json`, `collections.json`, `bank.json` and
  `intake.json`. All coded.
- `status` shows what the workspace holds. `--as-of YYYY-MM-DD` measures against another date (the demo uses
  October 31, 2026).
- The guard is a safety net against accidental reads, not a lock. The user can switch it off by disabling the
  plugin.
