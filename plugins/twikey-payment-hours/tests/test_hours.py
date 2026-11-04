"""Unit tests for scripts/hours.py. Every expected number below is worked out by hand from references/formulas.md.

Run from skills-v2: python3 -B -m unittest discover -s tests -v
"""
import contextlib
import datetime
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "scripts"))

import hours  # noqa: E402

TODAY = datetime.date(2026, 11, 4)
BRAND = "auto" + "pay"  # the brand word the copy never uses, built from parts so this file stays clean too

# A Belgian SME that sends invoices, is paid by card and transfer, has no direct debit yet and asks what moving
# 40% of its transfer payers to SEPA Direct Debit B2B would do.
SAMPLE = [
    "company.lang=en", "company.hourly_cost=45",
    "task.invoice.main.count=400", "task.invoice.main.minutes=3", "task.invoice.main.mode=partly",
    "task.invoice.main.who=accountant", "task.invoice.main.label=Send invoices from the ERP",
    "task.collect.main.count=400", "task.collect.main.minutes=1", "task.collect.main.mode=partly",
    "task.collect.main.who=accountant", "task.collect.main.label=Check incoming payments",
    "task.match.main.count=360", "task.match.main.minutes=4", "task.match.main.mode=manual",
    "task.match.main.who=accountant", "task.match.main.label=Match bank lines to invoices",
    "task.chase.mail.count=400*25%*2", "task.chase.mail.minutes=5", "task.chase.mail.mode=manual",
    "task.chase.mail.who=accountant", "task.chase.mail.label=Reminder mails",
    "task.chase.call.count=400*25%*30%", "task.chase.call.minutes=12", "task.chase.call.mode=manual",
    "task.chase.call.who=finance manager", "task.chase.call.label=Calls to late payers",
    "task.failed.main.count=15", "task.failed.main.minutes=10", "task.failed.main.mode=manual",
    "task.failed.main.who=accountant", "task.failed.main.label=Declined cards",
    "task.details.main.count=20", "task.details.main.minutes=6", "task.details.main.mode=manual",
    "task.details.main.who=accountant", "task.details.main.label=Update bank details",
    "task.refunds.main.count=5", "task.refunds.main.minutes=20", "task.refunds.main.mode=manual",
    "task.refunds.main.who=finance manager", "task.refunds.main.label=Refunds and chargebacks",
    "task.reporting.main.count=4", "task.reporting.main.minutes=90", "task.reporting.main.mode=partly",
    "task.reporting.main.who=finance manager", "task.reporting.main.label=Weekly cash forecast",
    "payments.per_month=400", "payments.avg_amount=850",
    "method.transfer.share=70", "method.transfer.minutes=4", "method.transfer.days=38",
    "method.transfer.fee_fixed=0.15",
    "method.card.share=30", "method.card.fee_fixed=0.25", "method.card.fee_pct=1.4", "method.card.minutes=1",
    "method.card.fail_pct=3", "method.card.fail_minutes=10", "method.card.dispute_pct=0.5",
    "method.card.dispute_fee=15", "method.card.dispute_minutes=30", "method.card.days=3",
    "method.sdd_b2b.share=0", "method.sdd_b2b.fee_fixed=0.30", "method.sdd_b2b.minutes=0.5",
    "method.sdd_b2b.fail_pct=1", "method.sdd_b2b.fail_fee=3", "method.sdd_b2b.fail_minutes=10",
    "method.sdd_b2b.days=5",
    "whatif=transfer:sdd_b2b:40", "note.dso=52 days",
]


def build(pairs):
    led = hours.empty_ledger()
    for pair in pairs:
        key, value = pair.split("=", 1)
        hours.set_value(led, key, value)
    return led


def pnum(text, lang):
    """A number as the report prints it (€, %, decimal comma in nl and fr) back to a float."""
    s = text.replace("€", "").replace("%", "").replace("−", "-").replace(" ", "")
    if lang in ("nl", "fr"):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def template_regex(template, **shapes):
    """found_line and the like as a regex: {x} becomes a named group (shapes[x] or any text), a repeated {x} must
    be the same text."""
    out, seen, pos = "", set(), 0
    for m in re.finditer(r"\{(\w+)\}", template):
        out += re.escape(template[pos:m.start()])
        name = m.group(1)
        out += "(?P=%s)" % name if name in seen else "(?P<%s>%s)" % (name, shapes.get(name, ".+?"))
        seen.add(name)
        pos = m.end()
    return out + re.escape(template[pos:])


def run_main(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hours.main(args)
    return code, out.getvalue(), err.getvalue()


class Rounding(unittest.TestCase):
    def test_half_up(self):
        self.assertEqual(hours.rnd(0.25, 1), 0.3)
        self.assertEqual(hours.rnd(0.35, 1), 0.4)
        self.assertEqual(hours.rnd(0.05, 1), 0.1)
        self.assertEqual(hours.rnd(0.24, 1), 0.2)
        self.assertEqual(hours.rnd(2.675, 2), 2.68)
        self.assertEqual(hours.rnd(1.005, 2), 1.01)
        self.assertEqual(hours.rnd(123456.785, 2), 123456.79)
        self.assertEqual(hours.rnd(100 / 6.0, 1), 16.7)
        self.assertEqual(hours.rnd(0.5, 0), 1.0)
        self.assertEqual(hours.rnd(0.0, 1), 0.0)


class Formatting(unittest.TestCase):
    def test_numbers_per_language(self):
        self.assertEqual(hours.num(1234.5, 1, "en"), "1,234.5")
        self.assertEqual(hours.num(1234.5, 1, "nl"), "1.234,5")
        self.assertEqual(hours.num(1234.5, 1, "fr"), "1 234,5")
        self.assertEqual(hours.eur(29826, "en"), "€29,826.00")
        self.assertEqual(hours.eur(29826, "nl"), "€29.826,00")
        self.assertEqual(hours.eur(1790.4, "fr"), "1 790,40 €")
        self.assertEqual(hours.eur(0, "fr"), "0,00 €")

    def test_plural_and_number_words(self):
        self.assertEqual([hours.payments_word(x, "fr") for x in (0, 1, 1.5, 2)],
                         ["paiement", "paiement", "paiement", "paiements"])
        self.assertEqual([hours.payments_word(x, "en") for x in (0, 1, 2)], ["payments", "payment", "payments"])
        self.assertEqual(hours.payments_word(1, "nl"), "betaling")
        self.assertEqual(hours.NUMBER_WORDS["fr"][1], "une")
        self.assertEqual(hours.NUMBER_WORDS["nl"][7], "zeven")

    def test_one_term_sum(self):
        self.assertEqual(hours.sum_text(["6.0"], "6.0"), "6.0")
        self.assertEqual(hours.sum_text(["1.0", "2.0"], "3.0"), "1.0 + 2.0 = 3.0")

    def test_percent_and_colon(self):
        self.assertEqual(hours.pct(37, "en"), "37%")
        self.assertEqual(hours.pct(37, "nl"), "37%")
        self.assertEqual(hours.pct(37, "fr"), "37 %")
        self.assertEqual(hours.pct(1.4, "nl"), "1,4%")
        self.assertEqual(hours.kv("fr", "Total", "85,6 h"), "Total : 85,6 h")
        self.assertEqual(hours.kv("nl", "Totaal", "85,6 uur"), "Totaal: 85,6 uur")

    def test_smart_counts(self):
        self.assertEqual(hours.smart(30.0, "en"), "30")
        self.assertEqual(hours.smart(0.5, "nl"), "0,5")
        self.assertEqual(hours.smart(100 / 3.0, "en"), "33.33")

    def test_pretty_expr(self):
        self.assertEqual(hours.pretty_expr("400*25%*2", "en"), "400 × 25% × 2")
        self.assertEqual(hours.pretty_expr("400*25%*2", "fr"), "400 × 25 % × 2")
        self.assertEqual(hours.pretty_expr("(400-20)*0.5", "nl"), "(400 − 20) × 0,5")

    def test_dates(self):
        self.assertEqual(hours.date_text(TODAY, "en"), "November 4, 2026")
        self.assertEqual(hours.date_text(TODAY, "nl"), "4 november 2026")
        self.assertEqual(hours.date_text(TODAY, "fr"), "4 novembre 2026")


class Expressions(unittest.TestCase):
    def test_sums(self):
        self.assertEqual(hours.evaluate("400*25%*2"), 200)
        self.assertEqual(hours.evaluate("400 × 25% ÷ 2"), 50)
        self.assertEqual(hours.evaluate("(400-20)*5"), 1900)
        self.assertEqual(hours.evaluate(" 12 "), 12)
        self.assertEqual(hours.evaluate("08"), 8)
        self.assertAlmostEqual(hours.evaluate("1.05*100"), 105)

    def test_percent_of_a_group(self):
        self.assertAlmostEqual(hours.evaluate("(100-65)%*400"), 140)
        self.assertAlmostEqual(hours.evaluate("400*(100-65)%"), 140)
        self.assertAlmostEqual(hours.evaluate("2/(100-65)%"), 2 / 0.35)
        self.assertAlmostEqual(hours.evaluate("((10+10)*2)%*100"), 40)

    def test_rejects(self):
        for bad in ("abc", "__import__('os')", "1e5", "2**3", "1,5", "(5", "%5", "", "5-10", "1/0", "1/(2-2)"):
            with self.assertRaises(hours.UserError, msg=bad):
                hours.evaluate(bad)

    def test_percent_fields(self):
        led = build(["method.card.share=30%", "method.card.fee_pct=1.4 %", "method.card.fail_pct=3",
                     "method.card.dispute_pct=0.5%", "whatif=transfer:sdd_b2b:40%"])
        self.assertEqual(led["methods"]["card"]["share"], 30)
        self.assertEqual(led["methods"]["card"]["fee_pct"], 1.4)
        self.assertEqual(led["methods"]["card"]["dispute_pct"], 0.5)
        self.assertEqual(led["whatif"], {"from": "transfer", "to": "sdd_b2b", "pct": 40})
        for bad in ("method.card.share=120", "method.card.fee_pct=101%", "whatif=transfer:sdd_b2b:150",
                    "whatif=transfer:transfer:10", "whatif=transfer:cash:10", "method.card.days=abc"):
            with self.assertRaises(hours.UserError, msg=bad):
                build([bad])

    def test_percent_fields_take_one_number_only(self):
        # Only "N" or "N%" in a percentage field, so the ledger always stores the same kind of number.
        for bad in ("method.card.share=30*2", "method.card.share=10+5%", "method.card.share=(30)%",
                    "method.card.fee_pct=30%%", "method.card.fail_pct=%3", "method.card.dispute_pct=1/2",
                    "whatif=transfer:sdd_b2b:4.0.0", "method.card.share=1.5.0"):
            with self.assertRaises(hours.UserError, msg=bad) as ctx:
                build([bad])
            self.assertIn("percentage", str(ctx.exception), bad)
        self.assertEqual(build(["method.card.share=30 %"])["methods"]["card"]["share"], 30)
        self.assertEqual(build(["task.chase.main.count=400*25%*2"])["tasks"]["chase"]["main"]["count"], 200)

    def test_values_in_range(self):
        for bad in ("company.fte_hours_week=0.5", "company.fte_hours_week=169", "company.fte_hours_week=0",
                    "task.match.main.count=" + "9" * 400, "task.match.main.count=1000000000*10",
                    "task.match.main.minutes=99999999999", "company.hourly_cost=inf", "company.hourly_cost=nan",
                    "task.match.main.count=" + "(" * 300 + "1" + ")" * 300):
            with self.assertRaises(hours.UserError, msg=bad[:60]):
                build([bad])
        self.assertEqual(build(["company.fte_hours_week=1"])["company"]["fte_hours_week"], 1)
        self.assertEqual(build(["company.fte_hours_week=168"])["company"]["fte_hours_week"], 168)
        self.assertEqual(hours.evaluate("1000000000"), 1e9)


class ProcessHours(unittest.TestCase):
    def setUp(self):
        self.led = build(SAMPLE)
        self.tot = hours.totals(self.led)

    def test_task_hours(self):
        got = {(r["step"], r["name"]): r["hours"] for r in self.tot["rows"]}
        self.assertEqual(got[("invoice", "main")], 20.0)    # 400 × 3 ÷ 60
        self.assertEqual(got[("collect", "main")], 6.7)     # 400 × 1 ÷ 60 = 6.67
        self.assertEqual(got[("match", "main")], 24.0)      # 360 × 4 ÷ 60
        self.assertEqual(got[("chase", "mail")], 16.7)      # 400 × 25% × 2 = 200, 200 × 5 ÷ 60 = 16.67
        self.assertEqual(got[("chase", "call")], 6.0)       # 400 × 25% × 30% = 30, 30 × 12 ÷ 60
        self.assertEqual(got[("refunds", "main")], 1.7)     # 5 × 20 ÷ 60 = 1.67
        self.assertEqual(got[("reporting", "main")], 6.0)   # 4 × 90 ÷ 60

    def test_step_and_total(self):
        self.assertEqual(self.tot["step_hours"]["chase"], 22.7)  # 16.7 + 6.0
        self.assertEqual(self.tot["total"], 85.6)  # 20.0 + 6.7 + 24.0 + 6.0 + 16.7 + 2.5 + 2.0 + 1.7 + 6.0

    def test_total_adds_rounded_lines(self):
        led = build(["task.chase.%s.count=1" % n for n in "abc"] + ["task.chase.%s.minutes=4" % n for n in "abc"])
        tot = hours.totals(led)
        self.assertEqual([r["hours"] for r in tot["rows"]], [0.1, 0.1, 0.1])  # 4 ÷ 60 = 0.07 each
        self.assertEqual(tot["total"], 0.3)  # not 0.2, the exact sum

    def test_count_as_shown(self):
        # 10/3 shows as 3.33. 3.33 × 40.5 ÷ 60 = 2.248 -> 2.2 (the exact 10/3 would give 2.25 -> 2.3)
        led = build(["task.match.main.count=10/3", "task.match.main.minutes=40.5"])
        self.assertEqual(hours.totals(led)["total"], 2.2)
        self.assertIn("3.33 × 40.5 ÷ 60 = 2.2", hours.process_table(led, "en"))

    def test_fte_default_week(self):
        self.assertEqual(self.tot["fte_month"], 164.7)  # 38 × 52 ÷ 12 = 164.67
        self.assertEqual(self.tot["fte"], 0.52)          # 85.6 ÷ 164.7 = 0.5197
        text = hours.process_formulas(self.led, "en")
        self.assertIn("85.6 ÷ 164.7 = 0.52 (hours in a full-time month = 38 × 52 ÷ 12 = 164.7, a 38-hour week, "
                      "the default value)", text)

    def test_fte_given_week(self):
        led = build(SAMPLE + ["company.fte_hours_week=40"])
        tot = hours.totals(led)
        self.assertEqual(tot["fte_month"], 173.3)  # 40 × 52 ÷ 12 = 173.33
        self.assertEqual(tot["fte"], 0.49)          # 85.6 ÷ 173.3 = 0.494
        self.assertIn("a 40-hour week, your answer", hours.process_formulas(led, "en"))

    def test_cost(self):
        self.assertEqual(self.tot["cost_month"], 3852.00)  # 85.6 × 45
        self.assertIn("85.6 × €45.00 = €3,852.00 (a year: €3,852.00 × 12 = €46,224.00)",
                      hours.process_formulas(self.led, "en"))
        led = build([p for p in SAMPLE if not p.startswith("company.hourly_cost")])
        self.assertIsNone(hours.totals(led)["cost_month"])
        self.assertIn(hours.T["en"]["no_cost"], hours.process_formulas(led, "en"))

    def test_twice_the_volume(self):
        got = {(r["step"], r["name"]): r["hours_double"] for r in self.tot["rows"]}
        self.assertEqual(got[("collect", "main")], 13.3)   # 400 × 2 × 1 ÷ 60 = 13.33, not 2 × 6.7
        self.assertEqual(got[("reporting", "main")], 6.0)  # reporting does not grow with volume
        self.assertEqual(self.tot["total_double"], 164.9)  # 40.0 + 13.3 + 48.0 + 12.0 + 33.3 + 5.0 + 4.0 + 3.3 + 6.0
        self.assertEqual(self.tot["fte_double"], 1.0)       # 164.9 ÷ 164.7 = 1.001
        self.assertEqual(self.tot["cost_month_double"], 7420.50)  # 164.9 × 45
        table = hours.process_table(self.led, "en")
        self.assertIn("400 × 2 × 1 ÷ 60 = 13.3", table)
        self.assertIn("6.0 (does not grow with volume)", table)

    def test_scales_override(self):
        led = build(["task.reporting.main.count=4", "task.reporting.main.minutes=90", "task.reporting.main.scales=yes",
                     "task.match.main.count=10", "task.match.main.minutes=6", "task.match.main.scales=no"])
        tot = hours.totals(led)
        self.assertEqual(tot["total"], 7.0)         # 6.0 + 1.0
        self.assertEqual(tot["total_double"], 13.0)  # 4 × 2 × 90 ÷ 60 = 12.0, match stays 1.0

    def test_labels_modes_and_gaps(self):
        led = build(["task.invoice.main.count=0", "task.invoice.main.minutes=3",
                     "task.chase.mail.count=10", "task.match.main.minutes=4"])
        table = hours.process_table(led, "en")
        self.assertIn("| 1. Send the invoice or payment request | Send the invoice or payment request | - | - | 0 | 3 | "
                      "0 × 3 ÷ 60 = 0.0 |", table)
        self.assertIn("| mail |", table)
        self.assertNotIn("main", table)
        gaps = hours.gaps_lines(led, "en")
        self.assertEqual(gaps[0], "- Not asked yet: 2. Take in payments, 5. Handle failed payments, "
                                  "6. Set up and update payment details, 7. Refunds, disputes and chargebacks, "
                                  "8. Reporting and cash forecasting.")
        self.assertEqual(gaps[1], "- Missing a count or minutes, so not in the total: 3. Match payments to invoices, "
                                  "4. mail.")
        self.assertEqual(hours.totals(led)["total"], 0.0)
        process = hours.cmd_process(led, "en")
        self.assertIn(gaps[0], process)
        self.assertIn("not asked yet", process)

    def test_map_alignment(self):
        led = build(["task.chase.a.mode=manual", "task.chase.a.count=1", "task.chase.a.minutes=600",
                     "task.chase.b.mode=partly", "task.chase.c.mode=automatic",
                     "task.match.main.count=2", "task.match.main.minutes=3", "task.match.main.mode=manual"])
        for lang in hours.LANGS:
            text = hours.process_map(led, lang)
            rows = [l for l in text.splitlines() if re.match(r"\d\. ", l) and re.search(r"\d+[.,]\d (h|uur)$", l)]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(set(len(r) for r in rows)), 1, text)


class Methods(unittest.TestCase):
    def setUp(self):
        self.led = build(SAMPLE)
        self.state = {s["id"]: s for s in hours.methods_state(self.led)}

    def test_card(self):
        s = self.state["card"]
        c = s["calc"]
        self.assertAlmostEqual(c["fee_each"], 12.15)    # 0.25 + 1.4% × 850
        self.assertEqual(c["fees"], 1215.00)            # 100 × 12.15
        self.assertAlmostEqual(c["hours"], 100 / 60.0)  # 100 × 1 ÷ 60, exact (printed 1.67 h)
        self.assertEqual(c["time_cost"], 75.00)         # 100 × 1 ÷ 60 × 45, rounded once
        self.assertEqual(c["fails"], 3)                 # 100 × 3%
        self.assertEqual(c["fail_each"], 7.50)          # 0 + 10 ÷ 60 × 45
        self.assertEqual(c["fail_cost"], 22.50)         # 3 × 7.50
        self.assertEqual(c["disputes"], 0.5)            # 100 × 0.5%
        self.assertEqual(c["disp_each"], 37.50)         # 15 + 30 ÷ 60 × 45
        self.assertEqual(c["disp_cost"], 18.75)         # 0.5 × 37.50
        self.assertEqual(c["full"], 1331.25)            # 1215 + 75 + 22.50 + 18.75
        self.assertEqual(s["payments"], 120)            # 400 × 30%
        self.assertEqual(s["year"], 19170.00)           # 1331.25 × 120 × 12 ÷ 100
        self.assertEqual(s["hours_month"], 2.9)         # (100 × 1 ÷ 60 + 3 × 10 ÷ 60 + 0.5 × 30 ÷ 60) × 120 ÷ 100

    def test_transfer_and_b2b(self):
        t = self.state["transfer"]
        self.assertEqual(t["calc"]["time_cost"], 300.00)  # 100 × 4 ÷ 60 × 45, not 6.7 × 45 = 301.50
        self.assertEqual(t["calc"]["full"], 315.00)       # 15.00 + 300.00
        self.assertEqual(t["year"], 10584.00)             # 315.00 × 280 × 12 ÷ 100
        self.assertEqual(t["hours_month"], 18.7)          # 100 × 4 ÷ 60 × 280 ÷ 100 = 18.67
        b = self.state["sdd_b2b"]
        self.assertEqual(b["calc"]["time_cost"], 37.50)   # 100 × 0.5 ÷ 60 × 45
        self.assertEqual(b["calc"]["fail_cost"], 10.50)   # 1 × (3 + 10 ÷ 60 × 45)
        self.assertEqual(b["calc"]["full"], 78.00)        # 30 + 37.50 + 10.50
        self.assertEqual(b["year"], 0.0)

    def test_handling_cost_rounded_once(self):
        led = build(["company.hourly_cost=48", "payments.per_month=299.88", "payments.avg_amount=100",
                     "method.transfer.share=100", "method.transfer.minutes=4", "method.transfer.fee_fixed=0"])
        s = hours.methods_state(led)[0]
        self.assertEqual(s["calc"]["time_cost"], 320.00)  # 100 × 4 ÷ 60 × 48, not 6.7 × 48 = 321.60
        self.assertEqual(s["hours_month"], 20.0)          # 100 × 4 ÷ 60 × 299.88 ÷ 100 = 19.99
        self.assertEqual(s["time_cost"], 960.00)          # 20.0 × 48
        text = hours.cmd_methods(led, "en")
        self.assertIn("Handling cost per 100 payments: 100 × 4 min ÷ 60 × €48.00 = €320.00", text)
        self.assertIn("(100 × 4 ÷ 60 + 0 × 0 ÷ 60 + 0 × 0 ÷ 60) × 299.88 ÷ 100 = 20.0 h", text)
        self.assertIn("Time cost a month: 20.0 h × €48.00 = €960.00", text)
        self.assertIn("All methods, per year: €%s\n" % hours.num(s["year"], 2, "en"), text)  # one term: no "a = a"
        self.assertIn("Hours a month on handling payments: 20.0 h\n", text)

    def test_failures_one_statement_per_equality(self):
        text = hours.cmd_methods(self.led, "en")
        self.assertIn("Failed payments per 100: 100 × 1% = 1. Cost of one: €3.00 + 10 min ÷ 60 × €45.00 = €10.50. "
                      "Per 100: 1 × €10.50 = €10.50", text)
        self.assertIn("Disputes, refunds and chargebacks per 100: 100 × 0.5% = 0.5. Cost of one: €15.00 + 30 min "
                      "÷ 60 × €45.00 = €37.50. Per 100: 0.5 × €37.50 = €18.75", text)

    def test_summary_and_days(self):
        text = hours.cmd_methods(self.led, "en")
        self.assertIn("All methods, per year: €10,584.00 + €0.00 + €19,170.00 = €29,754.00", text)
        self.assertIn("weighted by share: (70% × 38 + 30% × 3) ÷ 100% = 27.5", text)
        self.assertIn("Hours a month on handling payments: 18.7 + 0.0 + 2.9 = 21.6 h", text)
        self.assertIn(hours.T["en"]["m_overlap"], text)
        self.assertIn("Not given, counted as zero: failure rate, dispute rate", text)  # time fields only
        self.assertNotIn("fee", text.split("### ")[0].replace("Fees per 100", ""))  # a missing fee is never a gap
        self.assertNotIn("add up to", text)
        self.assertIn("| Bank transfer | 70% | 280 | 18.7 | 0 | 38 | €841.50 |", text)  # 18.7 × 45
        self.assertIn("| Card (one-off) | 30% | 120 | 2.9 | 3.6 | 3 | €130.50 |", text)   # 120 × 3% = 3.6
        self.assertIn("Failed payments a month: 120 × 3% = 3.6", text)
        self.assertIn("Disputes, refunds and chargebacks a month: 120 × 0.5% = 0.6", text)

    def test_days_skip_methods_without_days(self):
        led = build(SAMPLE + ["method.wero.share=10", "method.transfer.share=60"])
        line = hours.avg_days_line(hours.methods_state(led), "en")
        self.assertTrue(line.endswith("(60% × 38 + 30% × 3) ÷ 90% = 26.3"), line)  # 2370 ÷ 90 = 26.33

    def test_whatif(self):
        text = hours.cmd_methods(self.led, "en")
        self.assertIn("What if 40% of the payers move from bank transfer to SEPA Direct Debit B2B", text)
        self.assertIn("Bank transfer: 70% − 70% × 40% = 42%. SEPA Direct Debit B2B: 0% + 28% = 28%", text)
        self.assertIn("Bank transfer: €315.00 × 168 × 12 ÷ 100 = €6,350.40", text)
        self.assertIn("SEPA Direct Debit B2B: €78.00 × 112 × 12 ÷ 100 = €1,048.32", text)
        self.assertIn("Per year for bank transfer and SEPA Direct Debit B2B: €6,350.40 + €1,048.32 = €7,398.72 "
                      "(today €10,584.00 + €0.00 = €10,584.00)", text)
        self.assertIn("Difference a year: €7,398.72 − €10,584.00 = −€3,185.28", text)
        self.assertIn("11.2 + 1.1 + 2.9 = 15.2 h (today 18.7 + 0.0 + 2.9 = 21.6 h)", text)
        self.assertIn("Failed payments a month: 0 + 1.12 + 3.6 = 4.72 (today 0 + 0 + 3.6 = 3.6)", text)
        self.assertIn("(42% × 38 + 28% × 5 + 30% × 3) ÷ 100% = 18.3 (today 27.5)", text)
        self.assertIn("Time cost a month: 15.2 h × €45.00 = €684.00 (today 21.6 h × €45.00 = €972.00)", text)
        self.assertIn("Difference in time cost a month: €684.00 − €972.00 = −€288.00", text)
        whatif = text.split("### What if")[1]  # time leads, euro follows
        self.assertLess(whatif.index("Hours a month on handling"), whatif.index("Per year for"))
        nl, fr = hours.cmd_methods(self.led, "nl"), hours.cmd_methods(self.led, "fr")
        self.assertIn("### Wat als 40% van de betalers overstapt van ‘overschrijving’ naar ‘SEPA-domiciliëring B2B’", nl)
        self.assertIn("### Simulation : 40 % des payeurs passent de « virement » à « prélèvement SEPA B2B »", fr)
        self.assertIn("Différence par an : 7 398,72 € − 10 584,00 € = −3 185,28 €", fr)
        self.assertIn("0 % de 400 paiements par mois = 0 paiement par mois", fr)

    def no_fee_sample(self, keep=()):
        """The sample without fee fields, except the methods in keep."""
        fee = re.compile(r"^method\.(\w+)\.(fee_fixed|fee_pct|fail_fee|dispute_fee)=")
        return [p for p in SAMPLE if not fee.match(p) or fee.match(p).group(1) in keep]

    def test_fees_absent(self):
        led = build(self.no_fee_sample())
        for lang in hours.LANGS:
            text = hours.cmd_methods(led, lang)
            t = hours.T[lang]
            for word in (t["m_full"], t["m_fees"], t["m_total_year"], t["m_year"], t["m_pair_year"].split(" {")[0]):
                self.assertNotIn(word, text, lang)
            self.assertNotIn(t["m_no_fees"].split("{")[0], text)  # no fees at all: no fee line either
            self.assertIn(t["m_whatif_no_fees"].format(a=hours.method_mid("transfer", lang),
                                                       b=hours.method_mid("sdd_b2b", lang)), text)
            self.assertIn(t["m_time_cost_month"], text)  # time still has its cost
            self.assertEqual(one_term_sums(text), [], lang)
        text = hours.cmd_methods(led, "en")
        self.assertIn("Time cost a month: 15.2 h × €45.00 = €684.00", text)
        self.assertNotIn("Cost of one", text)  # no euro block at all without fees
        self.assertNotIn("fixed fee", text)
        self.assertNotIn("percentage fee", text)

    def test_fees_partial(self):
        led = build(self.no_fee_sample(keep=("card",)))
        text = hours.cmd_methods(led, "en")
        self.assertIn("| Card (one-off) | €1,331.25 | €19,170.00 |", text)
        self.assertNotIn("| Bank transfer | €", text)
        self.assertNotIn("All methods, per year", text)
        self.assertIn("Fees not given for: Bank transfer, SEPA Direct Debit B2B. Euro totals are only compared "
                      "between methods with fees.", text)
        self.assertIn("The euro difference needs fees for both bank transfer and SEPA Direct Debit B2B.", text)
        # card has a fixed and a percentage fee, no fee per failure: that part is left out, not counted as €0.00
        self.assertIn("Cost of one: 10 min ÷ 60 × €45.00 = €7.50", text)
        led = build(self.no_fee_sample(keep=("transfer", "sdd_b2b")))
        text = hours.cmd_methods(led, "en")
        self.assertIn("Fees not given for: Card (one-off).", text)
        self.assertIn("Per year for bank transfer and SEPA Direct Debit B2B", text)  # both ends of the shift have fees
        led = build(["payments.per_month=100", "payments.avg_amount=200", "company.hourly_cost=40",
                     "method.card.share=100", "method.card.fee_pct=1.5", "method.card.minutes=1"])
        text = hours.cmd_methods(led, "en")
        self.assertIn("Fees per 100 payments: 100 × 1.5% × €200.00 = €300.00", text)
        self.assertIn("All methods, per year: €", text)

    def test_fees_complete(self):
        text = hours.cmd_methods(self.led, "en")
        self.assertIn("All methods, per year: €10,584.00 + €0.00 + €19,170.00 = €29,754.00", text)
        self.assertIn("Fees per 100 payments: 100 × (€0.25 + 1.4% × €850.00) = €1,215.00", text)
        self.assertIn("Fees per 100 payments: 100 × €0.15 = €15.00", text)
        self.assertNotIn("Fees not given", text)
        block = text.split("**Card (one-off)**")[1].split("\n\n")[0]  # time first, euro after
        self.assertLess(block.index("Hours a month"), block.index("Fees per 100"))
        self.assertLess(block.index("Time cost a month"), block.index("Fees per 100"))

    def test_percentage_fee_needs_the_average_payment(self):
        led = build(["payments.per_month=100", "company.hourly_cost=40", "method.card.share=60",
                     "method.card.fee_pct=1.5", "method.transfer.share=40", "method.transfer.fee_fixed=0.2"])
        text = hours.cmd_methods(led, "en")
        self.assertIn("Set payments.avg_amount to work out the percentage fees of: Card (one-off).", text)
        self.assertNotIn("| Card (one-off) | €", text)
        self.assertIn("| Bank transfer | €20.00 |", text)
        self.assertNotIn("All methods, per year", text)

    def test_no_hourly_cost(self):
        led = build([p for p in SAMPLE if not p.startswith("company.hourly_cost")])
        text = hours.cmd_methods(led, "en")
        self.assertIn(hours.T["en"]["no_cost"], text)
        self.assertNotIn("Time cost", text)
        self.assertNotIn("Handling cost per 100", text)
        self.assertIn("Full cost per 100 payments: €15.00 + €0.00 + €0.00 = €15.00", text)  # fees only

    def test_whatif_missing_method(self):
        led = build(SAMPLE + ["whatif=card:sdd_core:50"])
        text = hours.cmd_methods(led, "en")
        self.assertIn("SEPA Direct Debit Core has no fees or rates yet", text)

    def test_shares_not_100(self):
        led = build(SAMPLE + ["method.card.share=25"])
        text = hours.cmd_methods(led, "en")
        self.assertIn("The shares add up to 70% + 0% + 25% = 95%, not 100%. Check the mix.", text)
        self.assertIn("70 % + 0 % + 25 % = 95 %, pas 100 %.", hours.cmd_methods(led, "fr"))

    def test_lowercase_mid_sentence(self):
        self.assertEqual(hours.method_mid("transfer", "nl"), "overschrijving")
        self.assertEqual(hours.method_mid("card", "fr"), "carte (ponctuelle)")
        self.assertEqual(hours.method_mid("sdd_b2b", "fr"), "prélèvement SEPA B2B")
        self.assertEqual(hours.method_mid("sdd_b2b", "nl"), "SEPA-domiciliëring B2B")
        self.assertEqual(hours.method_mid("paypal", "en"), "PayPal")
        self.assertEqual(hours.method_mid("wallet", "fr"), "Apple Pay / Google Pay")
        self.assertEqual(hours.method_mid("bancontact", "nl"), "Bancontact")

    def test_no_volume(self):
        led = build(["method.card.share=100"])
        self.assertEqual(hours.cmd_methods(led, "en"), hours.T["en"]["m_no_volume"])


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = os.path.join(self.dir.name, "ledger.json")

    def tearDown(self):
        self.dir.cleanup()

    def read(self):
        with open(self.ledger, encoding="utf-8") as f:
            return json.load(f)

    def test_set_show_unset(self):
        code, out, _ = run_main(["--ledger", self.ledger, "set", "task.chase.mail.count=400*25%*2",
                                 "task.chase.mail.minutes=5", "task.chase.call.count=30", "method.card.share=30",
                                 "note.dso=52 days"])
        self.assertEqual(code, 0)
        self.assertIn("saved 5 answer(s)", out)
        data = self.read()
        self.assertEqual(data["tasks"]["chase"]["mail"]["count"], 200)
        self.assertEqual(data["tasks"]["chase"]["mail"]["count_expr"], "400*25%*2")
        self.assertEqual(data["notes"]["dso"], "52 days")
        code, out, _ = run_main(["--ledger", self.ledger, "show"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["methods"]["card"]["share"], 30)
        code, _, _ = run_main(["--ledger", self.ledger, "unset", "task.chase.mail"])
        self.assertEqual(code, 0)
        self.assertEqual(list(self.read()["tasks"]["chase"]), ["call"])
        run_main(["--ledger", self.ledger, "unset", "task.chase", "method.card"])
        data = self.read()
        self.assertNotIn("chase", data["tasks"])
        self.assertNotIn("card", data["methods"])

    def test_errors_exit_2(self):
        for args in (["set", "task.chase.mail.colour=red"], ["set", "task.chasing.main.count=5"],
                     ["set", "task.chase.Main.count=5"], ["set", "task.chase.main.count=abc"],
                     ["set", "task.chase.main.mode=sometimes"], ["set", "company.lang=de"],
                     ["set", "company.fte_hours_week=0"], ["set", "nokey"], ["set", "foo.bar=1"],
                     ["unset", "task.chasing"], ["unset", "foo"]):
            code, out, err = run_main(["--ledger", self.ledger] + args)
            self.assertEqual(code, 2, args)
            self.assertTrue(err.startswith("error: "), args)
        self.assertFalse(os.path.exists(self.ledger))  # nothing was saved

    def test_bad_values_exit_2_without_traceback(self):
        for pair in ("company.fte_hours_week=0.5", "task.match.main.count=" + "9" * 400,
                     "method.card.share=30*2", "task.match.main.count=" + "(" * 300 + "1" + ")" * 300):
            code, out, err = run_main(["--ledger", self.ledger, "set", pair])
            self.assertEqual(code, 2, pair[:60])
            self.assertTrue(err.startswith("error: "), err)
            self.assertNotIn("Traceback", err)
        self.assertFalse(os.path.exists(self.ledger))

    def test_bad_ledger_exit_2(self):
        with open(self.ledger, "w", encoding="utf-8") as f:
            f.write("{not json")
        code, _, err = run_main(["--ledger", self.ledger, "show"])
        self.assertEqual(code, 2)
        self.assertIn("error: cannot read the ledger", err)

    def test_language_and_report_file(self):
        run_main(["--ledger", self.ledger, "set"] + SAMPLE)
        code, out, _ = run_main(["--ledger", self.ledger, "--lang", "nl", "process"])
        self.assertEqual(code, 0)
        self.assertIn("Totaal: 85,6 uur", out)
        run_main(["--ledger", self.ledger, "set", "company.lang=fr"])
        code, out, _ = run_main(["--ledger", self.ledger, "process"])
        self.assertIn("Total : 85,6 h", out)
        target = os.path.join(self.dir.name, "report.md")
        code, out, _ = run_main(["--ledger", self.ledger, "--lang", "en", "report", "--out", target])
        self.assertEqual(code, 0)
        with open(target, encoding="utf-8") as f:
            self.assertTrue(f.read().startswith("# Getting paid: hours a month"))


def formula_patterns(lang):
    """The formula shapes the calculator prints, as regexes: N a number, M an amount in the language's format."""
    n = r"(?<![\d.,])[\d.,]*\d"  # starts at a number's start, ends on a digit (not on a full stop)
    m = r"(?<![\d,])\d{1,3}(?: \d{3})*,\d{2} €" if lang == "fr" else "€" + n
    t = r"(?:%s|%s(?: ?%%)?)" % (m, n)
    f = lambda s: re.compile(s.replace("N", n).replace("M", m).replace("T", t))
    return {
        "sum": f(r"(?<![×÷] )((?:T \+ )+T) = (T)"),
        "times_60": f(r"(?<![×÷] )(N) × (N) ÷ 60 = (N)"),
        "times_2_60": f(r"(?<![×÷] )(N) × 2 × (N) ÷ 60 = (N)"),
        "divide": f(r"(?<![×÷] )(N) ÷ (N) = (N)"),
        "cost": f(r"(?<![×÷] )(N) × (M) = (M)"),
        "year": f(r"(M) × (N) × 12 ÷ 100 = (M)"),
        "months_12": f(r"(M) × 12 = (M)"),
        "diff": f(r"(M) − (M) = ([−+])(M)"),
        "rate": f(r"100 × (N) ?% = (N)\."),
        "hours_100": f(r"100 × (N) min ÷ 60 = (N) (?:h|uur)"),
        "handling": f(r"100 × (N) min ÷ 60 × (M) = (M)"),
        "one": f(r"(M) \+ (N) min ÷ 60 × (M) = (M)"),
        "hours_month": f(r"\(100 × (N) ÷ 60 \+ (N) × (N) ÷ 60 \+ (N) × (N) ÷ 60\) × (N) ÷ 100 = (N)"),
        "per_month": f(r"(?<![×÷] )(N) × (N) ?% = (N)(?![\d,.]*\d| ?%)"),
        "time_cost": f(r"(N) (?:h|uur) × (M) = (M)"),
        "fee_pct": f(r"100 × (N) ?% × (M) = (M)"),
        "one_time": f(r"(?<![×+] )(N) min ÷ 60 × (M) = (M)"),
        "minus_h": f(r"(N) − (N) = (N) (?:h|uur)"),
    }


def decimals(text):
    m = re.search(r"[.,](\d+)\D*$", text.replace(" ", ""))
    return len(m.group(1)) if m else 0


def false_chains(text):
    """Statements like "100 × 1% = 1 × (€3 + ... = €11) = €11" or "x = 6.7 h × €48 = €321.60": an equality whose
    middle part is again a calculation, so it asserts something false."""
    bad = []
    op = re.compile(r"[×÷+]| − ")
    for line in text.splitlines():
        for statement in re.split(r"\. |: | : |\|| \((?=[^\d€(−])", line):
            parts = statement.split(" = ")
            for i in range(1, len(parts) - 1):
                if op.search(parts[i - 1]) and op.search(parts[i]):
                    bad.append(line)
    return bad


ONE_TERM = re.compile(r"(?<![×÷+−] )(?<=\s)(€?[\d.,]*\d(?: ?%)?(?: €)?) = \1(?!\d|[.,]\d)")


def one_term_sums(text):
    """"6.0 = 6.0", "35% = 35%", "0,00 € = 0,00 €": a sum of one term printed as a formula."""
    return [m.group(0) for m in ONE_TERM.finditer(text)]


class Report(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.led = build(SAMPLE)
        cls.tot = hours.totals(cls.led)
        cls.reports = {lang: hours.cmd_report(cls.led, lang, today=TODAY) for lang in hours.LANGS}

    def check_formulas(self, text, lang):
        """Every sum, product and division the report prints gives the number it prints."""
        n = lambda s: pnum(s, lang)
        p = formula_patterns(lang)
        checks = {
            "times_60": lambda g: (hours.rnd(n(g[0]) * n(g[1]) / 60, 1), n(g[2])),
            "times_2_60": lambda g: (hours.rnd(n(g[0]) * 2 * n(g[1]) / 60, 1), n(g[2])),
            "divide": lambda g: (hours.rnd(n(g[0]) / n(g[1]), decimals(g[2])), n(g[2])),
            "cost": lambda g: (hours.rnd(n(g[0]) * n(g[1]), 2), n(g[2])),
            "year": lambda g: (hours.rnd(n(g[0]) * n(g[1]) * 12 / 100, 2), n(g[2])),
            "months_12": lambda g: (hours.rnd(n(g[0]) * 12, 2), n(g[1])),
            "diff": lambda g: (hours.rnd(n(g[0]) - n(g[1]), 2), (-1 if g[2] == "−" else 1) * n(g[3])),
            "rate": lambda g: (hours.rnd(n(g[0]), 2), n(g[1])),
            "hours_100": lambda g: (hours.rnd(100 * n(g[0]) / 60, 2), n(g[1])),
            "handling": lambda g: (hours.rnd(100 * n(g[0]) / 60 * n(g[1]), 2), n(g[2])),
            "one": lambda g: (hours.rnd(n(g[0]) + n(g[1]) / 60 * n(g[2]), 2), n(g[3])),
            "hours_month": lambda g: (hours.rnd((100 * n(g[0]) / 60 + n(g[1]) * n(g[2]) / 60 + n(g[3]) * n(g[4]) / 60)
                                                * n(g[5]) / 100, 1), n(g[6])),
            "per_month": lambda g: (hours.rnd(n(g[0]) * n(g[1]) / 100, 2), n(g[2])),
            "time_cost": lambda g: (hours.rnd(n(g[0]) * n(g[1]), 2), n(g[2])),
            "fee_pct": lambda g: (hours.rnd(100 * n(g[0]) / 100 * n(g[1]), 2), n(g[2])),
            "one_time": lambda g: (hours.rnd(n(g[0]) / 60 * n(g[1]), 2), n(g[2])),
            "minus_h": lambda g: (hours.rnd(n(g[0]) - n(g[1]), 1), n(g[2])),
        }
        found = 0
        for m in p["sum"].finditer(text):
            terms = [n(x) for x in m.group(1).split(" + ")]
            self.assertAlmostEqual(sum(terms), n(m.group(2)), places=6, msg=m.group(0))
            found += 1
        for name, check in checks.items():
            for m in p[name].finditer(text):
                got, printed = check(m.groups())
                self.assertEqual(got, printed, "%s: %s" % (name, m.group(0)))
                found += 1
        return found

    def test_every_formula_adds_up(self):
        for lang, text in self.reports.items():
            self.assertGreater(self.check_formulas(text, lang), 60, lang)
            self.assertGreater(self.check_formulas(hours.cmd_methods(self.led, lang), lang), 30, lang)
            self.assertGreater(self.check_formulas(hours.cmd_process(self.led, lang), lang), 15, lang)

    def test_no_false_chained_equalities(self):
        self.assertTrue(false_chains("- Failed payments per 100: 100 × 1% = 1 × (€3.00 + 10 min ÷ 60 × €48.00 = "
                                     "€11.00) = €11.00"))
        self.assertTrue(false_chains("- Handling: 100 × 4 min ÷ 60 = 6.7 h × €48.00 = €321.60"))
        for lang, text in self.reports.items():
            for out in (text, hours.cmd_methods(self.led, lang), hours.cmd_process(self.led, lang)):
                self.assertEqual(false_chains(out), [], lang)

    def test_what_we_found(self):
        ranked = sorted(self.tot["step_hours"].items(), key=lambda p: (-p[1], hours.STEPS.index(p[0])))[:3]
        for lang, text in self.reports.items():
            t = hours.T[lang]
            section = text.split("## " + t["found"])[1].split("\n## ")[0]
            self.assertIn(hours.kv(lang, t["found_all"].format(h=hours.num(85.6, 1, lang)), t["found_fte_cost"].format(
                f=hours.num(0.52, 2, lang), c=hours.eur(3852, lang))) + ".", section)
            rx = re.compile(r"^\d\. " + template_regex(t["found_line"]) + "$", re.M)
            lines = list(rx.finditer(section))
            self.assertEqual(len(lines), 3, lang)
            for m, (step, h) in zip(lines, ranked):
                self.assertEqual(m.group("s"), hours.STEP_LABEL[lang][step])
                self.assertEqual(pnum(m.group("h"), lang), h)
                self.assertEqual(pnum(m.group("t"), lang), 85.6)
                self.assertEqual(pnum(m.group("p"), lang), hours.rnd(100.0 * h / 85.6, 0))
            self.assertNotIn("Twikey", section)

    def test_final_section_adds_up(self):
        for lang, text in self.reports.items():
            t = hours.T[lang]
            final = text.split("## " + t["fits"])[1]
            auto = re.search(template_regex(t["auto_sum"], f=r"(?: \([^)]*\))?"), final)
            a, total = pnum(auto.group("a"), lang), pnum(auto.group("t"), lang)
            self.assertEqual(a, 55.9)  # collect 6.7 + match 24.0 + chase 22.7 + failed 2.5
            self.assertEqual(total, 85.6)
            f = auto.group("f")
            self.assertAlmostEqual(sum(pnum(x, lang) for x in f[2:-1].split(" + ")), a)
            steps = re.findall(r"^\*\*(\d)\. [^*]+\*\* ?: ([\d.,]+) ", final, re.M)
            self.assertEqual([s for s, _ in steps], ["2", "3", "4", "5"])
            self.assertAlmostEqual(sum(pnum(h, lang) for _, h in steps), a)
            self.assertIn(t["no_saving"], text.split("## " + t["fits"])[0])
            for gone in ("manual_title", "manual_sum", "next"):  # no uncovered-steps section, no separate next step
                self.assertNotIn(t[gone].split("{")[0].rstrip(": "), text, (lang, gone))

    def test_demo_once_and_sections(self):
        heads = None
        for lang, text in self.reports.items():
            self.assertEqual(text.count("demo.html"), 1, lang)
            self.assertEqual(text.count("utm_source=twikey-payment-hours"), 1, lang)
            self.assertEqual(re.findall(r"^## .*", text, re.M)[-1], "## " + hours.T[lang]["fits"])  # the last section
            count = len(re.findall(r"^## ", text, re.M))
            heads = heads or count
            self.assertEqual(count, heads, lang)

    def test_clean_copy(self):
        for lang, text in self.reports.items():
            for out in (text, hours.cmd_methods(self.led, lang), hours.cmd_process(self.led, lang)):
                self.assertNotIn("—", out)
                self.assertNotIn(";", out)
                self.assertNotIn(BRAND, out.lower())
                self.assertNotRegex(out.lower(), r"success|\b(grootboek|ledger|registre)\b")
                self.assertNotIn("?", re.sub(r"https?://\S+", "", out))  # nothing unknown in a full ledger
                self.assertEqual(one_term_sums(out), [], lang)
        self.assertNotRegex(self.reports["nl"], r"(?i)\b(u|uw)\b")
        for lang, text in self.reports.items():  # a note prints as the user's own words, one bullet, no key
            self.assertIn("\n- 52 days\n", text)
            self.assertNotIn("dso", text)
        for lang, text in self.reports.items():
            self.assertIn("- " + hours.T[lang]["m_overlap"], text)
            self.assertIn("- " + hours.T[lang]["a_answers"], text)

    def test_french_typography(self):
        text = self.reports["fr"]
        text = re.sub(r"«[^»]*»|“[^”]*”|https?://\S+", "", text)  # quotes and links are not ours to change
        self.assertNotRegex(text, r"\S: ")
        self.assertNotRegex(text, r"\d%")
        self.assertNotRegex(text, r"€\d")  # money is 1 790,40 €
        self.assertIn("Total : 85,6 h", text)
        self.assertIn("28 % du total", text)
        self.assertIn("29 754,00 €", text)
        self.assertIn("| Étape | Tâche | Méthode actuelle | Qui | Nombre par mois | Minutes par opération |", text)

    def test_automated_only_with_a_steps_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "claims.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Claims\n\n## Lines\n\n"
                        "### dunning\n- steps: chase\n- en: “Dunning line.”\n- source: https://www.twikey.com/\n\n"
                        "### core-refund\n- methods: sdd_core\n- en: “Refund line.”\n"
                        "- source: https://www.twikey.com/start/index.html\n\n"
                        "### demo\n- en: Demo https://www.twikey.com/demo.html?utm_source=x\n"
                        "- nl: Demo https://www.twikey.com/be/demo.html?utm_source=x\n"
                        "- fr: Démo https://www.twikey.com/fr/demo.html?utm_source=x\n- source: https://www.twikey.com/demo.html\n\n"
                        "## Pricing page\n\n- en: https://www.twikey.com/pricing.html\n")
            with mock.patch.object(hours, "CLAIMS", path):
                en = hours.cmd_report(self.led, "en", today=TODAY)
                nl = hours.cmd_report(self.led, "nl", today=TODAY)
                fr = hours.cmd_report(self.led, "fr", today=TODAY)
        final = en.split("## Where Twikey fits")[1]
        self.assertIn("22.7 of 85.6 hours.", final)  # one step: no "(22.7)"
        self.assertEqual(re.findall(r"^\*\*(\d)\.", final, re.M), ["4"])
        self.assertNotIn("Refund line", final)  # a line without `steps` never makes a step count
        self.assertEqual(re.findall(r"^(\d)\. .*\*$", en, re.M), [])  # no stars in the map
        # A line with no Dutch or French text prints in English, labelled as such.
        self.assertIn("Twikey (Engels): “Dunning line.” (https://www.twikey.com/)", nl)
        self.assertIn("Twikey (anglais) : “Dunning line.” (https://www.twikey.com/)", fr)
        self.assertNotIn("pricing", en + nl + fr)  # no pricing page, no package names

    def test_empty_sections(self):
        led = build(["task.refunds.main.count=5", "task.refunds.main.minutes=12"])
        text = hours.cmd_report(led, "en", today=TODAY)
        final = text.split("## Where Twikey fits")[1]
        self.assertIn(hours.T["en"]["none_steps"], final)  # refunds: no Twikey line lists it
        self.assertNotIn("0.0 of", final)
        led = build(["task.match.main.count=60", "task.match.main.minutes=10"])
        text = hours.cmd_report(led, "en", today=TODAY)
        self.assertIn("The one step you answered takes 10.0 hours a month: 0.06 FTE.", text)  # no hourly cost
        self.assertIn("- Not asked yet: 1. Send the invoice or payment request, 2. Take in payments", text)
        self.assertIn("- Total hours a month: 10.0 h\n", text)  # one term: no "10.0 = 10.0"
        self.assertIn("10.0 of 10.0 hours.", text)
        self.assertEqual(re.findall(r"^(\d)\. .*\*$", text, re.M), [])  # no stars in the map

    def test_total_sentence_when_steps_are_missing(self):
        led = build(SAMPLE[:2] + ["task.match.main.count=60", "task.match.main.minutes=10",
                                  "task.chase.main.count=30", "task.chase.main.minutes=4"])
        expect = {"en": "The two steps you answered take 12.0 hours a month: 0.07 FTE and €540.00 a month at your "
                        "hourly cost.",
                  "nl": "De twee stappen die je beantwoordde kosten 12,0 uur per maand: 0,07 VTE en €540,00 per "
                        "maand aan je uurkost.",
                  "fr": "Les deux étapes renseignées prennent 12,0 heures par mois : 0,07 ETP et 540,00 € par mois à "
                        "votre coût horaire."}
        for lang, sentence in expect.items():
            self.assertIn("\n%s\n" % sentence, hours.cmd_report(led, lang, today=TODAY))
        led = build(SAMPLE[:2] + ["task.%s.main.count=1" % s for s in hours.STEPS[:7]]
                    + ["task.%s.main.minutes=6" % s for s in hours.STEPS[:7]])
        self.assertIn("The seven steps you answered take 0.7 hours a month", hours.cmd_report(led, "en", today=TODAY))
        self.assertIn("De zeven stappen", hours.cmd_report(led, "nl", today=TODAY))
        self.assertIn("Les sept étapes", hours.cmd_report(led, "fr", today=TODAY))
        self.assertIn("Getting paid takes 85.6 hours a month", self.reports["en"])

    def test_no_tasks(self):
        text = hours.cmd_report(hours.empty_ledger(), "nl", today=TODAY)
        self.assertTrue(text.endswith("Nog geen taken opgeslagen."))

    def test_final_section_order(self):
        claims = hours.load_claims()[0]
        for lang, text in self.reports.items():
            t, demo = hours.T[lang], claims["demo"][lang]
            self.assertEqual(text.count(t["auto_note"]), 1, lang)  # once, at the end
            final = text.split("## " + t["fits"])[1]
            order = [final.index("**2."), final.index(t["auto_sum"].split("{")[0]), final.index(t["auto_note"]),
                     final.index(claims["card-chargebacks"].get(lang, claims["card-chargebacks"]["en"])),
                     final.index(demo), final.index("---")]
            self.assertEqual(order, sorted(order), lang)  # steps, their sum, the note, method lines, demo, footer

    def test_twikey_only_in_final_section(self):
        for lang, text in self.reports.items():
            t = hours.T[lang]
            body, final = text.split("## " + t["fits"])
            self.assertNotIn("Twikey", body, lang)
            self.assertNotIn("twikey.com", body, lang)
            self.assertNotRegex(text, r"(Pricing page|prijspagina|page des tarifs)")  # no package rows anywhere
            self.assertNotRegex(text, r"(?m)^\* ")  # no map footnote
            self.assertNotIn("Twikey", hours.cmd_process(self.led, lang))
            methods = hours.cmd_methods(self.led, lang)
            body, final = methods.split("## " + t["fits"])
            self.assertNotIn("Twikey", body, lang)
            self.assertIn("%s. Twikey" % hours.METHOD_LABEL[lang]["card"], final)  # each prefixed with the method
        nl, fr = self.reports["nl"], self.reports["fr"]
        self.assertIn("## Waar Twikey past", nl)
        self.assertIn("## Où Twikey intervient", fr)

    def test_mix_lines(self):
        en = hours.cmd_report(self.led, "en", today=TODAY)
        self.assertIn("- Hours a month by how the work is done today: by hand 24.0 + 6.0 + 16.7 + 2.5 + 2.0 + 1.7 = "
                      "52.9 h. Partly automatic 20.0 + 6.7 + 6.0 = 32.7 h.", en)  # 52.9 + 32.7 = 85.6
        self.assertIn("- Hours a month that grow with volume: 85.6 − 6.0 = 79.6 h. At twice the volume: "
                      "164.9 − 6.0 = 158.9 h.", en)  # the weekly forecast (6.0 h) does not grow
        self.assertIn("- Uren per maand volgens hoe het werk nu gebeurt: handmatig ", self.reports["nl"])
        self.assertIn("- Heures par mois qui croissent avec le volume : 85,6 − 6,0 = 79,6 h.", self.reports["fr"])
        led = build(["task.match.main.count=60", "task.match.main.minutes=10", "task.chase.main.count=6",
                     "task.chase.main.minutes=10", "task.chase.main.mode=automatic"])
        lines = hours.mix_lines(led, "en")
        self.assertEqual(lines[0], "- Hours a month by how the work is done today: automatic 1.0 h. How not given "
                                   "10.0 h.")
        self.assertEqual(lines[1], "- Hours a month that grow with volume: 11.0 h. At twice the volume: 22.0 h.")
        self.assertIn(lines[1], hours.cmd_process(led, "en"))

    def test_switch_note_under_the_whatif(self):
        for lang in hours.LANGS:
            note = "- " + hours.T[lang]["m_switch_note"]
            self.assertIn(note, self.reports[lang])
            heading, body = hours.cmd_methods(self.led, lang).split("### ")[-1].split("\n\n")[:2]
            self.assertTrue(body.endswith("\n" + note), (lang, body[-200:]))  # the last line of the what-if
        led = build(SAMPLE + ["whatif=card:sdd_core:50"])  # cannot be calculated: no note
        self.assertNotIn(hours.T["en"]["m_switch_note"], hours.cmd_methods(led, "en"))

    def test_footer_version(self):
        self.assertIn("Made with Payment Hours by Twikey, version %s." % hours.VERSION, self.reports["en"])
        self.assertIn("Gemaakt met Payment Hours van Twikey, versie %s." % hours.VERSION, self.reports["nl"])
        self.assertIn("Réalisé avec Payment Hours par Twikey, version %s." % hours.VERSION, self.reports["fr"])

    def test_zero_total(self):
        led = build(["task.match.main.count=0", "task.match.main.minutes=4", "task.chase.main.count=0",
                     "task.chase.main.minutes=5"])
        for lang in hours.LANGS:
            text = hours.cmd_report(led, lang, today=TODAY)
            found = text.split("## " + hours.T[lang]["found"])[1].split("\n## ")[0]
            self.assertNotRegex(found, r"^\d\. ", lang)  # no ranked lines
            self.assertNotIn("0,0 ÷ 0,0" if lang != "en" else "0.0 ÷ 0.0", text)
            self.assertNotRegex(text, r"(?<![\d,.])0 ?% (of the total|van het totaal|du total)")
            self.assertEqual(one_term_sums(text), [], lang)

    def test_one_method_no_one_term_sums(self):
        led = build(SAMPLE[:2] + ["task.match.main.count=60", "task.match.main.minutes=10",
                                  "payments.per_month=100", "payments.avg_amount=500",
                                  "method.transfer.share=35", "method.transfer.minutes=2",
                                  "method.transfer.days=38"])
        for lang in hours.LANGS:
            for out in (hours.cmd_methods(led, lang), hours.cmd_report(led, lang, today=TODAY),
                        hours.cmd_process(led, lang)):
                self.assertEqual(one_term_sums(out), [], lang)
        text = hours.cmd_methods(led, "en")
        self.assertIn("The shares add up to 35%, not 100%. Check the mix.", text)
        self.assertIn("Average days until the money is in, weighted by share: 38\n", text)
        self.assertNotIn("All methods, per year", text)  # no fees given: no euro lines, only time cost
        self.assertEqual(one_term_sums("Total: 6.0 = 6.0 h, 35% = 35%, 0,00 € = 0,00 €"),
                         ["6.0 = 6.0", "35% = 35%", "0,00 € = 0,00 €"])

    def test_deterministic(self):
        self.assertEqual(hours.cmd_report(self.led, "fr", today=TODAY), self.reports["fr"])


if __name__ == "__main__":
    unittest.main()
