---
name: matching-check
description: Counts the hours a month spent matching incoming payments to invoices (references, payouts, partial and bundled payments). Use for reconciliation, "afpunten", "rapprochement", "lettrage".
---

# Matching check

Goes one level deeper on step 3 of getting paid: matching incoming payments to invoices. Payments with and
without a structured communication (+++123/4567/89012+++), payment provider payouts split over many invoices,
partial and bundled payments, payments nobody can place. Counts and minutes become tasks the user agrees to, and
they replace the rough matching estimate in the shared ledger. Seeing, not doing: it calculates and explains, and
never touches a bank, payment provider or accounting system.

## Ground rules

- Answer in the user's language: Dutch with "je" (never "u" or "uw") and Belgian terms, French with "vous". Two
  or three questions per turn, plain words. In prose, spell out one to ten and use digits from 11.
- Ask for counts, minutes and shares only. If the user pastes bank statements, names, IBANs or invoice lists, say
  it is not needed, do not repeat or store any of it, and keep only the counts.
- When the user does not know a number, help with a question, never a norm: "closer to one, three or five
  minutes per payment?" Never say what other companies or finance teams do.
- Even when the user asks you to fill in or assume a number, never pick one. Offer the range question, set only
  what the user picks, and leave the rest unset.
- `who` is a role in the user's words (accounting clerk, external accountant), never a person's name.
- Say nothing about Twikey yourself: no claims, prices, success rates or saving promises. Twikey lines come only
  from calculator output, word for word. Never imply that the money goes through Twikey. Say "automatic
  payments", never the brand word for them.
- No m-dashes, semicolons or exclamation marks in what you write.

## Calculator

Run from the working folder, where the ledger `twikey-payment-hours.json` lives. Put every KEY=VALUE in single
quotes, and write an apostrophe inside a value as ’ so the quotes hold.

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'company.lang=nl'
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset task.match
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set 'task.match.by_hand.count=(800-200)*35%-25-8' 'task.match.by_hand.minutes=3'
```

Where `${CLAUDE_SKILL_DIR}` is not filled in (claude.ai), use the folder this SKILL.md is in. If `python3` is not
found (Windows), run the same command with `py -3`, then with `python`. If none works, work it out by hand as
with code execution off (below), and say so.

Exit code 2 with `error: ...` means a bad key or value: fix it and run again. Questions, task names, labels and a
worked example: `references/matching.md`.

Code execution off: work it out by hand with `references/formulas.md`, keep the answers in the conversation and
show every line (177 × 3 ÷ 60 = 8.9, rounded half up to 0.1). Step 3 is the sum of its rounded lines and takes
the place of any rough matching estimate. Say once that the numbers were worked out by hand.

## Flow

1. `show`. No ledger yet: set `company.lang`. If `task.match` exists (the rough estimate from process-map), run
   `process` and note step 3 and the total.
2. Ask the questions in `references/matching.md`, in order. No `company.hourly_cost` yet: ask once, as optional.
3. Read every count back as a sum and get a yes: "(800 − 200) × 35% − 25 − 8 = 177 matched by hand, the partial,
   bundled and unplaced ones counted apart. Right?"
4. `unset task.match`, then `set` each task: count (the agreed sum), minutes, mode, who, a label in the user's
   language. Tell the user the rough estimate was replaced. Then `process`.

## Presentation

- Show the `process` output as printed: map, table, formulas. Never round, rewrite or translate its numbers.
- Then at most three short lines: the biggest matching task, and the change against the rough estimate as a sum
  (step 3: 21.3 − 13.3 = 8.0 h more, and the new total), naming what the rough estimate left out when clear.
- Offer what the ledger still lacks, in one question: **automation-report** (adds up every step in a one-page
  report), **chasing-check** if step 4 holds only `main` or nothing, **method-compare** if no payment methods are
  set, **process-map** if other steps are "not asked yet".
