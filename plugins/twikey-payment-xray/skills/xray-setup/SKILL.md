---
name: xray-setup
description: Sets up Twikey Payment X-ray, a read-only check of where a company's payment process leaks. Shows the data notice, creates the workspace, points it at a folder of raw exports outside the working folder (or loads the fictional demo company), and reads the exports into a coded ledger. Use when the user says "set up the payment x-ray", "x-ray my payments", "try the demo", "load demo data", "analyze my bank exports", "where does my payment process leak", "waar lekt mijn betaalproces", "zet de payment x-ray op", "où est-ce que je perds de l'argent sur mes paiements", "analyse mes exports bancaires", or when another x-ray skill finds no workspace.
---

# Payment X-ray setup

The X-ray works on a company's own exports and never sends, collects or changes anything. Only the script
`twikey_xray.py` opens the raw exports. You, Claude, work only with the coded workspace and the script output.

## Rules for every X-ray skill

- Never open, read, search, list, copy or move anything in the raw export folder, and never touch the key file
  `twikey-xray-key.json`. A plugin guard blocks most attempts. If a tool call is blocked, do not look for another
  way in. The guard prevents accidental reads. It is not a lock, so the rule is yours to keep.
- Run the script exactly as the skills write it: `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py"
  --home twikey-xray-workspace --lang <en|nl|fr> <command> ...`, with no pipes, redirects, `cd` or other commands
  around it. In this folder the X-ray guard lets the shell run only X-ray's own commands. Read the files in
  `twikey-xray-workspace/` with the Read tool.
- Run the script with `--json` when you analyze further. Copy numbers exactly. Do not recompute them. Write
  amounts the way the script prints them in text mode: the euro sign first, then the number written 41,417.50 and
  22.6% in English, 41.417,50 and 22,6% in Dutch and French.
- The script prints only counts, amounts, dates, file numbers ("file 2"), known column names, the shape of a
  column's values and codes (C001 customer, A001 account, M001 mandate, I0001 invoice, R0001 payment reference).
  Talk about customers by code. The names and numbers come back only in the final report.
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
   If `start_problem` is set, stop and tell the user exactly that sentence. On Windows it reads "macOS and Linux.
   Windows is not supported yet." When Claude was started in the home folder or in a folder that holds the
   exports, the user starts Claude again in a new, empty folder and asks again there.
2. **Show the data notice** and ask the user to confirm before you go on:
   - Twikey receives nothing. The plugin makes no network calls.
   - The exports stay in their own folder. A script replaces names, customer numbers, IBANs, mandate
     references, invoice numbers, payment references and file names with codes before Claude reads anything.
     Claude sees amounts, dates, counts, statuses, Core or B2B, the currency, SEPA reason codes and the codes. The
     key that turns codes back into names and numbers stays next to the exports.
   - Coded data (amounts and dates per customer code) does go to the user's AI provider, like everything Claude
     reads.
   - Supported only in Claude Code on the user's own computer, on macOS or Linux, not in claude.ai, Claude Code on
     the web or Cowork. If the user is in one of those, stop and say so.
3. **Demo or own data.** Use `--lang en`, `--lang nl` or `--lang fr` for the user's language: the workspace then
   keeps it, and the Twikey lines, reason-code texts, dates and amounts come in that language.
   - Demo: `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en demo --json`.
     It copies the exports of a fictional Belgian wholesaler to `~/.twikey-xray/demo-raw` and reads them.
   - Own data: ask for a folder **outside** the current working folder, for example `~/Documents/payment-exports`.
     The user saves the exports there with their own file manager, not through you. Ask for exports as far back
     as the user can go, at least 12 months: the longer the period, the more the X-ray can show. The bank files
     are enough to start: return and reject files (camt.054, pain.002 or a failed-collections CSV) and camt.053
     bank statements give the failed collections, new attempts and mail drafts. A camt.053 also gives the failure
     rate per collection day. A CSV bank statement is used for the payment matching. The mandate list
     (CSV) adds the mandate checks. Open invoices or invoice history with a status, paid date or open amount (CSV)
     add the payment matching and payment terms. Tell the user that the invoice export is optional.
     Then run
     `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en init --raw "<folder>"`
     and `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace intake --json`.
     If `init` refuses, give the user its message as it is.
4. **When intake stops** (exit code 2, `"status": "blocked"`): nothing was written. Files are numbered in name
   order ("file 2"), the order the user's file manager shows. For each file, show the reason and its `columns`:
   position, the header when it is a known column name (otherwise "header not shown"), and the shape of the
   values. Ask the user which column holds which field (the output lists the fields). Then rerun intake with one
   `--map` followed by all the column maps, for example `--map "2:#1=invoice_number" "2:#3=amount"`.
   `<file number>:#<position>=<field>` names a column, `<file number>:@kind=<kind>` names the kind of export. To
   leave files out, put their numbers after one `--skip`. An invoice export needs a status, a paid date or an open
   amount, otherwise X-ray cannot tell paid invoices from open ones. A bank export whose money-in and money-out words are
   unknown stops too. CODA and MT940 are not supported yet: ask the user to export camt.053 or CSV instead. Never
   open the file to look for yourself.
5. **Show what was read** in three to five lines: files read, columns dropped, records in the ledger with each
   source's own period, assumptions the script made (such as the date order). Then offer the scan (the
   **xray-scan** skill).

## Notes

- The workspace (`twikey-xray-workspace/`) holds `config.json`, `store.json` (invoices), `mandates.json`,
  `collections.json`, `bank.json` and `intake.json`. All coded.
- `status` shows what the workspace holds. `--as-of YYYY-MM-DD` measures against another date (the demo uses
  October 31, 2026).
- The guard is a safety net against accidental reads, not a lock. The user can switch it off by disabling the
  plugin.
