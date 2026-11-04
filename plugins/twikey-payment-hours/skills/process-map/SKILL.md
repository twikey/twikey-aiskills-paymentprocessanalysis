---
name: process-map
description: Maps how a company gets paid, step by step, with hours, FTE and cost per step. Start here. Use when asked how much time getting paid takes, "hoeveel tijd kost ons betaalproces", "combien de temps".
---

# Process map

Walks the user through the eight steps of getting paid, one step at a time, saves their own numbers in a small
ledger and ends with a process map: hours a month per step, total, FTE and cost at their own hourly cost, today
and at twice the volume. Every number is the user's answer or a formula on it. method-compare, chasing-check,
matching-check and automation-report build on the same ledger. Covers invoicing, taking in payments, matching,
chasing late payers, failed payments, payment details, refunds and reporting.

## Ground rules

- Answer in the user's language. Dutch: "je", never "u" or "uw", Belgian terms (domiciliëring). French: "vous".
  Two or three questions per turn, plain words. In prose, one to ten in words, digits from 11.
- Aggregate numbers only. If the user pastes customer names, IBANs or invoice lists, say it is not needed, do
  not repeat or save any of it, and keep only the counts.
- When the user does not know, offer a range as a question to estimate ("closer to one, three or five
  minutes?"), never as what other companies do or as a benchmark.
- Even when the user asks you to fill in or assume a number, never pick one. Offer the range question, set only
  what the user picks, and leave the rest unset.
- Say nothing about Twikey here: automation-report covers that, through the calculator. No prices, no success
  rates, no saving promises. Say "automatic payments", never the brand word for it.
- Seeing, not doing: never contact customers or touch payment systems. No m-dashes, semicolons or exclamation marks.

## The calculator

Run it from the working folder (the ledger `twikey-payment-hours.json` lives there). Single-quote every
KEY=VALUE: values hold `*`, `%` and spaces. Write an apostrophe inside a value as ’.

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'company.lang=nl' 'payments.per_month=380'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'task.match.main.label=Betalingen koppelen' 'task.match.main.mode=partly' 'task.match.main.who=boekhouder' 'task.match.main.count=380*40%' 'task.match.main.minutes=3'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'company.hourly_cost=45'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset task.refunds
```

Where `${CLAUDE_SKILL_DIR}` is not filled in (claude.ai), use the folder this SKILL.md is in. If `python3` is not
found (Windows), run the same command with `py -3`, then with `python`. If none works, work it out by hand as
with code execution off (below), and say so.

- One task per step: `task.STEP.main.label|mode|who|count|minutes`. STEP: `invoice`, `collect`, `match`,
  `chase`, `failed`, `details`, `refunds`, `reporting`. mode: `manual`, `partly`, `automatic`. Always set the
  label, short, in the user's language. who is a role, never a person's name.
- count takes the sum the user agreed to (`380*40%` prints as 380 × 40% = 152). Decimals with a dot (1.5).
- A note (`note.KEY=TEXT`) prints in the report without its key: write the text as a full phrase in the user's
  language.
- Setting a key again replaces it. `unset task.STEP` removes a step, `unset task` clears every step. Exit code 2
  with `error: ...`: fix the key or value and run again. `--lang en|nl|fr` before the command changes the output.
- Code execution off: work out every number by hand with `references/formulas.md`, show each formula with the
  user's numbers in the same map and table, and say once that it was worked out by hand. Keep the answers as a
  list of the keys above so the other skills can use them.

## Flow

Read `references/steps.md` first: per step the work it covers, the questions, a count formula, estimate prompts.

1. If a ledger exists, run `show` and ask whether to continue or start over. Open in two sentences: eight steps,
   about ten minutes, only counts and minutes. Set `company.lang`. Ask the anchors: invoices or payment requests
   a month, payments received a month, how customers pay (rough share per method).
2. Go through the eight steps in order, one a turn (two short ones may share). Per step: how it is done today,
   who, times a month, minutes each. Build the count from the anchors and let the user confirm the sum.
3. After each step, `set` all five keys and confirm in one line ("Matching: 380 × 40% = 152 a month, three
   minutes each, partly automatic, bookkeeper"). Any answer can be changed later.
4. A step that does not apply: one task with count 0 and minutes 0, its label saying why, so it shows 0.0 hours.
   A step the user skips: no task, it shows as not asked yet. A fully automatic step is not left out: mode
   `automatic`, minutes 0 or the minutes someone still spends checking it.
5. After step 8, ask once for the hourly cost of the people doing this work, salary and overhead included. Never
   suggest a figure. No answer: hours only. A full-time week other than 38 hours goes in `company.fte_hours_week`.
6. Run `process`.

## How to present

1. Paste the `process` output as printed: the map in its code block, the table, the formula lines. Do not
   recompute, round, restyle or translate its numbers.
2. Add at most two sentences: the step with the most hours and the total at twice the volume, copied from the
   output. Name the steps the user skipped (the map shows them as not asked yet). Call it an estimate from their
   answers.
3. End with one line offering the next skills: method-compare (time, failures and days to cash per payment
   method), chasing-check (reminders in detail), matching-check (matching in detail), automation-report (a
   one-page report of it all).
