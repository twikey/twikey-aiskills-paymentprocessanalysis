# Chasing check: questions, counts and commands

Read this when running the chasing check. Section 1 is what to ask, section 2 turns the answers into task counts,
section 3 writes them to the ledger, section 4 covers the cases that do not fit the usual flow.

## 1. The questions, in order

Ask two or three per turn, in the user's language. Skip what the ledger already holds and confirm it instead
("You said about 400 invoices a month. Is that still right?").

**Turn 1: volume**
- How many invoices do you send a month?
- What share of them is paid after the due date? If the user does not know: "Closer to one in ten, one in four or
  one in two?"
- Do you know your days sales outstanding (DSO)? It is optional. Store it as given in `note.dso`, as a full
  phrase in the user's language ("DSO: 48 days, your figure"): a note prints in the report without its key.

**Turn 2: the rounds**
- How many reminder rounds does a late invoice go through before you stop or hand it over, and what is each round:
  an e-mail, a phone call, a letter or a registered letter (formal notice)?
- Does the accounting software send a round on its own, does someone start or check it, or is it done by hand?

**Turn 3: each round**
- How many invoices are still open when each round goes out? A count ("about 50 second reminders a month") or a
  share of the round before ("about half are still open after the first e-mail") both work. If the software sends
  the reminders, its reminder history for last month gives the counts.
- How many minutes does one take, including the answer when the customer replies ("I already paid", "send me a
  copy")? If the user does not know: "Closer to two, five or ten minutes per call, counting the calls that don't get
  through?"
- Who does it? Write the role in the user's words (accounting, office manager, account manager). If the user gives
  a person's name, ask for the role and store only that.

**Turn 4: the end of the line**
- How many invoices a month go to a collection agency, a bailiff or a lawyer, and how many minutes does preparing
  and handing over one file take, follow-up questions included?
- Does someone go through the list of open invoices before the rounds go out? How often a month, and how long
  each time?
- Only when the ledger has no `company.hourly_cost` and the user wants to see cost: "What does one hour of the
  people doing this cost you, all-in?"

## 2. From answers to task counts

A task's count is the number of invoices that reach that round in a month. Build it as a sum of the user's own
numbers, so the table shows where it comes from:

- First round = invoices a month × share paid late: `400*25%`.
- Each later round = the round before × the share still open: `400*25%*50%`.
- Hand-overs = the last round × the share handed over, or the count the user gives.
- When the user gives a count directly, use it as it is: `50`.
- When every late invoice gets the same number of e-mail rounds at the same minutes, one task can hold them:
  `400*25%*2`.

Values use digits, `+ - * / ( )`, `%` and a dot for decimals. Turn "2,5 minuten" or "2,5 minutes" into `2.5`.

**Task names** sort in the calculator's table, so number them in the order they happen. Lowercase letters, digits
and `_` only.

| Name | Task |
|---|---|
| `r0_review` | going through the list of open invoices |
| `r1_mail`, `r2_mail` | reminder rounds by e-mail, numbered in order |
| `r3_call` | a round by phone |
| `r3_letter` | a round by ordinary letter |
| `r4_registered` | a formal notice by registered letter |
| `r9_handover` | hand-overs to a collection agency, bailiff or lawyer (always last) |

Use the round's own number: a call that comes first is `r1_call`.

**Mode**, how the round is done today: `automatic` when the software sends it with no one touching it (minutes are
then zero, or the time someone spends checking), `partly` when the software sends it but someone starts or checks
it, `manual` when a person writes, calls or posts it.

**Labels** go in the user's language. Write an apostrophe as ’ so the single quotes around the value stay intact.

| English | Dutch | French |
|---|---|---|
| Go through the open invoices | Openstaande facturen overlopen | Passer en revue les factures ouvertes |
| First reminder by e-mail | Eerste herinnering per e-mail | Premier rappel par e-mail |
| Second reminder by e-mail | Tweede herinnering per e-mail | Deuxième rappel par e-mail |
| Reminder call | Klant opbellen | Rappel par téléphone |
| Reminder letter | Aanmaning per brief | Rappel par courrier |
| Formal notice by registered letter | Ingebrekestelling per aangetekende brief | Mise en demeure par lettre recommandée |
| Hand-over to a collection agency | Dossier naar het incassobureau | Transmission à une société de recouvrement |
| Hand-over to a lawyer or bailiff | Dossier naar advocaat of gerechtsdeurwaarder | Transmission à un avocat ou un huissier de justice |

### Worked example

The answers: 400 invoices a month, one in four paid late. The first reminder is an e-mail the accounting software
prepares and someone checks (two minutes). Half are still open for the second e-mail, typed by hand (four
minutes). Of those, 40% get a call from the account manager (ten minutes). Half of the called invoices get a registered letter
(15 minutes). 30% of those go to a collection agency (45 minutes per file, by the finance manager). Accounting
goes through the open invoices four times a month (30 minutes). DSO 48 days.

Show this to the user before writing anything and ask whether it matches:

| Round | Channel | Sum | Count | Minutes | Who |
|---|---|---|---|---:|---|
| 0 | open-invoice list | four times a month | 4 | 30 | accounting |
| 1 | e-mail | 400 × 25% | 100 | 2 | accounting |
| 2 | e-mail | 400 × 25% × 50% | 50 | 4 | accounting |
| 3 | call | 400 × 25% × 50% × 40% | 20 | 10 | account manager |
| 4 | registered letter | 400 × 25% × 50% × 40% × 50% | 10 | 15 | accounting |
| hand-over | collection agency | 400 × 25% × 50% × 40% × 50% × 30% | 3 | 45 | finance manager |

The calculator then prints 2.0 + 3.3 + 3.3 + 3.3 + 2.5 + 2.3 = 16.7 hours a month for step 4. With a rough
estimate of `400*25%` reminders at 8 minutes (13.3 hours), the change is 16.7 − 13.3 = 3.4 hours a month.

## 3. The commands

Run from the working folder, with the path SKILL.md shows (in claude.ai: the folder SKILL.md is in).

```
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" show
python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process

python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" unset task.chase && python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" set \
  'task.chase.r0_review.count=4' 'task.chase.r0_review.minutes=30' 'task.chase.r0_review.mode=manual' \
  'task.chase.r0_review.who=accounting' 'task.chase.r0_review.label=Go through the open invoices' \
  'task.chase.r1_mail.count=400*25%' 'task.chase.r1_mail.minutes=2' 'task.chase.r1_mail.mode=partly' \
  'task.chase.r1_mail.who=accounting' 'task.chase.r1_mail.label=First reminder by e-mail' \
  'task.chase.r2_mail.count=400*25%*50%' 'task.chase.r2_mail.minutes=4' 'task.chase.r2_mail.mode=manual' \
  'task.chase.r2_mail.who=accounting' 'task.chase.r2_mail.label=Second reminder by e-mail' \
  'task.chase.r3_call.count=400*25%*50%*40%' 'task.chase.r3_call.minutes=10' 'task.chase.r3_call.mode=manual' \
  'task.chase.r3_call.who=account manager' 'task.chase.r3_call.label=Reminder call' \
  'task.chase.r4_registered.count=400*25%*50%*40%*50%' 'task.chase.r4_registered.minutes=15' \
  'task.chase.r4_registered.mode=manual' 'task.chase.r4_registered.who=accounting' \
  'task.chase.r4_registered.label=Formal notice by registered letter' \
  'task.chase.r9_handover.count=400*25%*50%*40%*50%*30%' 'task.chase.r9_handover.minutes=45' \
  'task.chase.r9_handover.mode=manual' 'task.chase.r9_handover.who=finance manager' \
  'task.chase.r9_handover.label=Hand-over to a collection agency' \
  'note.late_share=25% of 400 invoices a month are paid late' 'note.dso=DSO: 48 days, your figure'

python3 -B "${CLAUDE_SKILL_DIR}/scripts/hours.py" process
```

- `unset task.chase` removes every task of step 4: the rough `main` and any detailed tasks from an earlier run.
- `set` writes nothing when one pair is wrong. After `error: ...`, fix that pair and run `set` again on its own
  (the rough estimate is already gone, so do not run `unset` again unless you want to start over).
- To correct one number later, `set` only that key and run `process` again.

## 4. Edge cases

**No reminders at all.** Step 4 is zero hours, not "not asked yet". Unset the step and set one task with count 0
and minutes 0: `'task.chase.r1_none.count=0' 'task.chase.r1_none.minutes=0' 'task.chase.r1_none.who=no one'
'task.chase.r1_none.label=No reminders sent'` (who and label in the user's language). Leave the mode out. The
table then shows "-" under "How today", so say that it means nothing is done. If invoices are paid late anyway,
store the share in `note.late_share` and state the zero hours plainly, without judging it. A call made "only when
it gets really late" is a round: count it.

**Everything outsourced.** When an agency or the accountant's office sends every reminder, count only the hours
that stay in-house: passing on the list or the files, answering the agency's questions, reading its reports, and
customer calls that still come in. Do not count the agency's own time and do not ask for its fee, because this
check counts hours. Add `'note.chase_outsourced=Reminders sent by an external agency'` in the user's words.

**The user only knows DSO.** Store `note.dso` as given. Say that DSO tells how long money takes to come in on
average, not how much work goes into chasing it, so the hours need one count. Ask for the number of first
reminders a month (from the reminder history, or as an estimate the user picks: "closer to 20, 50 or 100?") and
the minutes each. If the user asks you to fill it in, do not: leave the step as it is.
If the user cannot give any count, do not unset anything: step 4 keeps the rough estimate from process-map, and
say so.

**Empty ledger** (chasing-check runs on its own). Set `company.lang` and ask for invoices a month directly. The map
shows the other steps as "not asked yet". Offer process-map for the full picture.

**Customer names, IBANs or invoice lists pasted.** Say they are not needed, do not repeat or store them, and ask
for the counts instead (or count the lines without naming anyone).

**A request to send reminders or contact a customer.** This check only counts and explains. It does not send,
call, write to or contact anyone, and it does not touch the accounting software.
