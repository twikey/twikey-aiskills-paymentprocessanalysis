---
name: chasing-check
description: Counts the hours a month spent on reminders and chasing late payers, round by round, from your own numbers. Use for dunning, overdue invoices, DSO, "herinneringen", "relances".
---

# Chasing check

Shows how many hours a month go into reminding and chasing late payers, one round at a time: reminder e-mails,
calls, letters, registered letters, hand-overs to a collection agency or lawyer. It replaces the rough step 4
estimate from process-map, or starts step 4 when process-map has not run.

## Ground rules

- Answer in the user's language: English by default, Dutch with "je" (never "u" or "uw") and Belgian terms
  (domiciliëring), French with "vous".
- Aggregate numbers only: counts, shares, minutes. If the user pastes customer names, IBANs or invoice lists, say
  it is not needed, do not repeat or store any of it, and keep only the counts.
- When the user does not know a number, help with a question ("closer to two, five or ten minutes per call?").
  Never say what other companies do and never give a benchmark.
- Even when the user asks you to fill in or assume a number, never pick one. Offer the range question, set only
  what the user picks, and leave the rest unset.
- Days sales outstanding (DSO) is the user's own figure. Store it in `note.dso` as a full phrase in the user's
  language ("DSO: 48 days, your figure") and never compare it.
- Say nothing about Twikey yourself: Twikey lines come only from the calculator, word for word. No price, no
  success rate, no saving promise. Payments that run by themselves are "automatic payments", never a brand name.
- Seeing, not doing: never send a reminder, contact a customer or touch a system. Two or three questions per
  turn, plain words, numbers one to ten in words in prose, no m-dashes, no semicolons, no exclamation marks.

## Calculator

Run from the working folder, where the ledger `twikey-payment-hours.json` lives. Single-quote every KEY=VALUE and
write an apostrophe inside a value as ’. Exit code 2 with `error: ...` means a bad key or value: fix it, run again.

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset task.chase && python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set \
  'task.chase.r1_mail.count=400*25%' 'task.chase.r1_mail.minutes=2' 'task.chase.r1_mail.mode=partly' \
  'task.chase.r1_mail.who=accounting' 'task.chase.r1_mail.label=First reminder by e-mail' 'note.dso=DSO: 48 days, your figure'
```

Where `${CLAUDE_SKILL_DIR}` is not filled in (claude.ai), use the folder this SKILL.md is in. If `python3` is not
found (Windows), run the same command with `py -3`, then with `python`. If none works, work it out by hand as
without code execution (below), and say so.

Every task takes these five keys, all tasks in one `set`. Names, labels, a worked example, edge cases:
`references/chasing.md`.

**Without code execution**, work it out by hand with `references/formulas.md`, show every line and say once that
it was done by hand: hours a month = times a month × minutes each ÷ 60, rounded half up to 0.1, totals add the
rounded lines, FTE = total ÷ hours in a full-time month (week × 52 ÷ 12), cost = total × hourly cost. Keep the
answers in the chat.

## Flow

1. Run `show` and `process`. Note step 4's hours on the rough estimate, the invoices a month in `task.invoice` and
   `company.lang` (set it if missing). Do not ask again for what the ledger holds.
2. Ask the questions in `references/chasing.md`, in order: invoices a month and the share paid late, the reminder
   rounds and the channel of each, how many invoices reach each round with minutes each and who, hand-overs to a
   collection agency or lawyer, and DSO if the user knows it.
3. Show the counts as sums in a short table (round, channel, sum, count, minutes, who). Ask the user to confirm
   or correct it before anything is written.
4. Replace step 4 in one command line: `unset task.chase`, then one `set` with every task (count, minutes, mode,
   who, label in the user's language) plus `note.dso` and `note.late_share` when given. Say the rough estimate
   was replaced. Then run `process`.

## Presentation

- Show the `process` output as printed: the map in its code block, the table, the formulas. Do not round,
  reword or recompute its numbers.
- Then two or three short lines: step 4 before and after, with the sum ("13.3 hours a month on the rough
  estimate, 16.7 round by round: 16.7 − 13.3 = 3.4 more"), and the round that takes the most hours.
- End with one offer: automation-report to add everything up in a one-page report. Also offer matching-check
  when step 3 holds only `main` or nothing, and method-compare when the ledger has no `method` entries.
