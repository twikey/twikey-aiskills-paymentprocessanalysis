# Formulas

The calculator `scripts/hours.py` uses these formulas. When code execution is off, work them out by hand in the
same order, show each one with the user's numbers, and say once that the numbers were worked out by hand.

Rounding: half up. Counts and minutes to 0.01 before anything is worked out with them (the number the table
shows is the number used), hours to 0.1, euros to the cent, FTE to 0.01. Every total adds up the rounded lines it
shows, so the lines always add up to the total.

## Hours (process-map, chasing-check, matching-check)

| What | Formula |
|---|---|
| Hours a month, one task | times a month × minutes each ÷ 60 |
| Hours a month, one step | sum of its tasks' rounded hours |
| Total hours a month | sum of every task's rounded hours |
| Hours in a full-time month | hours in a full-time week × 52 ÷ 12 (38 × 52 ÷ 12 = 164.7 when the user gives no week) |
| FTE | total hours a month ÷ hours in a full-time month |
| Cost a month | total hours a month × the user's hourly cost |
| Cost a year | cost a month × 12 |
| At twice the volume, one task | times a month × 2 × minutes each ÷ 60. A task that does not grow with volume (reporting, by default) stays the same |
| At twice the volume, total | sum of the rounded doubled lines, then FTE and cost as above |

A count may be a sum the user agreed to, for example invoices a month × share paid late × reminder rounds:
400 × 25% × 2 = 200. Show the sum, not only the result.

## Payment methods (method-compare)

All inputs are the user's own. Time comes first and needs no fees. A missing time input counts as zero and is
named as not given. Fees are optional: a method has fees when its fixed or percentage fee is given (0 counts).
Euro totals are compared only between methods with fees, and the methods without are named.

| What | Formula |
|---|---|
| Payments a month, one method | payments a month × share |
| Hours a month, one method | (payments × manual minutes + failures × minutes per failure + disputes × minutes per dispute) ÷ 60, from the exact inputs, rounded to 0.1 at the end |
| Failures a month, one method | payments a month × failure rate (disputes: × dispute rate) |
| Time cost a month, one method | hours a month × hourly cost (only with an hourly cost) |
| All methods, hours a month | sum of the rounded lines |
| Average days until the money is in | sum of (share × days) ÷ sum of the shares that have days |

Only for a method with fees:

| What | Formula |
|---|---|
| Fee per payment | fixed fee + percentage fee × average payment |
| Fees per 100 payments | 100 × fee per payment |
| Handling hours per 100 | 100 × manual minutes per payment ÷ 60 |
| Handling cost per 100 | 100 × manual minutes per payment ÷ 60 × hourly cost, rounded to the cent once |
| Failures per 100 | 100 × failure rate |
| Cost of one failure | fee per failure + minutes per failure ÷ 60 × hourly cost |
| Failure cost per 100 | failures per 100 × cost of one failure |
| Disputes per 100, cost of one, cost per 100 | as failures, with the dispute rate, fee and minutes |
| Full cost per 100 payments | fees + handling cost + failure cost + dispute cost |
| Per year | full cost per 100 × payments a month for that method × 12 ÷ 100 |
| All methods per year | sum of the rounded per-year lines, only when every method has fees |

What-if "move P% of the payers of method A to method B": A's new share = A's share − A's share × P%. B's new share =
B's share + A's share × P%. Then hours a month, failures a month, average days and time cost again with the new
shares, each as today → after. A euro difference a year (new total − today's total) only when A and B both have
fees.
