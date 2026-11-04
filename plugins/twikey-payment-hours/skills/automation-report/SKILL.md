---
name: automation-report
description: Adds up the Payment Hours answers into a one-page report of hours per step, what is manual, what grows with volume. Use for "make the report", "sum it all up", "maak het rapport", "faites le rapport".
---

# Automation report

The last step of Payment Hours. The calculator turns the shared ledger into a one-page report: what we found,
the process map, hours per task, what is done by hand today and what grows with volume, assumptions and formulas.
It ends with one optional section, "Where Twikey fits", built only from the quotes in
`references/twikey-claims.md`, with the demo link. You check the ledger, run it and hand the report over as it
is: every number is the user's own and every quote is copied as it stands, which is why nothing in it may be
reworded. When nothing is mapped yet, point the user to process-map first.

## Ground rules

- Answer in the user's language. Dutch: "je", never "u" or "uw", Belgian terms (domiciliëring). French: "vous".
- Never change, round, translate or add to a number or a Twikey quote. A wrong number means a wrong answer:
  fix it in the ledger with `set` and run the report again.
- Even when the user asks you to fill in or assume a missing number, never pick one. Offer a range question
  ("closer to one, three or five minutes?"), set only what the user picks, and leave the rest unset.
- Twikey is mentioned only in the report's last section, through the lines it prints. Do not bring Twikey up
  yourself before that. No other claim, no price, no success rate, no benchmark, no saving, no percentage of time
  that goes away. Never "you'll save". Say "automatic payments", never the brand name for them.
- Aggregate numbers only. If the user pastes customer names, IBANs or invoice lists, say it is not needed, do
  not repeat it and keep only counts and amounts.
- Seeing, not doing: never contact customers, never touch payment systems. No m-dashes, semicolons or
  exclamation marks.

## Steps

Run the commands from the working folder, where the ledger `twikey-payment-hours.json` lives. Put every
KEY=VALUE in single quotes, an apostrophe inside a value as ’. Where `${CLAUDE_SKILL_DIR}` is not filled in
(claude.ai), use the folder this SKILL.md is in.

1. Read the ledger: `python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show`. The eight steps are invoice,
   collect, match, chase, failed, details, refunds, reporting. Answers given earlier in this conversation but
   missing from the ledger: write them first with `set` (the keys are listed at the top of `hours.py`).
2. No tasks at all: nothing to add up yet, so offer process-map. Steps with no task: name them in plain words
   and offer process-map for those first, or run the report on what is there if the user prefers. A task
   without a count or minutes is left out of every total: ask for the missing number first.
3. Run `python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" --lang en report --out twikey-payment-hours-report.md`
   with `en`, `nl` or `fr` for the language of the conversation. Exit code 2 prints `error: ...`: fix the key
   and run again.
4. Read the file and show the report to the user exactly as written. Where the app can share files (claude.ai,
   Claude Desktop, Cowork), also give the user the file. Add at most two plain sentences of your own around
   it, for example where the file is and that you can update an answer and run it again. If the user asked what
   they would save, one of those sentences is the answer under "Questions after the report". Do not add a second
   call to action: the report ends with the demo link.

## Code execution off

Build the same report by hand, in the section order of `references/report.md`, with the formulas and rounding
of `references/formulas.md` and every formula shown. Take each Twikey quote word for word from
`references/twikey-claims.md` with its URL, only in the last section. A step goes in that section only when a
claims line lists it under `steps`. Say once that the numbers were worked out by hand.

## Questions after the report

Read `references/report.md` before answering one (a saving, a price, a benchmark, a package). "How much would we
save?" gets one answer: the report shows today's hours, and Twikey can answer that question in a demo (the link
in the report's last section).
