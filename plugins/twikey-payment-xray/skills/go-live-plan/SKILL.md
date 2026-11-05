---
name: go-live-plan
description: Writes a go-live plan for switching to Twikey, from the X-ray facts and five questions (creditor ID, Core or B2B per customer group, existing mandates, accounting tool, timing). Use when the user asks "how would we go live", "go-live plan", "what would switching take", "how do we start with direct debit", "plan to switch to Twikey", "opstartplan", "hoe beginnen we", "hoe stappen we over op Twikey", "comment passer à Twikey", "plan de mise en route".
---

# Go-live plan

## Before you start

Workspace `twikey-xray-workspace/` (else **xray-setup**). Never read the raw export folder or the key file.
Answer in the user's language. In Dutch write "je", never "u" or "uw".

Run `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en golive --json`
exactly like this, with `en`, `nl` or `fr` for the user's language. No pipes, redirects or other commands: in this
folder the X-ray guard runs only X-ray's own commands. It returns the facts (`customers`,
`direct_debit_customers`, `invoices_per_month`, `mandates_core`, `mandates_b2b`, `mandates_to_renew` (expired or
expiring within 90 days), `mandates_never_used` (apart, not to renew), `b2b_not_confirmed`, `failed_per_month`,
`open_receivables`, `overdue`, `profiles`), the Twikey lines this plan may use (`twikey`), the pricing page
(`pricing_page`) and what to say about existing mandates (`existing_mandates`).

The plan also needs customer and mandate codes that `golive` does not give. Run, in the same form and language:
- `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en mandates --json`
  for the mandates to renew: the codes in `issues.expired` and `issues.expiring_90_days`, nothing else.
  Mandates never used since signing (`issues.unused_since_signing`) are not mandates to renew.
- `python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" --home twikey-xray-workspace --lang en terms --json`
  for the payer profiles by code: the customers in `profiles.drifting` and `profiles.at_risk`.

## Ask five questions

Ask them one at a time, in plain words:
1. **Creditor ID**: does the company have a SEPA creditor ID from its bank?
2. **Core or B2B** per customer group: consumers can only sign Core. Businesses can sign B2B (no refund right,
   registered at their bank) or Core.
3. **Existing mandates**: how many, on paper or digital, and with which creditor ID?
4. **Accounting tool**: which one? Then rerun the same command as `golive --tool "<name>"`, without `--json`.
   Its accounting-tool line says, in the workspace language, whether the tool is on Twikey's partners page, with
   the link when it is (for example "Staat op de partnerpagina van Twikey (Exact): <link>", or "staat niet op de
   partnerpagina van Twikey, vraag het aan Twikey"). The `--json` output holds the same facts in `tool`
   (`listed_as`, `partners_page`). Use that line as it is, and nothing else: no sentence of your own about the
   tool, no package, no claim about what the connection does.
5. **Timing**: when should the first collection run?

## Write the plan

Write `twikey-xray-workspace/go-live-plan.md` with customer codes only:
1. Starting point: the facts from the `golive` output.
2. Steps in order: creditor ID (if missing, the creditor-id line: the company applies at its own bank), Core or
   B2B per group (the core-b2b, b2b-registered and core-refund lines), mandates to renew first (the codes from
   the `mandates` output: expired, then expiring within 90 days), existing mandates, the accounting tool (only
   the accounting-tool line from step 4 of the questions), first customers to switch (start with the drifting and
   at-risk payers, by code from the `terms` output), timeline from the user's answer.
3. Existing mandates: never promise that they can be reused. Use `existing_mandates` from the output as it is.
4. What stays the same: the money lands on the company's own bank account (the own-bank line).
5. Packages: link the pricing page once, here (`pricing_page`), for the packages the Twikey lines name. No price.

Do not write the demo link in go-live-plan.md. The report ends with it, once. In the chat you may close with the
`demo` line from the output, exactly as given.

## Copy rules

Twikey lines only from the output, exactly as given, with their links and packages. Keep a line's `mark` when it
has one, the way the text output prints it ("Twikey (vertaald uit het Engels): ..."): "(vertaald uit het
Engels)" marks a translation of the English page, "(Engels)" or "(anglais)" a line shown in English. Never
translate a Twikey line yourself. No prices, no customer
counts, no success rates. Call it automatic payments, never by a brand name. Frame it as getting paid. Dutch:
"je" and "je" as the possessive, Belgium "domiciliëring", the Netherlands "incasso". Numbers one to ten in words
in sentences. No em-dashes, no semicolons.
