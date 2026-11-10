import datetime as dt
import json
import os
import unittest

from tests import helpers  # noqa: F401
from xray import checks
from xray.common import DATA_DIR

D = dt.date


def coll(date, status="collected", code="M001", cust="C001", amount=100.0, reason=None, account="A001", **kw):
    c = {"status": status, "date": date, "date_kind": "collection", "amount": amount, "customer": cust,
         "mandate": code, "account": account, "scheme": "CORE", "reason_code": reason}
    c.update(kw)
    return c


def line(i, date, amount, cust=None, ogm=None, status=None):
    return {"id": "B%04d" % i, "date": date, "amount": amount, "customer": cust, "ogm": ogm,
            "ogm_status": status or ("valid" if ogm else "absent")}


class DecodeTest(unittest.TestCase):
    def test_grouping_and_categories(self):
        cs = [coll("2026-08-04", "failed", reason="AM04", amount=10.0),
              coll("2026-08-04", "failed", reason="AM04", amount=15.5),
              coll("2026-08-05", "failed", reason="MD01", amount=20.0, scheme="B2B"),
              coll("2026-08-05", "failed", reason="MD01", amount=30.0, scheme="CORE"),
              coll("2026-09-05", "failed", reason="MD06", amount=5.0, cust="C002"),
              coll("2026-09-07", "failed", reason="XX99", amount=1.0, cust="C003"),
              coll("2026-09-07", "failed", reason=None, amount=2.0, cust="C003", date_kind="booked"),
              coll("2026-09-08", "failed", reason="FF01", amount=100.0, cust="C004"),
              coll("2026-09-09", "collected", amount=999.0)]
        d = checks.decode(cs)
        self.assertEqual(d["total"], {"count": 8, "amount": 183.5})
        by = {r["code"]: r for r in d["by_code"]}
        self.assertEqual((by["AM04"]["count"], by["AM04"]["amount"]), (2, 25.5))
        self.assertEqual(by["MD01"]["categories"], {"conversation": 1, "new_mandate": 1})
        self.assertFalse(by["XX99"]["known"])
        self.assertEqual(by["XX99"]["meaning"], "unknown code")
        self.assertEqual(d["by_category"]["new_attempt"]["count"], 2)
        self.assertEqual(d["by_category"]["own_setup"]["count"], 1)
        self.assertEqual(d["by_category"]["unknown"]["count"], 1)
        self.assertEqual(d["by_category"]["unreadable"]["count"], 1)
        self.assertEqual(d["unknown_codes"], ["XX99"])
        self.assertEqual(d["failures_by_day"], {"4": 2, "5": 3, "7": 1, "8": 1})
        self.assertEqual(d["days_of_month_return_booked"], {"7": 1})
        self.assertEqual(d["repeat_customers"], {"C001": 4, "C003": 2})
        self.assertEqual(d["basis"], "Counted from the direct debits returned or refunded on your camt.053 bank "
                                     "statements.")

    def test_no_failures_is_a_count_of_zero(self):
        d = checks.decode([coll("2026-09-09"), coll("2026-10-09")])
        self.assertEqual(d["total"], {"count": 0, "amount": 0.0})
        self.assertEqual((d["by_code"], d["by_category"]), ([], {}))
        self.assertEqual(checks.decode([])["days_of_month_overall"], None)

    def test_unknown_code_is_called_unknown(self):
        d = checks.decode([coll("2026-08-04", "failed", reason="SL11")])
        r = d["by_code"][0]
        self.assertEqual((r["meaning"], r["known"], r["page"]), ("unknown code", False, None))

    def test_epc_code_outside_twikeys_list(self):
        d = checks.decode([coll("2026-08-04", "failed", reason="ED05")])
        r = d["by_code"][0]
        self.assertEqual((r["meaning"], r["known"], r["page"]), ("Settlement of the collection failed", False, None))
        self.assertIn("EPC173-14", r["meaning_source"])
        self.assertEqual(list(d["by_category"]), ["bank"])
        self.assertEqual(d["unknown_codes"], ["ED05"])
        self.assertNotIn("Twikey's reason-code list", checks.CATEGORY_TEXTS["en"]["unknown"])

    def test_reason_not_on_the_statement_and_proprietary_reason(self):
        d = checks.decode([coll("2026-08-04", "failed", reason=None, reason_missing=True),
                           coll("2026-08-05", "failed", reason=None, reason_proprietary=True, amount=40.0)])
        self.assertEqual(sorted(r["label"] for r in d["by_code"]),
                         ["proprietary reason (not shown)", "reason not on the statement"])
        self.assertEqual(list(d["by_category"]), ["unreadable"])

    def test_worth_a_new_attempt(self):
        d = checks.decode([coll("2026-08-04", "failed", reason="MS03")])
        self.assertTrue(d["by_category"]["new_attempt"]["meaning"].startswith("Worth a new attempt"))

    def test_failure_rate_per_collection_day(self):
        def c(date, n, status="collected", **kw):
            return coll(date, status, code="M%d" % n, cust="C%d" % n, **kw)
        cs = ([c("2026-08-04", n, e2e="a%d" % n) for n in range(1, 10)]          # nine collected on Aug 4
              + [c("2026-08-04", 10, e2e="x"), c("2026-08-04", 10, "failed", reason="AM04", e2e="x")]  # returned
              + [c("2026-08-18", 10, e2e="x2")]                                   # its retry: left out
              + [c("2026-08-04", 11, e2e="r"), c("2026-08-04", 11, "failed", reason="MD06", e2e="r")]  # refunded
              + [c("2026-09-04", n, e2e="s%d" % n) for n in range(1, 5)]          # four collected on Fri Sep 4
              + [c("2026-10-05", n, e2e="o%d" % n) for n in range(1, 4)]          # Mon Oct 5: the Sunday 4th run
              + [c("2026-08-20", 20), c("2026-08-20", 21)]                        # day 20: one month only
              + [c("2026-03-04", 12, "failed", reason="AM04")])                   # a month without collections
        d = checks.decode(cs)
        # days with presentations in at least two months only: day 20 (August only) is left out. The retry of the
        # 18th is left out. October 5 counts as day 4: October 4 was a Sunday and the 4th is the usual day.
        self.assertEqual(d["days_of_month"], {"4": {"failed": 2, "presented": 18, "months": 3, "rate_pct": 11.1,
                                                    "moved_runs": 1, "qualifies": False}})
        self.assertEqual(d["days_of_month_overall"], {"failed": 2, "presented": 20, "rate_pct": 10.0})
        self.assertEqual(d["days_of_month_period"], {"from": "2026-08", "to": "2026-10", "months": 3})
        self.assertEqual(d["failures_by_day"], {"4": 3})
        self.assertEqual(checks.day_stats(cs)["retries_left_out"], 1)

    def test_a_retry_with_the_same_end_to_end_reference_is_left_out(self):
        cs = [coll("2026-08-04", "failed", reason="AM04", e2e="E1"), coll("2026-08-11", e2e="E1"),
              coll("2026-09-04", code="M2", cust="C2")]
        days = checks.day_stats(cs)["days"]
        self.assertNotIn("11", days)
        self.assertEqual(days["4"]["presented"], 2)

    def test_reason_code_links_in_the_users_language(self):
        cs = [coll("2026-08-04", "failed", reason="AM04")]
        self.assertEqual(checks.decode(cs, "nl")["by_code"][0]["page"],
                         "https://www.twikey.com/be/product/r-codes/AM04.html")
        self.assertEqual(checks.decode(cs, "fr")["by_code"][0]["page"],
                         "https://www.twikey.com/fr/product/r-codes/AM04.html")
        self.assertEqual(checks.decode(cs, "en")["by_code"][0]["page"],
                         "https://www.twikey.com/product/r-codes/AM04.html")

    def test_languages(self):
        cs = [coll("2026-08-04", "failed", reason="AM04")]
        self.assertTrue(checks.decode(cs, "nl")["by_code"][0]["meaning"])
        self.assertTrue(checks.decode(cs, "fr")["by_code"][0]["meaning"])
        self.assertNotEqual(checks.decode(cs, "nl")["by_code"][0]["meaning"],
                            checks.decode(cs, "en")["by_code"][0]["meaning"])

    def test_every_twikey_code_has_a_category(self):
        codes = checks.rcodes("en")
        self.assertEqual(len(codes), 25)
        for code in codes:
            self.assertIn(checks.category(code, "CORE", codes), checks.CATEGORIES)
            self.assertNotEqual(checks.category(code, "CORE", codes), "unknown", code)


class PaymentsTest(unittest.TestCase):
    def test_groups_and_payments_to_book_by_hand(self):
        bank = [line(1, "2026-08-03", 100.0, "C1", "R0001"), line(2, "2026-08-04", 50.0, "C2", "R0002"),
                line(3, "2026-09-03", 20.0, "C3", status="invalid"), line(4, "2026-09-04", 30.0, "C3"),
                line(5, "2026-10-01", 40.0, "C3"), line(6, "2026-10-02", 70.0, "C4", status="other"),
                line(7, "2026-10-03", 80.0, None)]
        d = checks.payments(bank)
        self.assertEqual(d["credit_lines"], {"count": 7, "amount": 390.0})
        self.assertEqual({k: v["count"] for k, v in d["groups"].items()},
                         {"valid": 2, "invalid": 1, "other": 1, "absent": 3})
        self.assertEqual(d["groups"]["absent"]["customers"], ["C3"])
        h = d["by_hand"]
        self.assertEqual((h["count"], h["amount"], h["share_pct"], h["per_month"], h["customers"]),
                         (4, 170.0, 57.1, 1.3, ["C3"]))
        self.assertEqual(d["period"], {"from": "2026-08-03", "to": "2026-10-03", "months": 3})
        self.assertEqual(d["twikey"]["id"], "unmatched-payments")

    def test_no_incoming_payments(self):
        d = checks.payments([])
        self.assertEqual((d["credit_lines"]["count"], d["by_hand"]["share_pct"], d["by_hand"]["per_month"]),
                         (0, None, None))


class StepsTest(unittest.TestCase):
    def test_checklists_come_from_the_data_file(self):
        with open(os.path.join(DATA_DIR, "manual_steps.json"), encoding="utf-8") as f:
            data = json.load(f)
        for lang in ("en", "nl", "fr"):
            self.assertEqual(set(data[lang]["items"]), set(checks.STEP_ITEMS), lang)
            r = checks.steps([], [], D(2026, 10, 31), lang)
            for i in r["items"]:
                want = data[lang]["items"][i["id"]]["checklist"]
                self.assertEqual(i["checklist"], want)
                self.assertEqual(i["steps_each"], len(want))
            # every item type is listed, with zero when the statements hold none
            self.assertEqual(sorted(i["id"] for i in r["items"]), sorted(checks.STEP_ITEMS))
            self.assertEqual((r["total_items"], r["total_steps"], r["per_month_total"]), (0, 0, None))
        # the same number of steps in every language
        for k in checks.STEP_ITEMS:
            self.assertEqual(len({len(data[lang]["items"][k]["checklist"]) for lang in ("en", "nl", "fr")}), 1, k)

    def test_counts_and_totals(self):
        cs = [coll("2026-09-01", "failed", reason="AM04"), coll("2026-10-01", "failed", reason="MS02"),
              coll("2026-10-01", "failed", reason="XX99")]
        bank = [line(1, "2026-09-20", 77.0, "C9"), line(2, "2026-10-20", 10.0, "C8", "R0001")]
        r = checks.steps(cs, bank, D(2026, 10, 31))
        by = {i["id"]: i for i in r["items"]}
        self.assertEqual(by["failed_new_attempt"]["count"], 1)
        self.assertEqual(by["failed_conversation"]["count"], 1)
        self.assertEqual(by["failed_unknown"]["count"], 1)  # an unknown code: ask the bank
        self.assertEqual(by["book_by_hand"]["count"], 1)    # no structured communication
        self.assertEqual(by["failed_new_attempt"]["months"], 2)
        self.assertEqual(by["failed_new_attempt"]["per_month"], 0.5)
        self.assertEqual(r["total_items"], 4)
        self.assertEqual(r["total_steps"], sum(i["count"] * i["steps_each"] for i in r["items"]))
        self.assertEqual(r["items"][0]["id"], "failed_new_attempt")  # biggest steps_total first
        self.assertEqual([t["id"] for t in r["twikey"]], ["failure-decoder", "unmatched-payments"])

    def test_per_month_totals_are_rounded_once(self):
        # three item types, one item each over three months: 0.3 each when shown, 1.0 together
        cs = [coll("2026-08-04", "failed", reason="AM04"), coll("2026-09-04", "failed", reason="MS02"),
              coll("2026-10-05", "failed", reason="ED05")]
        r = checks.steps(cs, [], D(2026, 10, 31))
        shown = [i["per_month"] for i in r["items"] if i["per_month"]]
        self.assertEqual(shown, [0.3, 0.3, 0.3])
        self.assertEqual(r["per_month_total"], 1.0)
        self.assertEqual(r["per_month_steps_total"], round((4 + 4 + 2) / 3.0, 1))


class GoliveTest(unittest.TestCase):
    def test_facts_from_the_statements(self):
        cs = ([coll("2026-%02d-04" % m, cust="C%d" % n, code="M%d" % n, scheme="CORE", e2e="%d-%d" % (m, n))
               for m in (8, 9) for n in range(1, 4)]
              + [coll("2026-%02d-04" % m, cust="C9", code="M9", scheme="B2B", e2e="%d-9" % m) for m in (8, 9)]
              + [coll("2026-09-04", "failed", cust="C1", code="M1", reason="AM04", e2e="9-1")])  # returned
        bank = [line(1, "2026-08-10", 10.0, "C5", "R0001"), line(2, "2026-09-10", 10.0, "C6"),
                line(3, "2026-09-11", 10.0, "C1")]
        g = checks.golive(cs, bank, "Exact Online")
        self.assertEqual((g["direct_debit_customers"], g["core_customers"], g["b2b_customers"], g["mandates"]),
                         (4, 3, 1, 4))
        self.assertEqual((g["collections_per_month"], g["failed_per_month"], g["failure_rate_pct"]), (4.0, 1.0, 12.5))
        self.assertEqual((g["payers_by_transfer"], g["transfers_per_month"], g["by_hand_per_month"]), (2, 1.5, 1.0))
        self.assertEqual(g["tool"]["listed_as"], ["Exact"])
        self.assertEqual([t["id"] for t in g["twikey"]], list(checks.GOLIVE_LINES))
        self.assertEqual(g["demo"]["id"], "demo")


def failed(date, reason="AM04", cust="C001", code="M001", amount=100.0, **kw):
    return coll(date, "failed", code=code, cust=cust, amount=amount, reason=reason, **kw)


class MonthHelpers:
    ON = D(2026, 10, 31)
    TODAY = D(2026, 11, 2)

    def prep(self, collections=(), bank=(), since=90, lang="en", mail_lang=None, today=None):
        from xray import month
        return month.prepare(list(collections), list(bank), self.ON, since, lang, mail_lang, today or self.TODAY)

    def render(self, r):
        from xray import month
        return month.render(r, today=self.TODAY)

    @staticmethod
    def runs(day, months, n, failed_first=0, prefix="M"):
        """n collections on this day in each of these months (2026), each on its own mandate. The first
        failed_first of the first month failed."""
        cs = []
        for m in months:
            for i in range(n):
                cs.append(coll("2026-%02d-%02d" % (m, day), cust="C%s%d" % (prefix, i), code="%s%d" % (prefix, i)))
        for i in range(failed_first):
            cs[i] = dict(cs[i], status="failed", reason_code="AM04")
        return cs


class MonthTest(MonthHelpers, unittest.TestCase):
    def test_a_failure_collected_later_is_left_out(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", e2e="E0001"),
              coll("2026-09-18", cust="C1", code="M1"),                            # same mandate and amount
              failed("2026-10-05", cust="C2", code="M2", e2e="E0002"),
              coll("2026-10-20", cust="C2", code="M2", amount=55.0, e2e="E0002"),  # same end-to-end reference
              failed("2026-10-05", cust="C3", code="M3"),
              coll("2026-10-05", cust="C3", code="M3")]                            # the original presentation
        r = self.prep(cs)
        self.assertEqual([a["customer"] for a in r["new_attempts"]], ["C3"])
        self.assertEqual(r["closed"], {"collected_later": 2, "paid_by_transfer": 0})

    def test_next_months_regular_collection_closes_nothing(self):
        cs = [failed("2026-08-04", cust="C1", code="M1"), coll("2026-09-04", cust="C1", code="M1")]
        self.assertEqual(len(self.prep(cs)["new_attempts"]), 1)

    def test_a_later_payment_by_transfer_from_the_customer_covers_it(self):
        cs = [failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(cs, [line(1, "2026-10-12", 100.0, "C1")])
        self.assertEqual((r["new_attempts"], r["closed"]["paid_by_transfer"]), ([], 1))
        self.assertIn("Left out because they are no longer owed: one (a later collection, or a payment by transfer "
                      "from that customer since).", self.render(r))
        # a payment before the failure, a smaller one, or one from someone else covers nothing
        for b in (line(1, "2026-10-01", 100.0, "C1"), line(1, "2026-10-12", 60.0, "C1"),
                  line(1, "2026-10-12", 100.0, "C2")):
            self.assertEqual(len(self.prep(cs, [b])["new_attempts"]), 1)
        # one payment covers one debt
        two = cs + [failed("2026-10-05", cust="C1", code="M2")]
        self.assertEqual(len(self.prep(two, [line(1, "2026-10-12", 100.0, "C1")])["new_attempts"]), 1)

    def test_window_and_categories(self):
        cs = [failed("2026-07-01"), failed("2026-10-01", reason="MS02", cust="C2", code="M2"),
              failed("2026-10-01", reason="MD01", cust="C3", code="M3", scheme="CORE")]
        r = self.prep(cs)
        self.assertEqual(r["new_attempts"], [])  # July is outside the 90 days
        self.assertEqual([(m["customer"], m["reason"]) for m in r["mails"]],
                         [("C2", "conversation"), ("C3", "new_mandate")])
        self.assertEqual(len(self.prep(cs, since=200)["new_attempts"]), 1)

    def test_suggested_day_needs_20_collections_over_two_months_on_two_days(self):
        from xray import month
        # day 4: 24 presented over two months, 3 failed. Day 18: 20 presented over two months, none failed.
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 10, prefix="B")
        day, info = month.suggested_day(cs, self.ON, self.TODAY)
        self.assertEqual((day["day"], day["rate_pct"], day["presented"], day["months"], day["failed"]),
                         (18, 0.0, 20, 2, 0))
        self.assertEqual((day["qualifying_days"], day["overall_rate_pct"]), (2, 6.8))  # 3 of 44
        # at least 14 days after the later of the as-of date and today: November 16, so the 18th of November
        self.assertEqual((day["earliest"], day["date"]), ("2026-11-16", "2026-11-18"))
        self.assertIn("14 days", day["notice"])
        # a later today moves the date: December 3 + 14 = December 17, so the 18th of December
        day, _ = month.suggested_day(cs, self.ON, D(2026, 12, 3))
        self.assertEqual(day["date"], "2026-12-18")
        # an as-of date after today counts from the as-of date
        day, _ = month.suggested_day(cs, self.ON, D(2026, 1, 1))
        self.assertEqual(day["date"], "2026-11-18")

    def test_no_suggested_day_on_a_thin_basis(self):
        from xray import month
        # day 18 with 2 of 2 collected is no basis: it never qualifies, so only day 4 is left
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 1, prefix="B")
        day, info = month.suggested_day(cs, self.ON, self.TODAY)
        self.assertIsNone(day)
        self.assertEqual((info["qualifying_days"], info["no_day_reason"]), ([4], "too_little_history"))
        # 20 collections in one month: one month is no pattern
        day, info = month.suggested_day(self.runs(4, (8, 9), 12, prefix="A") + self.runs(18, (9,), 20, prefix="B"),
                                        self.ON, self.TODAY)
        self.assertIsNone(day)
        # two days qualify, but the best one fails as often as all collections together
        cs = self.runs(4, (8, 9), 10, failed_first=2, prefix="A") + self.runs(18, (8, 9), 10, failed_first=2,
                                                                            prefix="B")
        day, info = month.suggested_day(cs, self.ON, self.TODAY)
        self.assertIsNone(day)
        self.assertEqual(info["no_day_reason"], "no_better_day")
        # without a day, the new-attempt mail holds the literal placeholder, never a computed date
        r = self.prep([failed("2026-10-05")])
        self.assertIsNone(r["suggested_day"])
        self.assertIsNone(r["new_attempts"][0]["new_date"])
        self.assertIn("[date of the new collection]", r["mails"][0]["body"])
        self.assertIn("Too little history", self.render(r))

    def test_a_shifted_run_counts_under_its_usual_day(self):
        from xray import month
        # day 25: August 25 and September 25, and Monday October 26 (October 25 was a Sunday)
        cs = (self.runs(7, (8, 9, 10), 8, failed_first=4, prefix="A")
              + [coll("2026-%s" % d, cust="CB%d" % i, code="B%d" % i) for d in ("08-25", "09-25", "10-26")
                 for i in range(7)])
        day, _ = month.suggested_day(cs, self.ON, self.TODAY)
        self.assertEqual((day["day"], day["presented"], day["months"]), (25, 21, 3))
        self.assertEqual(day["date"], "2026-11-25")
        # without the shift, day 25 has 14 collections and does not qualify
        cs2 = [c for c in cs if c["date"] != "2026-10-26"]
        self.assertIsNone(month.suggested_day(cs2, self.ON, self.TODAY)[0])

    def test_retries_stay_out_of_the_day_statistics(self):
        from xray import month
        # 20 retries on the 18th, each 14 days after a failure on the 4th: not a collection day of its own
        cs = self.runs(4, (8, 9), 10, failed_first=10, prefix="A") + self.runs(4, (8, 9), 10, prefix="C")
        cs += [coll("2026-08-18", cust="CA%d" % i, code="A%d" % i) for i in range(10)]
        cs += self.runs(18, (9,), 10, prefix="A")  # September 18: retries are only for August failures
        stats = month.checks.day_stats(cs)
        self.assertEqual(stats["retries_left_out"], 10)
        self.assertNotIn("18", {k for k, v in stats["days"].items() if v["months"] >= 2})

    def test_suggested_date_is_a_working_day(self):
        from xray import month
        self.assertEqual(month.next_day_of_month(31, D(2026, 10, 31)), D(2026, 12, 31))  # November has no 31st
        self.assertEqual(month.working_day(D(2026, 11, 21)), D(2026, 11, 23))  # Saturday -> Monday
        self.assertEqual(month.working_day(D(2026, 12, 25)), D(2026, 12, 28))  # Christmas, Boxing Day, Sunday
        self.assertEqual(month.working_day(D(2027, 3, 26)), D(2027, 3, 30))   # Good Friday, Easter Monday 2027

    def test_every_new_date_gives_14_days_notice(self):
        from xray import month
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 10, prefix="B")
        for k in range(0, 400, 3):
            today = D(2026, 9, 1) + dt.timedelta(days=k)
            day, _ = month.suggested_day(cs, self.ON, today)
            date = dt.date.fromisoformat(day["date"])
            self.assertGreaterEqual((date - max(self.ON, today)).days, month.NOTICE_DAYS, today)
            self.assertEqual(month.working_day(date), date, today)
            self.assertLess((date - max(self.ON, today)).days, month.NOTICE_DAYS + 35, today)

    def test_placeholders_filled_in_every_language(self):
        cs = [failed("2026-10-05", cust="C1", code="M1"), failed("2026-10-05", "MD06", cust="C2", code="M2"),
              failed("2026-10-05", "AC04", cust="C3", code="M3"),
              failed("2026-10-05", "MD01", cust="C4", code="M4", scheme="B2B")]
        for lang in ("en", "nl", "fr"):
            r = self.prep(cs, mail_lang=lang)
            texts = [m["subject"] + m["body"] for m in r["mails"]]
            self.assertEqual(len(texts), 4)
            for t in texts:
                self.assertNotRegex(t, r"[{}]", (lang, t))

    def test_closing_without_any_data_names_no_empty_period(self):
        r = self.prep()
        self.assertEqual(r["closing"]["text"], "Claude prepared this once, from your bank statements. Nothing was "
                                               "sent and no bank file was written.")
        self.assertEqual(r["counts"], {"new_attempts": 0, "mails": 0})


class MonthMailTest(MonthHelpers, unittest.TestCase):
    """One debt per collection, B2B registration, one mail per customer by priority, plurals, wording."""

    def test_repeated_failures_are_one_debt(self):
        cs = [failed("2026-10-05", cust="C1", code="M1", e2e="E1"), failed("2026-10-19", cust="C1", code="M1", e2e="E2")]
        r = self.prep(cs)
        self.assertEqual(len(r["new_attempts"]), 1)
        a = r["new_attempts"][0]
        self.assertEqual((a["amount"], a["failure_date"], a["first_failure_date"], a["attempts"]),
                         (100.0, "2026-10-19", "2026-10-05", 2))
        self.assertEqual(len(r["mails"]), 1)
        self.assertEqual(r["mails"][0]["amount"], 100.0)  # never 200: one debt, counted once
        self.assertIn("€100.00", r["mails"][0]["subject"])
        self.assertIn("- €100.00, presented twice, last on October 19, 2026", r["mails"][0]["body"])
        self.assertIn("€100.00, failed twice, last on October 19, 2026.", self.render(r))
        # the same end-to-end reference is one debt too, even more than three weeks later
        cs = [failed("2026-09-04", cust="C1", code="M1", e2e="E1"), failed("2026-10-05", cust="C1", code="M1", e2e="E1")]
        self.assertEqual([a["attempts"] for a in self.prep(cs)["new_attempts"]], [2])
        # a month later, the same amount on the same mandate is the next collection: two debts
        cs = [failed("2026-09-04", cust="C1", code="M1"), failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(cs)
        self.assertEqual([a["attempts"] for a in r["new_attempts"]], [1, 1])
        self.assertEqual(r["mails"][0]["amount"], 200.0)

    def test_no_new_attempt_on_a_mandate_that_later_got_md01(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="AM04"),
              failed("2026-10-05", cust="C1", code="M1", reason="MD01", scheme="CORE")]
        r = self.prep(cs)
        self.assertEqual(r["new_attempts"], [])
        self.assertEqual([(m["reason"], len(m["items"])) for m in r["mails"]], [("new_mandate", 2)])
        # on a B2B mandate, a later MD01 means the customer's bank does not know it: register it
        cs = [dict(c, scheme="B2B") for c in cs]
        self.assertEqual([m["reason"] for m in self.prep(cs)["mails"]], ["b2b_register"])

    def test_md01_on_a_b2b_mandate_asks_to_register_it(self):
        cs = [failed("2026-10-05", cust="C1", code="M1", reason="MD01", scheme="B2B")]
        for lang, want in (("en", "Your bank rejected the following direct debit, because B2B mandate M1 is not "
                                  "registered there:"),
                           ("nl", "omdat B2B-mandaat M1 daar niet geregistreerd is"),
                           ("fr", "parce que le mandat B2B M1 n'y est pas enregistré")):
            m = self.prep(cs, mail_lang=lang)["mails"][0]
            self.assertEqual(m["reason"], "b2b_register")
            self.assertIn(want, m["body"])
            self.assertNotRegex(m["body"], r"refunded or refused|terugbetaald of geweigerd|remboursé ou refusé")
        self.assertIn("Could you ask your bank to register it? Then we will present the collection of €100.00 again.",
                      self.prep(cs)["mails"][0]["body"])
        # on a Core mandate MD01 still needs a new mandate
        self.assertEqual(self.prep([dict(cs[0], scheme="CORE")])["mails"][0]["reason"], "new_mandate")

    def test_one_mail_per_customer_by_priority(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="MS02"), failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(cs)
        self.assertEqual([(m["customer"], m["reason"], m["amount"]) for m in r["mails"]], [("C1", "conversation", 200.0)])
        # conversation > new_mandate > b2b_register > new_attempt
        cs = [failed("2026-08-04", cust="C1", code="M1", reason="AM04"),
              failed("2026-09-04", cust="C1", code="M2", reason="MD01", scheme="B2B"),
              failed("2026-10-05", cust="C1", code="M3", reason="AC04")]
        self.assertEqual([m["reason"] for m in self.prep(cs, since=120)["mails"]], ["new_mandate"])

    def test_new_attempt_mail_asks_for_funds_only_for_insufficient_funds(self):
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 10, prefix="B")
        am04 = failed("2026-10-05", cust="C1", code="M1", reason="AM04")
        ms03 = failed("2026-10-05", cust="C2", code="M2", reason="MS03")
        r = self.prep(cs + [am04, ms03])
        by = {m["customer"]: m for m in r["mails"]}
        self.assertEqual(by["C1"]["subject"], "New collection of €100.00 on November 18, 2026")
        self.assertIn("Could you make sure there are enough funds in your account that day?", by["C1"]["body"])
        self.assertEqual(by["C2"]["template"], "new_attempt_neutral")
        self.assertNotIn("funds", by["C2"]["body"])
        self.assertIn("If anything changed on your side, just reply to this email.", by["C2"]["body"])
        nl = {m["customer"]: m for m in self.prep(cs + [am04, ms03], mail_lang="nl")["mails"]}
        self.assertEqual(nl["C1"]["subject"], "Nieuwe domiciliëring van €100,00 op 18 november 2026")
        self.assertIn("Wil je ervoor zorgen dat er die dag voldoende saldo op je rekening staat?", nl["C1"]["body"])
        self.assertNotIn("saldo", nl["C2"]["body"])

    def test_conversation_mail_wording(self):
        one = [failed("2026-10-05", cust="C1", code="M1", reason="MS02")]
        two = one + [failed("2026-09-04", cust="C1", code="M1", reason="MD06")]
        self.assertIn("You can simply reply to this email.", self.prep(one)["mails"][0]["body"])
        fr1 = self.prep(one, mail_lang="fr")["mails"][0]["body"]
        fr2 = self.prep(two, mail_lang="fr")["mails"][0]["body"]
        self.assertIn("Nous avons constaté que le prélèvement suivant a été remboursé ou refusé :", fr1)
        self.assertIn("Nous avons constaté que les prélèvements suivants ont été remboursés ou refusés :", fr2)

    def test_closing_lines_have_no_doubled_twikey_label(self):
        text = self.render(self.prep([failed("2026-10-05")]))
        after = text.split("What Twikey does:", 1)[1]
        self.assertNotIn("- Twikey:", after)
        self.assertIn("- “This allows us", after)
        fr = self.render(self.prep([failed("2026-10-05")], lang="fr"))
        self.assertIn("Formule : ", fr)
        self.assertNotRegex(fr, r"\S: Professional|Formule:")

    def test_a_new_attempt_waits_for_the_new_mandate_or_registration_the_mail_asks_for(self):
        # AM04 on M1 is worth a new attempt, AC04 on M2 needs a new mandate: one mail, new_mandate
        cs = [failed("2026-10-05", cust="C1", code="M1"), failed("2026-10-05", cust="C1", code="M2", reason="AC04")]
        r = self.prep(cs)
        self.assertEqual([a["mail_reason"] for a in r["new_attempts"]], ["new_mandate"])
        self.assertIn("The mail in part 2 asks this customer to sign a new mandate: present it again once it is "
                      "signed.", self.render(r))
        # MD01 on B2B mandate M2: the mail asks to register it, part 1 waits for that
        cs = [failed("2026-10-05", cust="C1", code="M1"),
              failed("2026-10-05", cust="C1", code="M2", reason="MD01", scheme="B2B")]
        r = self.prep(cs)
        self.assertEqual([a["mail_reason"] for a in r["new_attempts"]], ["b2b_register"])
        self.assertIn("present it again once that is done.", self.render(r))
        # the B2B mail names only the mandate the bank does not know
        self.assertIn("B2B mandate M2 is not registered", r["mails"][0]["body"])
        self.assertNotIn("M1 and M2", r["mails"][0]["subject"] + r["mails"][0]["body"])
        # alone, a new attempt has no note
        self.assertNotIn("The mail in part 2", self.render(self.prep(cs[:1])))

    def test_a_conversation_mail_says_what_else_to_ask_for(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="MS02"),
              failed("2026-10-05", cust="C1", code="M2", reason="AC04")]
        r = self.prep(cs)
        self.assertEqual([m["reason"] for m in r["mails"]], ["conversation"])
        self.assertIn("This customer also needs a new mandate (mandate M2): add the request to sign one to this "
                      "mail.", self.render(r))
        cs[1] = failed("2026-10-05", cust="C1", code="M2", reason="MD01", scheme="B2B")
        for lang, want in (("en", "B2B mandate M2 is not registered at this customer's bank"),
                           ("nl", "B2B-mandaat M2 is niet geregistreerd bij de bank van deze klant"),
                           ("fr", "Le mandat B2B M2 n'est pas enregistré auprès de la banque de ce client")):
            self.assertIn(want, self.render(self.prep(cs, lang=lang)))
        # a conversation alone needs nothing more
        self.assertNotIn("also needs", self.render(self.prep(cs[:1])))

    def test_a_mail_with_several_debts_reads_in_the_plural(self):
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 10, prefix="B")
        cs += [failed("2026-09-04", cust="C1", code="M1", reason="MS03", amount=100.0),
               failed("2026-10-05", cust="C1", code="M1", reason="MS03", amount=150.0)]
        cs += [failed("2026-09-04", cust="C2", code="M2", reason="AC04"),
               failed("2026-10-05", cust="C2", code="M2", reason="AC04", amount=150.0)]
        want = {"en": ("New collections of €250.00 in total on November 18, 2026",
                       "We will collect these again on November 18, 2026, €250.00 in total.",
                       "Once it is signed, we will collect these again, €250.00 in total."),
                "nl": ("Nieuwe domiciliëringen van samen €250,00 op 18 november 2026",
                       "We bieden deze domiciliëringen van samen €250,00 opnieuw aan op 18 november 2026.",
                       "Zodra het getekend is, bieden we deze domiciliëringen van samen €250,00 opnieuw aan."),
                "fr": ("Nouveaux prélèvements le 18 novembre 2026, pour un total de €250,00",
                       "Nous présenterons à nouveau ces prélèvements le 18 novembre 2026, pour un total de €250,00.",
                       "Une fois le mandat signé, nous présenterons à nouveau ces prélèvements, pour un total de "
                       "€250,00.")}
        for lang, (subject, attempt, mandate_line) in want.items():
            mails = {m["customer"]: m for m in self.prep(cs, mail_lang=lang)["mails"]}
            self.assertEqual(mails["C1"]["subject"], subject)
            self.assertIn(attempt, mails["C1"]["body"])
            self.assertIn(mandate_line, mails["C2"]["body"])
            # one debt keeps the singular
            one = self.prep(cs[:-3], mail_lang=lang)["mails"][0]
            self.assertNotRegex(one["subject"] + one["body"], r"(?i)\bthese\b|deze domiciliëringen|ces prélèvements")

    def test_the_drafts_ask_to_check_the_books(self):
        text = self.render(self.prep([failed("2026-10-05", cust="C1", code="M1")]))
        self.assertIn("Check each draft, then send it yourself. Nothing was sent. The drafts cover the failed "
                      "collections of the last 90 days that are still open. Your bank statements show what came in "
                      "at the bank, not what your books say: check that each amount is still owed before you send a "
                      "draft.", text)
        self.assertNotIn("€0.00", text)


if __name__ == "__main__":
    unittest.main()
