# The report: sections, follow-up questions, what never to say

## Sections

`hours.py report` writes these sections in this order, with the same structure in English, Dutch and French.
The calculator writes every number, sentence and quote. When code execution is off, build the same sections by
hand in the same order.

| Section | What it holds |
|---|---|
| Title and date | "Estimate from your own answers" and today's date. |
| What we found | The total hours a month, FTE and cost, then the three steps with the most hours, biggest first, each with its share of the total and the division shown. |
| The process map | The eight steps as a text diagram: how each is done today, hours a month, "not asked yet" for a step with no answer, "?" for a step whose task misses a number. Then the total. |
| Hours a month, per task | One row per task: step, task, how today, who, times a month (a sum such as 400 × 25% × 2 shows its formula), minutes each, hours a month with its formula, hours at twice the volume. Reporting does not grow with volume unless the user said it does. Then the hours by hand, partly automatic and automatic today, each as a sum. |
| Payment methods compared | Only when method-compare ran. Time first: per method the payments, hours and failed payments a month, days until the money is in and time cost, the totals and the average days. Euros only for methods whose fees the user gave, never compared across methods without fees (those are named). The what-if if one was set, in hours, failures and days. |
| Assumptions and formulas | Every number is the user's own answer and nothing was measured. The formulas for total hours, FTE, cost a month and a year (only with an hourly cost), and twice the volume. The user's notes. |
| Where Twikey fits | The only section that names Twikey, and it comes last. The answered steps a Twikey page describes automating, each with its hours and the quote with its link, their hours as a sum, the sentence that not every task in such a step is covered and the demo shows which are, Twikey's lines on the payment methods if method-compare ran, and the demo link. No package names, no prices. |

A step goes in "Where Twikey fits" only when a line in `twikey-claims.md` lists it under `steps`, and a line
carries `steps` only when it says the work is automated or done by Twikey. With the claims file of November 4,
2026 that is collect, match, chase and failed. The claims file wins if it says otherwise.

### Building it by hand

- Hours per task, per step, total, FTE, cost and twice the volume: the formulas and rounding in `formulas.md`.
  Totals add up the rounded lines. Show each formula with the user's numbers.
- Quotes: the line in the user's language with its page. English: `en` and `source`. Dutch: `nl` and
  `source-nl`, and when the line has `nl-kind`, link the English page it names, as the calculator does. French:
  `fr` and `source-fr`, and when there is no `fr` line, the English line marked "(anglais)". Quotes appear only in
  the last section. No package names.
- The `demo` line in the user's language closes the last section.
- Say once, above the report, that the numbers were worked out by hand.

## Follow-up questions

Answer in the user's language, in two or three sentences, and send them back to the report or the demo link.

**"How much would we save with Twikey?"** The report shows the hours spent today, and its last section the hours
on steps a Twikey page describes automating (quote the number from that section). How much of that time goes away depends on how Twikey would be
set up for this company, and Twikey can answer that in a demo (the link in the report). Do not estimate it, not
even on a percentage the user suggests: once it sits next to Twikey's name, it reads as Twikey's promise.

**"What does it cost?" or "Is Twikey worth it for us?"** No price, no range. Point to Twikey's pricing page (the
"Pricing page" list in `twikey-claims.md`) and the demo. The cost of the user's own hours is in the report if they gave an hourly cost. Whether it is worth it is their call, and the demo
is where Twikey answers questions about their case. Never say a company is too small, or big enough, for Twikey.

**"Is this a benchmark?" or "How do we compare to other companies?"** No. Every count, minute, fee and rate is
the user's own answer. Nothing was measured and nothing is compared with other companies. Do not offer an
industry figure.

**"Which package do we need?"** The report names no package. Which one fits depends on the setup, and that is a
question for the demo. Do not recommend one.

**"Can Twikey also do refunds or reporting?"** Those steps are not in "Where Twikey fits" because no Twikey line
in this report speaks to them. Do not say Twikey cannot do it, and do not say it can. The
demo is the place to ask.

**"This number is wrong."** Find the answer behind it, change it with `set`, run the report again and show the
new report. Never edit the report file by hand.

**"Why does a step I already do automatically count?"** A step counts because a Twikey page says it automates
it. The "How today" column shows how the company does it now. The hours are the ones the user gave.

**"Does the money go through Twikey?"** Quote the `own-account` line of `twikey-claims.md` word for word with
its page, in the user's language. Nothing more about it.

**"Can you send this to Twikey or to my team?"** The skill does not contact anyone. The file is theirs to share,
and it holds only their aggregate answers.

## What never to say

- A saving or a reduction: "you'll save", "Twikey cuts this to", "frees up", "up to", any percentage of time or
  cost that goes away.
- A benchmark or a typical value: "most companies", "on average", "the industry", "typically".
- A price, a price range, a discount, or a success rate (recovery, collection, fewer late payments, faster cash).
- Any Twikey feature, integration or claim that is not a line in the report or in `twikey-claims.md`. Never that
  Twikey processes payments or holds the money.
- The brand name for automatic payments. Say "automatic payments".
- A second call to action: no "contact sales", "start a trial", "book a call", no names of people. The demo link
  in the report is the only one.
- A comparison with other payment companies.
