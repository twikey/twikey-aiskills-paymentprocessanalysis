import datetime as dt
import unittest

from tests import helpers  # noqa: F401
from xray import checks
from xray.common import DEFAULT_CONFIG, add_months

D = dt.date


def mandate(code="M001", cust="C001", **kw):
    m = {"mandate": code, "customer": cust, "account": "A001", "scheme": "CORE", "signed_date": "2019-01-01",
         "signed": True, "status": "active", "last_collection_date": None, "bank_confirmed": None, "ref_missing": False}
    m.update(kw)
    return m


def coll(date, status="collected", code="M001", cust="C001", amount=100.0, reason=None, account="A001", **kw):
    c = {"status": status, "date": date, "date_kind": "collection", "amount": amount, "customer": cust,
         "mandate": code, "account": account, "scheme": "CORE", "reason_code": reason, "batch_count": 1}
    c.update(kw)
    return c


class ThirtySixMonthRuleTest(unittest.TestCase):
    def issues(self, mandates, collections, on):
        return checks.mandate_health(mandates, collections, on)["issues"]

    def test_add_months_clamps_month_end(self):
        self.assertEqual(add_months(D(2023, 1, 31), 1), D(2023, 2, 28))
        self.assertEqual(add_months(D(2024, 2, 29), 36), D(2027, 2, 28))
        self.assertEqual(add_months(D(2023, 8, 31), 36), D(2026, 8, 31))
        self.assertEqual(add_months(D(2026, 10, 31), -12), D(2025, 10, 31))

    def test_boundary_day(self):
        m = [mandate(last_collection_date="2023-08-31")]
        day_before = self.issues(m, [], D(2026, 8, 30))
        self.assertEqual(day_before["expired"], [])
        self.assertEqual(day_before["expiring_90_days"][0]["expires_on"], "2026-08-31")
        on_the_day = self.issues(m, [], D(2026, 8, 31))
        self.assertEqual(on_the_day["expired"][0]["expired_on"], "2026-08-31")

    def test_failed_collection_counts_as_presented(self):
        cs = [coll("2022-01-10"), coll("2024-12-01", status="failed", reason="AM04")]
        i = self.issues([mandate()], cs, D(2026, 10, 31))
        self.assertEqual(i["expired"], [])
        self.assertEqual(i["expiring_90_days"], [])

    def test_presentations_after_expiry_do_not_revive(self):
        cs = [coll("2020-01-15"), coll("2023-02-01", status="failed", reason="MD01"), coll("2023-03-01")]
        e = self.issues([mandate()], cs, D(2026, 10, 31))["expired"]
        # counted_from: the last presentation before the 36 months without one, the base of expired_on
        self.assertEqual(e, [{"mandate": "M001", "customer": "C001", "expired_on": "2023-01-15",
                              "counted_from": "2020-01-15", "last_presented": "2023-03-01",
                              "presented_after_expiry": 2, "failed_after_expiry": 1}])

    def test_last_collection_from_list_and_from_data_combine(self):
        m = [mandate(last_collection_date="2022-05-01")]
        i = self.issues(m, [coll("2025-01-20")], D(2026, 10, 31))
        self.assertEqual(i["expired"], [])  # the 2025 collection keeps it alive

    def test_never_used(self):
        old = self.issues([mandate(signed_date="2023-02-10")], [], D(2026, 10, 31))
        self.assertEqual(old["unused_since_signing"][0]["signed_on"], "2023-02-10")
        new = self.issues([mandate(signed_date="2025-06-01")], [], D(2026, 10, 31))
        self.assertEqual(new["unused_since_signing"], [])

    def test_cancelled_mandates_are_not_checked_for_expiry(self):
        i = self.issues([mandate(status="cancelled", last_collection_date="2019-01-01")], [], D(2026, 10, 31))
        self.assertEqual(i["expired"], [])

    def test_b2b_and_core_both_follow_the_rule(self):
        m = [mandate("M001", scheme="B2B", last_collection_date="2022-01-01"),
             mandate("M002", "C002", scheme="CORE", last_collection_date="2022-01-01")]
        self.assertEqual(len(self.issues(m, [], D(2026, 10, 31))["expired"]), 2)

    def test_refund_booking_date_is_not_a_presentation(self):
        # last known presentation 2022-05-01, a refund booked 2024-02-01 without its collection date
        cs = [coll("2022-05-01"), coll("2024-02-01", "failed", reason="MD06", date_kind="booked")]
        i = self.issues([mandate()], cs, D(2026, 10, 31))
        self.assertEqual(i["expired"], [])  # never expired from a guessed date, never kept alive by it either
        self.assertEqual(i["last_collection_unknown"], [{"mandate": "M001", "customer": "C001",
                                                         "return_booked_on": "2024-02-01",
                                                         "last_known_collection": "2022-05-01"}])
        # a return booked before the last known presentation changes nothing
        cs = [coll("2022-05-01", "failed", reason="AM04", date_kind="booked"), coll("2023-01-10")]
        i = self.issues([mandate()], cs, D(2026, 10, 31))
        self.assertEqual(i["last_collection_unknown"], [])
        self.assertEqual(i["expired"][0]["expired_on"], "2026-01-10")
        # the original collection date, when the file carries it, is used
        cs = [coll("2022-05-01", "failed", reason="MD06")]
        self.assertEqual(self.issues([mandate()], cs, D(2026, 10, 31))["expired"][0]["expired_on"], "2025-05-01")

    def test_other_mandate_issues(self):
        m = [mandate("M001", ref_missing=True, signed_date=None, signed=False),
             mandate("M002", "C002", scheme="B2B", bank_confirmed=False, last_collection_date="2026-10-01"),
             mandate("M003", "C003", last_collection_date="2026-10-01"),
             mandate("M003", "C004", account="A004", last_collection_date="2026-10-01"),
             mandate("M005", "C005", account="A005", last_collection_date="2026-10-01"),
             mandate("M006", "C005", account="A005", last_collection_date="2026-10-01")]
        cs = [coll("2026-09-01", code="M005", cust="C005", account="A099")]
        i = self.issues(m, cs, D(2026, 10, 31))
        self.assertEqual([x["mandate"] for x in i["missing_reference"]], ["M001"])
        self.assertEqual([x["mandate"] for x in i["missing_signature_date"]], ["M001"])
        self.assertEqual([x["mandate"] for x in i["signature_missing"]], ["M001"])
        self.assertEqual([x["mandate"] for x in i["b2b_not_confirmed"]], ["M002"])
        self.assertEqual(i["duplicate_reference"], [{"mandate": "M003", "customers": ["C003", "C004"]}])
        self.assertEqual(i["possible_duplicate"], [{"customer": "C005", "mandates": ["M005", "M006"]}])
        self.assertEqual(i["iban_changed"], [{"mandate": "M005", "customer": "C005", "accounts": 2}])


class DecodeTest(unittest.TestCase):
    def test_grouping_and_categories(self):
        cs = [coll("2026-08-04", "failed", reason="AM04", amount=10.0),
              coll("2026-08-04", "failed", reason="AM04", amount=15.5),
              coll("2026-08-05", "failed", reason="MD01", amount=20.0, scheme="B2B"),
              coll("2026-08-05", "failed", reason="MD01", amount=30.0, scheme="CORE"),
              coll("2026-09-05", "failed", reason="MD06", amount=5.0, cust="C002"),
              coll("2026-09-07", "failed", reason="XX99", amount=1.0, cust="C003"),
              coll("2026-09-07", "failed", reason=None, amount=2.0, cust="C003", date_kind="booked"),
              coll(None, "failed", reason="FF01", amount=100.0, cust=None, batch_count=4),
              coll("2026-09-09", "collected", amount=999.0)]
        d = checks.decode(cs)
        self.assertEqual(d["total"], {"count": 11, "amount": 183.5, "amount_unknown_count": 0})
        by = {r["code"]: r for r in d["by_code"]}
        self.assertEqual((by["AM04"]["count"], by["AM04"]["amount"]), (2, 25.5))
        self.assertEqual(by["MD01"]["categories"], {"conversation": 1, "new_mandate": 1})
        self.assertFalse(by["XX99"]["known"])
        self.assertEqual(by["XX99"]["meaning"], "unknown code")
        self.assertEqual(by["FF01"]["count"], 4)
        self.assertEqual(d["by_category"]["new_attempt"]["count"], 2)
        self.assertEqual(d["by_category"]["own_setup"]["count"], 4)
        self.assertEqual(d["by_category"]["unknown"]["count"], 1)
        self.assertEqual(d["by_category"]["unreadable"]["count"], 1)
        self.assertEqual(d["unknown_codes"], ["XX99"])
        self.assertEqual(d["failures_by_day"], {"4": 2, "5": 3, "7": 1})
        self.assertEqual(d["days_of_month_return_booked"], {"7": 1})
        self.assertEqual(d["repeat_customers"], {"C001": 4, "C003": 2})

    # ------------------------------------------------------------------ codes, amounts, rates

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

    def test_reason_not_in_file(self):
        d = checks.decode([coll("2026-08-04", "failed", reason=None, reason_missing=True)])
        self.assertEqual(d["by_code"][0]["label"], "reason not in file")

    def test_worth_a_new_attempt(self):
        d = checks.decode([coll("2026-08-04", "failed", reason="MS03")])
        self.assertTrue(d["by_category"]["new_attempt"]["meaning"].startswith("Worth a new attempt"))

    def test_proprietary_reason_and_unknown_amount(self):
        cs = [coll(None, "failed", reason=None, reason_proprietary=True, amount=40.0),
              coll(None, "failed", reason="FF01", amount=None, cust=None, batch_count=7)]
        d = checks.decode(cs)
        by = {r["label"]: r for r in d["by_code"]}
        self.assertEqual(by["proprietary reason (not shown)"]["count"], 1)
        self.assertEqual((by["FF01"]["amount"], by["FF01"]["amount_unknown_count"]), (0.0, 7))
        self.assertEqual(d["total"], {"count": 8, "amount": 40.0, "amount_unknown_count": 7})

    def test_failure_rate_per_collection_day(self):
        def c(date, n, status="collected", **kw):
            return coll(date, status, code="M%d" % n, cust="C%d" % n, **kw)
        cs = ([c("2026-08-04", n, e2e="a%d" % n) for n in range(1, 10)]          # nine collected on Aug 4
              + [c("2026-08-04", 10, "failed", reason="AM04", e2e="x")]           # one rejected before settlement
              + [c("2026-08-18", 10, e2e="x2")]                                   # its retry: left out
              + [c("2026-08-04", 11, e2e="r"), c("2026-08-04", 11, "failed", reason="MD06", e2e="r")]  # returned
              + [c("2026-09-04", n, e2e="s%d" % n) for n in range(1, 5)]          # four collected on Fri Sep 4
              + [c("2026-10-05", n, e2e="o%d" % n) for n in range(1, 4)]          # Mon Oct 5: the Sunday 4th run
              + [c("2026-08-20", 20), c("2026-08-20", 21)]                        # day 20: one month only
              + [c("2026-03-04", 12, "failed", reason="AM04")])                   # a month without bank data
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

    def test_epc_code_label_says_not_on_twikeys_page(self):
        d = checks.decode([coll("2026-08-04", "failed", reason="ED05")])
        self.assertEqual(d["unknown_codes"], ["ED05"])  # the field name stays
        self.assertEqual(d["by_code"][0]["meaning"], "Settlement of the collection failed")  # the EPC meaning stays
        self.assertNotIn("Twikey's reason-code list", checks.CATEGORY_TEXTS["en"]["unknown"])

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


def inv(code, cust, amount, state="BOOKED", ogm=None, paid=None, due="2026-09-01", date="2026-08-01"):
    return {"id": code, "number": code, "amount": amount, "date": date, "duedate": due, "state": state,
            "customer": {"customerNumber": cust, "companyName": cust},
            "lastpayment": [{"date": paid, "method": "transfer"}] if paid else [],
            "xray": {"ogm": ogm, "paid_date": paid, "open_amount": amount if state == "BOOKED" else 0.0}}


def line(i, date, amount, cust=None, ogm=None, mentions=False):
    return {"id": "B%04d" % i, "date": date, "amount": amount, "customer": cust, "ogm": ogm,
            "mentions_open_invoice": mentions}


class MatchTest(unittest.TestCase):
    def test_categories(self):
        o1, o2 = "+++090/9337/55493+++", "+++260/0000/00170+++"
        store = {"invoices": {
            "I1": inv("I1", "C1", 100.0, "PAID", o1, paid="2026-09-01"),
            "I2": inv("I2", "C1", 200.0, "BOOKED", o2),
            "I3": inv("I3", "C2", 50.0, "PAID", paid="2026-09-10"),
            "I4": inv("I4", "C2", 50.0, "PAID", paid="2026-09-10"),
            "I5": inv("I5", "C3", 80.0, "BOOKED"),
        }}
        bank = [line(1, "2026-09-01", 100.0, "C1", o1),      # matched
                line(2, "2026-09-02", 100.0, "C1", o1),      # double
                line(3, "2026-09-03", 50.0, "C1", o2),       # partial of I2
                line(4, "2026-09-10", 100.0, "C2"),          # bundled I3 + I4
                line(5, "2026-09-11", 80.0, "C3"),           # I5 open in the books: paid but open
                line(6, "2026-09-12", 33.0, "C3", mentions=True),  # unmatched, known customer
                line(7, "2026-09-13", 9.0, "C9")]            # unmatched, not in the invoices
        r = checks.match(store, bank)
        self.assertEqual(r["matched"]["count"], 1)
        self.assertEqual(r["double"]["count"], 1)
        self.assertEqual((r["partial"]["count"], r["partial"]["still_open"]), (1, 150.0))
        self.assertEqual((r["bundled"]["count"], r["bundled"]["invoices"]), (1, 2))
        self.assertEqual((r["paid_but_open"]["count"], r["paid_but_open"]["invoices"]), (1, ["I5"]))
        u = r["unmatched"]
        self.assertEqual((u["count"], u["known_customer"], u["unknown_party"], u["mentions_open_invoice"]),
                         (1, 1, 0, 1))
        # C9 is in none of the invoices and gives no reference: another receipt, not an invoice payment
        self.assertEqual((r["other_receipts"]["count"], r["other_receipts"]["customers"]), (1, ["C9"]))
        self.assertEqual(r["credit_lines"], {"count": 7, "amount": 472.0})
        self.assertNotIn(";", r["method"])

    def test_same_amount_prefers_the_invoice_paid_that_day(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 10.0, "PAID", paid="2026-08-01", due="2026-08-01"),
            "I2": inv("I2", "C1", 10.0, "PAID", paid="2026-09-01", due="2026-09-01"),
        }}
        r = checks.match(store, [line(1, "2026-09-01", 10.0, "C1")])
        self.assertEqual(r["matched"]["count"], 1)

    def test_never_an_invoice_issued_after_the_payment(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 10.0, "PAID", paid="2026-08-29", due="2026-08-30", date="2026-07-31"),
            "I2": inv("I2", "C1", 10.0, "BOOKED", due="2026-11-24", date="2026-10-25"),
        }}
        r = checks.match(store, [line(1, "2026-08-30", 10.0, "C1")])
        self.assertEqual(r["matched"]["count"], 1)
        self.assertEqual(r["paid_but_open"]["count"], 0)
        # even with the later invoice's structured communication, a payment never settles a later invoice
        store["invoices"]["I2"]["xray"]["ogm"] = "+++260/0000/00170+++"
        r = checks.match(store, [line(1, "2026-08-30", 99.0, "C1", "+++260/0000/00170+++")])
        self.assertEqual((r["paid_but_open"]["count"], r["partial"]["count"], r["unmatched"]["count"]), (0, 0, 1))

    def test_paid_invoice_near_the_payment_wins_over_an_open_one(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 10.0, "BOOKED", due="2026-07-01", date="2026-06-01"),
            "I2": inv("I2", "C1", 10.0, "PAID", paid="2026-08-28", due="2026-08-30", date="2026-07-31"),
        }}
        r = checks.match(store, [line(1, "2026-08-30", 10.0, "C1")])
        self.assertEqual((r["matched"]["count"], r["paid_but_open"]["count"]), (1, 0))

    def test_credit_notes_and_cancelled_invoices(self):
        # F001 1,000 open, CN001 200 credit note, F002 300 (another customer), F003 500 cancelled, F004 450 open
        store = {"invoices": {
            "F001": inv("F001", "Alfa", 1000.0, "BOOKED", date="2026-09-01", due="2026-10-01"),
            "CN001": inv("CN001", "Alfa", 200.0, "CREDITED", date="2026-09-05", due="2026-10-05"),
            "F002": inv("F002", "Beta", 300.0, "BOOKED", date="2026-09-01", due="2026-10-01"),
            "F003": inv("F003", "Gamma", 500.0, "CANCELLED", date="2026-09-01", due="2026-10-01"),
            "F004": inv("F004", "Gamma", 450.0, "BOOKED", date="2026-09-02", due="2026-10-02"),
        }}
        bank = [line(1, "2026-10-10", 800.0, "Alfa"),   # F001 minus CN001
                line(2, "2026-10-11", 200.0, "Alfa"),   # the credit note on its own is never a match
                line(3, "2026-10-12", 500.0, "Gamma")]  # the cancelled invoice is never a candidate
        r = checks.match(store, bank)
        self.assertEqual((r["bundled"]["count"], r["bundled"]["invoices"], r["bundled"]["credit_notes"]), (1, 1, 1))
        self.assertEqual(r["bundled"]["lines"][0]["invoices"], ["F001", "CN001"])
        self.assertEqual((r["matched"]["count"], r["paid_but_open"]["count"]), (0, 0))
        self.assertEqual((r["unmatched"]["count"], r["unmatched"]["known_customer"]), (2, 2))
        self.assertEqual(r["unmatched"]["customers"], ["Alfa", "Gamma"])

    def test_payer_whose_only_invoice_was_credited_or_cancelled_is_a_customer(self):
        store = {"invoices": {
            "F010": inv("F010", "Delta", 300.0, "CANCELLED", date="2026-09-01", due="2026-10-01"),
            "CN013": inv("CN013", "Golf", 150.0, "CREDITED", date="2026-09-01", due="2026-10-01"),
        }}
        r = checks.match(store, [line(1, "2026-10-11", 300.0, "Delta"), line(2, "2026-10-13", 150.0, "Golf")])
        self.assertEqual(r["other_receipts"]["count"], 0)
        self.assertEqual((r["unmatched"]["count"], r["unmatched"]["known_customer"], r["unmatched"]["unknown_party"]),
                         (2, 2, 0))


class ProfileTest(unittest.TestCase):
    def store(self, lates, open_overdue_days=None):
        invs = {}
        for k, late in enumerate(lates):
            due = D(2026, 1, 1) + dt.timedelta(days=30 * k)
            invs["I%d" % k] = inv("I%d" % k, "C1", 10.0, "PAID", paid=str(due + dt.timedelta(days=late)),
                                  due=str(due), date=str(due - dt.timedelta(days=30)))
            invs["I%d" % k]["xray"]["terms_days"] = 30
        if open_overdue_days is not None:
            due = D(2026, 10, 31) - dt.timedelta(days=open_overdue_days)
            invs["IO"] = inv("IO", "C1", 10.0, "BOOKED", due=str(due), date=str(due - dt.timedelta(days=30)))
        return {"invoices": invs}

    def profile(self, store):
        return checks.terms(store, dict(DEFAULT_CONFIG), D(2026, 10, 31))["customers"][0]["profile"]

    def test_rules(self):
        self.assertEqual(self.profile(self.store([0, 1, -1, 2, 0, 1])), "clockwork")
        self.assertEqual(self.profile(self.store([12] * 6)), "late_but_pays")
        self.assertEqual(self.profile(self.store([0, 3, 6, 9, 12, 15])), "drifting")
        self.assertEqual(self.profile(self.store([0, 1], open_overdue_days=61)), "at_risk")
        self.assertEqual(self.profile(self.store([0, 1], open_overdue_days=60)), "too_early")

    def test_failed_collections_are_never_clockwork(self):
        store = self.store([0, 1, -1, 2, 0, 1])
        failed = [coll("2026-03-01", "failed", reason="AM04", cust="C1")]
        r = checks.terms(store, dict(DEFAULT_CONFIG), D(2026, 10, 31), failed)
        self.assertEqual(r["customers"][0]["profile"], "after_failures")
        self.assertEqual(r["profiles"]["clockwork"]["count"], 0)

    def test_dso_against_each_invoices_own_term(self):
        invs = {"I1": inv("I1", "C1", 100.0, "BOOKED", date="2026-10-01", due="2026-10-15"),   # 14 days
                "I2": inv("I2", "C2", 300.0, "BOOKED", date="2026-10-01", due="2026-11-30")}   # 60 days
        r = checks.terms({"invoices": invs}, dict(DEFAULT_CONFIG), D(2026, 10, 31))
        self.assertEqual(r["terms_days_90d"], 48.5)  # (100 x 14 + 300 x 60) / 400
        self.assertEqual(r["dso_90d"], 90.0)
        self.assertEqual(r["dso_minus_terms"], 41.5)
        self.assertNotIn("default_terms_days", r)

    def test_dso_counts_partly_paid_invoices_at_their_billed_amount(self):
        part = inv("I1", "C1", 100.0, "BOOKED", date="2026-10-01", due="2026-10-31")
        part["xray"]["open_amount"] = 40.0  # 60 paid, 40 still open
        r = checks.terms({"invoices": {"I1": part}}, dict(DEFAULT_CONFIG), D(2026, 10, 31))
        self.assertEqual(r["dso_90d"], 36.0)  # 40 open / 100 billed x 90, not 40 / 40 x 90
        self.assertEqual(r["open_receivables"], 40.0)

    def test_method_names_standard_formulas(self):
        r = checks.terms({"invoices": {}}, dict(DEFAULT_CONFIG), D(2026, 10, 31))
        self.assertTrue(r["method"].startswith("Standard aging and DSO formulas"))

    def test_slope(self):
        self.assertAlmostEqual(checks._slope([0, 3, 6, 9]), 3.0)
        self.assertAlmostEqual(checks._slope([5, 5, 5]), 0.0)


class LateInvoicesTest(unittest.TestCase):
    def test_more_than_seven_days_past_due(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 10.0, "PAID", paid="2026-09-09", due="2026-09-01"),   # 8 days late
            "I2": inv("I2", "C1", 10.0, "PAID", paid="2026-09-08", due="2026-09-01"),   # 7 days: not late
            "I3": inv("I3", "C2", 10.0, "BOOKED", due="2026-10-23"),                    # open, 8 days past due
            "I4": inv("I4", "C2", 10.0, "BOOKED", due="2026-10-30"),                    # open, 1 day
            "I5": inv("I5", "C3", 10.0, "CREDITED", due="2026-01-01"),                  # credit note
            "I6": inv("I6", "C3", 10.0, "CANCELLED", due="2026-01-01")}}
        r = checks.late_invoices(store, D(2026, 10, 31))
        self.assertEqual((r["count"], r["customers"], r["months"]), (2, ["C1", "C2"], 1))


class StepsTest(unittest.TestCase):
    def test_checklists_come_from_the_data_file(self):
        import json
        import os
        from xray.common import DATA_DIR
        with open(os.path.join(DATA_DIR, "manual_steps.json"), encoding="utf-8") as f:
            data = json.load(f)
        for lang in ("en", "nl", "fr"):
            self.assertEqual(set(data[lang]["items"]), set(checks.STEP_ITEMS), lang)
            r = checks.steps({"invoices": {}}, [], [], [], D(2026, 10, 31), lang)
            for i in r["items"]:
                want = data[lang]["items"][i["id"]]["checklist"]
                self.assertEqual(i["checklist"], want)
                self.assertEqual(i["steps_each"], len(want))
            # every item type is listed, with zero when the files hold none
            self.assertEqual(sorted(i["id"] for i in r["items"]), sorted(checks.STEP_ITEMS))
            self.assertEqual((r["total_items"], r["total_steps"], r["per_month_total"]), (0, 0, None))
        # the same number of steps in every language
        for k in checks.STEP_ITEMS:
            self.assertEqual(len({len(data[lang]["items"][k]["checklist"]) for lang in ("en", "nl", "fr")}), 1, k)

    def test_counts_and_totals(self):
        store = {"invoices": {"I1": inv("I1", "C1", 10.0, "BOOKED", due="2026-10-01", date="2026-09-01")}}
        cs = [coll("2026-09-01", "failed", reason="AM04"), coll("2026-10-01", "failed", reason="MS02"),
              coll("2026-10-01", "failed", reason="XX99")]
        bank = [line(1, "2026-09-20", 77.0, "C9")]  # a party in no invoice, no reference: another receipt
        r = checks.steps(store, [mandate(signed=False)], cs, bank, D(2026, 10, 31))
        by = {i["id"]: i for i in r["items"]}
        self.assertEqual(by["failed_new_attempt"]["count"], 1)
        self.assertEqual(by["failed_conversation"]["count"], 1)
        self.assertEqual(by["failed_unknown"]["count"], 1)  # an unknown code: ask the bank
        self.assertEqual(by["mandate_fix"]["count"], 1)
        self.assertEqual(by["late_invoice"]["count"], 1)
        self.assertEqual(by["unmatched"]["count"], 0)
        self.assertEqual(by["failed_new_attempt"]["months"], 2)
        self.assertEqual(by["failed_new_attempt"]["per_month"], 0.5)
        self.assertIsNone(by["mandate_fix"]["per_month"])
        self.assertEqual(r["total_items"], 5)
        self.assertEqual(r["total_steps"], sum(i["count"] * i["steps_each"] for i in r["items"]))
        self.assertEqual(r["items"][0]["id"], "failed_new_attempt")  # biggest steps_total first
        self.assertEqual(r["per_month_left_out"], ["mandate_fix"])


def failed(date, reason="AM04", cust="C001", code="M001", amount=100.0, **kw):
    return coll(date, "failed", code=code, cust=cust, amount=amount, reason=reason, **kw)


class MonthHelpers:
    ON = D(2026, 10, 31)
    TODAY = D(2026, 11, 2)

    def prep(self, store=None, collections=(), bank=(), mandates=(), since=90, lang="en", mail_lang=None,
             today=None, source=None):
        from xray import month
        return month.prepare(store or {"invoices": {}}, list(mandates), list(collections), list(bank), self.ON, since,
                             lang, mail_lang, today or self.TODAY, source)

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
        r = self.prep(collections=cs)
        self.assertEqual([a["customer"] for a in r["new_attempts"]], ["C3"])
        self.assertEqual(r["collected_later"], 2)

    def test_next_months_regular_collection_closes_nothing(self):
        cs = [failed("2026-08-04", cust="C1", code="M1"), coll("2026-09-04", cust="C1", code="M1")]
        self.assertEqual(len(self.prep(collections=cs)["new_attempts"]), 1)

    def test_a_failure_whose_invoice_is_paid_is_left_out(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, "PAID", paid="2026-09-20", due="2026-09-04"),
                              "I2": inv("I2", "C2", 100.0, "BOOKED", due="2026-10-05")}}
        cs = [failed("2026-09-04", cust="C1", code="M1"), failed("2026-10-05", cust="C2", code="M2")]
        r = self.prep(store, cs)
        self.assertEqual([(a["customer"], a["invoice"]) for a in r["new_attempts"]], [("C2", "I2")])

    def test_window_and_categories(self):
        cs = [failed("2026-07-01"), failed("2026-10-01", reason="MS02", cust="C2", code="M2"),
              failed("2026-10-01", reason="MD01", cust="C3", code="M3", scheme="CORE")]
        r = self.prep(collections=cs)
        self.assertEqual(r["new_attempts"], [])  # July is outside the 90 days
        self.assertEqual([(m["customer"], m["reason"]) for m in r["mails"]],
                         [("C2", "conversation"), ("C3", "new_mandate")])
        self.assertEqual(len(self.prep(collections=cs, since=200)["new_attempts"]), 1)

    def test_invoice_known_only_when_one_fits(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05"),
                              "I2": inv("I2", "C1", 100.0, due="2026-11-04"),     # due after the failure
                              "I3": inv("I3", "C2", 100.0, due="2026-10-05"),
                              "I4": inv("I4", "C2", 100.0, due="2026-10-05")}}    # two on the same day
        cs = [failed("2026-10-05", cust="C1", code="M1"), failed("2026-10-05", cust="C2", code="M2")]
        r = self.prep(store, cs)
        self.assertEqual([a["invoice"] for a in r["new_attempts"]], ["I1", None])
        body = r["mails"][1]["body"]
        self.assertIn("- €100.00, collection of October 5, 2026", body)  # no invoice named when it is not known

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
        r = self.prep(collections=[failed("2026-10-05")])
        self.assertIsNone(r["suggested_day"])
        self.assertIsNone(r["new_attempts"][0]["new_date"])
        self.assertIn("[date of the new collection]", r["mails"][0]["body"])
        self.assertIn("Too little history", month.render(r))

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

    def test_match_suggestion_strengths_and_order(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 250.0, ogm="R0001", due="2026-10-01"),
            "I2": inv("I2", "C1", 120.0, due="2026-11-01", date="2026-10-20"),  # issued after the payment
            "I3": inv("I3", "C2", 120.0, due="2026-11-01", date="2026-10-20"),
            "I4": inv("I4", "C3", 999.0, due="2026-11-01"),
            "I5": inv("I5", "C4", 333.0, due="2026-11-01"),
            "I6": inv("I6", "C5", 333.0, due="2026-11-01")}}
        bank = [
            dict(line(1, "2026-10-02", 100.0, "C1", ogm="R0001"), ogm_invoices=["I1"]),  # partial, by reference
            dict(line(2, "2026-10-10", 120.0, "C1", mentions=True), ogm_invoices=[]),     # paid before invoicing
            dict(line(3, "2026-10-11", 999.0, "C8", mentions=True), ogm_invoices=[]),     # unknown payer
            dict(line(4, "2026-10-12", 333.0, "C8", mentions=True), ogm_invoices=[]),     # two invoices of 333
        ]
        ms = self.prep(store, bank=bank)["match_suggestions"]
        got = [(ln["line"], [(c["invoice"], c["strength"]) for c in ln["candidates"]]) for ln in ms["lines"]]
        self.assertEqual(got, [("B0001", [("I1", "structured_communication")]),
                               ("B0002", [("I2", "same_customer_same_amount")]),
                               ("B0003", [("I4", "amount_only")])])
        self.assertEqual(ms["without_candidate"], 1)
        self.assertEqual(ms["strengths"], ["structured_communication", "same_customer_same_amount", "amount_only"])

    def test_at_most_three_candidates_strongest_first(self):
        store = {"invoices": {
            "I1": inv("I1", "C1", 500.0, ogm="R0001", due="2026-10-01"),
            "I2": inv("I2", "C1", 500.0, ogm="R0001", due="2026-10-02"),
            "I3": inv("I3", "C1", 500.0, ogm="R0001", due="2026-10-03"),
            "I4": inv("I4", "C1", 500.0, ogm="R0001", due="2026-10-04")}}
        bank = [dict(line(1, "2026-10-10", 90.0, "C1", ogm="R0001"), ogm_invoices=["I1", "I2", "I3", "I4"])]
        ms = self.prep(store, bank=bank)["match_suggestions"]
        self.assertEqual(len(ms["lines"][0]["candidates"]), 3)

    def test_mandates_to_renew_active_first(self):
        store = {"invoices": {"I1": inv("I1", "C2", 10.0, due="2026-10-01")}}
        mands = [mandate("M1", "C1", last_collection_date="2022-01-10"),
                 mandate("M2", "C2", last_collection_date="2023-12-01"),
                 mandate("M3", "C3", last_collection_date="2025-01-01")]
        r = self.prep(store, mandates=mands)["mandates_to_renew"]
        self.assertEqual([(x["mandate"], x["status"], x["still_active"]) for x in r],
                         [("M2", "expiring", True), ("M1", "expired", False)])
        self.assertEqual(r[1]["last_collection"], "2022-01-10")
        self.assertIn("January 10, 2025", r[1]["mail"]["body"])
        self.assertIn("[link to your mandate form]", r[1]["mail"]["body"])

    def test_placeholders_filled_in_every_language(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05")}}
        cs = [failed("2026-10-05", cust="C1", code="M1"), failed("2026-10-05", "MD06", cust="C2", code="M2"),
              failed("2026-10-05", "AC04", cust="C3", code="M3")]
        for lang in ("en", "nl", "fr"):
            r = self.prep(store, cs, mandates=[mandate("M9", "C9", last_collection_date="2022-01-10")],
                          mail_lang=lang)
            texts = [m["subject"] + m["body"] for m in r["mails"]] + \
                    [x["mail"]["subject"] + x["mail"]["body"] for x in r["mandates_to_renew"]]
            self.assertEqual(len(texts), 4)
            for t in texts:
                self.assertNotRegex(t, r"[{}]", (lang, t))


class MonthFixTest(MonthHelpers, unittest.TestCase):
    """One debt per collection, money that came in another way, dead mandates, B2B registration, one mail per
    customer, placeholders, competing amount-only suggestions, not-checked sections, copy."""

    def render(self, r):
        from xray import month
        return month.render(r, today=self.TODAY)

    # A1
    def test_repeated_failures_are_one_debt(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20")}}
        cs = [failed("2026-10-05", cust="C1", code="M1", e2e="E1"), failed("2026-10-19", cust="C1", code="M1", e2e="E2")]
        r = self.prep(store, cs)
        self.assertEqual(len(r["new_attempts"]), 1)
        a = r["new_attempts"][0]
        self.assertEqual((a["invoice"], a["amount"], a["failure_date"], a["first_failure_date"], a["attempts"]),
                         ("I1", 100.0, "2026-10-19", "2026-10-05", 2))
        self.assertEqual(len(r["mails"]), 1)
        self.assertEqual(r["mails"][0]["amount"], 100.0)  # never 200: one debt, counted once
        self.assertIn("€100.00", r["mails"][0]["subject"])
        self.assertIn("- invoice I1: €100.00, presented twice, last on October 19, 2026", r["mails"][0]["body"])
        self.assertIn("€100.00, failed twice, last on October 19, 2026.", self.render(r))
        # the same end-to-end reference is one debt too, even more than three weeks later
        cs = [failed("2026-09-04", cust="C1", code="M1", e2e="E1"), failed("2026-10-05", cust="C1", code="M1", e2e="E1")]
        self.assertEqual([a["attempts"] for a in self.prep(collections=cs)["new_attempts"]], [2])
        # a month later, the same amount on the same mandate is the next invoice: two debts
        cs = [failed("2026-09-04", cust="C1", code="M1"), failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(collections=cs)
        self.assertEqual([a["attempts"] for a in r["new_attempts"]], [1, 1])
        self.assertEqual(r["mails"][0]["amount"], 200.0)

    # A2
    def test_paid_at_the_bank_after_the_failure_closes_it(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20", ogm="R0001")}}
        cs = [failed("2026-10-05", cust="C1", code="M1")]
        bank = [dict(line(1, "2026-10-12", 100.0, "C1", ogm="R0001"), ogm_invoices=["I1"])]
        r = self.prep(store, cs, bank)
        self.assertEqual((r["new_attempts"], r["mails"]), ([], []))
        self.assertEqual(r["closed"]["paid_at_bank"], 1)
        # only in "close in your books"
        self.assertEqual([x["invoice"] for x in r["match_suggestions"]["paid_but_open"]], ["I1"])
        text = self.render(r)
        self.assertIn("- Invoice I1 of **C1**: €100.00, paid on October 12, 2026.", text)
        self.assertNotIn("New attempt:", text)

    def test_a_failure_on_a_cancelled_invoice_is_closed(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, "CANCELLED", due="2026-10-05", date="2026-09-20")}}
        r = self.prep(store, [failed("2026-10-05", cust="C1", code="M1")])
        self.assertEqual((r["new_attempts"], r["mails"], r["closed"]["invoice_closed"]), ([], [], 1))

    def test_a_later_bank_payment_from_the_customer_covers_it(self):
        store = {"invoices": {"I9": inv("I9", "C1", 50.0, "PAID", paid="2026-08-01", due="2026-08-01")}}
        cs = [failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(store, cs, [line(1, "2026-10-12", 100.0, "C1")])
        self.assertEqual((r["new_attempts"], r["closed"]["bank_credit"]), ([], 1))
        # a payment before the failure, or a smaller one, covers nothing
        for b in (line(1, "2026-10-01", 100.0, "C1"), line(1, "2026-10-12", 60.0, "C1")):
            self.assertEqual(len(self.prep(store, cs, [b])["new_attempts"]), 1)

    # A3
    def test_no_new_attempt_on_an_expired_mandate(self):
        mands = [mandate("M1", "C1", last_collection_date="2023-06-01")]
        r = self.prep(None, [failed("2026-10-05", cust="C1", code="M1", reason="AM04")], mandates=mands)
        self.assertEqual(r["new_attempts"], [])
        self.assertEqual([(m["customer"], m["reason"]) for m in r["mails"]], [("C1", "new_mandate")])

    def test_no_new_attempt_on_a_mandate_that_later_got_md01(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="AM04"),
              failed("2026-10-05", cust="C1", code="M1", reason="MD01", scheme="CORE")]
        r = self.prep(None, cs)
        self.assertEqual(r["new_attempts"], [])
        self.assertEqual([(m["reason"], len(m["items"])) for m in r["mails"]], [("new_mandate", 2)])
        # on a B2B mandate, a later MD01 means the customer's bank does not know it: register it
        cs = [dict(c, scheme="B2B") for c in cs]
        self.assertEqual([m["reason"] for m in self.prep(None, cs)["mails"]], ["b2b_register"])

    # A4
    def test_md01_on_a_b2b_mandate_asks_to_register_it(self):
        cs = [failed("2026-10-05", cust="C1", code="M1", reason="MD01", scheme="B2B")]
        for lang, want in (("en", "Your bank rejected the following direct debit, because B2B mandate M1 is not "
                                  "registered there:"),
                           ("nl", "omdat B2B-mandaat M1 daar niet geregistreerd is"),
                           ("fr", "parce que le mandat B2B M1 n'y est pas enregistré")):
            m = self.prep(None, cs, mail_lang=lang)["mails"][0]
            self.assertEqual(m["reason"], "b2b_register")
            self.assertIn(want, m["body"])
            self.assertNotRegex(m["body"], r"refunded or refused|terugbetaald of geweigerd|remboursé ou refusé")
        self.assertIn("Could you ask your bank to register it? Then we will present the collection of €100.00 again.",
                      self.prep(None, cs)["mails"][0]["body"])
        # on a Core mandate MD01 still needs a new mandate
        cs = [dict(cs[0], scheme="CORE")]
        self.assertEqual(self.prep(None, cs)["mails"][0]["reason"], "new_mandate")

    # A5
    def test_one_mail_per_customer_by_priority(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-09-04", date="2026-08-20"),
                              "I2": inv("I2", "C1", 100.0, due="2026-10-05", date="2026-09-20")}}
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="MS02"), failed("2026-10-05", cust="C1", code="M1")]
        r = self.prep(store, cs)
        self.assertEqual([(m["customer"], m["reason"], m["invoices"], m["amount"]) for m in r["mails"]],
                         [("C1", "conversation", ["I1", "I2"], 200.0)])
        # conversation > new_mandate > b2b_register > new_attempt
        cs = [failed("2026-08-04", cust="C1", code="M1", reason="AM04"),
              failed("2026-09-04", cust="C1", code="M2", reason="MD01", scheme="B2B"),
              failed("2026-10-05", cust="C1", code="M3", reason="AC04")]
        self.assertEqual([m["reason"] for m in self.prep(None, cs, since=120)["mails"]], ["new_mandate"])
        # an expired mandate of a customer who already gets a mail: no second mail
        mands = [mandate("M9", "C1", last_collection_date="2022-01-10")]
        r = self.prep(store, [failed("2026-10-05", cust="C1", code="M1", reason="MS02")], mandates=mands)
        renew = r["mandates_to_renew"][0]
        self.assertEqual((renew["mail"], renew["mail_covered_by"]), (None, "conversation"))
        self.assertIn("No separate draft, so this customer gets one mail", self.render(r))

    # A7
    def test_unknown_amount_is_a_placeholder_never_zero(self):
        cs = [failed("2026-10-05", cust="C1", code="M1", amount=None)]
        for lang, ph in (("en", "[amount]"), ("nl", "[bedrag]"), ("fr", "[montant]")):
            r = self.prep(None, cs, lang=lang)
            m = r["mails"][0]
            self.assertIsNone(m["amount"])
            self.assertIn(ph, m["subject"] + m["body"])
            text = self.render(r)
            self.assertIn(ph, text)
            self.assertNotRegex(m["body"] + text, r"€0[.,]00")

    # A8
    def test_amount_only_never_suggests_one_invoice_for_two_lines(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20")}}
        bank = [dict(line(1, "2026-10-12", 100.0, None, mentions=True), ogm_invoices=[]),
                dict(line(2, "2026-10-13", 100.0, None, mentions=True), ogm_invoices=[])]
        ms = self.prep(store, bank=bank)["match_suggestions"]
        self.assertEqual((ms["lines"], ms["without_candidate"]), ([], 2))
        # one line alone still gets it
        self.assertEqual(len(self.prep(store, bank=bank[:1])["match_suggestions"]["lines"]), 1)

    def test_closing_without_any_data_names_no_empty_period(self):
        r = self.prep()
        self.assertEqual(r["closing"]["text"], "Claude prepared this once, from your exports. Nothing was sent and no "
                                               "bank file was written.")

    # A9
    def test_a_missing_export_is_not_checked_never_none(self):
        source = {"invoices": True, "failures": True, "mandates": False, "bank": False}
        r = self.prep(None, [failed("2026-10-05")], source=source)
        self.assertEqual(r["checked"], {"new_attempts": True, "mails": True, "mandates_to_renew": False,
                                        "match_suggestions": False, "paid_but_open": False, "double_payment": False})
        text = self.render(r)
        self.assertIn("## 3. Mandates to renew\n\nNot checked: no mandate list in your exports.", text)
        self.assertIn("## 4. Match suggestions\n\nNot checked: no bank statement in your exports.", text)
        self.assertEqual(text.count("None."), 0)
        r = self.prep(None, [failed("2026-10-05")], lang="nl", source=source)
        self.assertIn("Niet nagekeken: geen bankafschrift in je exports.", self.render(r))

    # B1, D2
    def test_renewal_tense_and_expiring_mandates_get_no_mail(self):
        store = {"invoices": {"I1": inv("I1", "C2", 10.0, due="2026-10-01")}}
        mands = [mandate("M1", "C1", last_collection_date="2022-01-10"),
                 mandate("M2", "C2", last_collection_date="2023-12-01")]
        r = self.prep(store, mandates=mands, mail_lang="nl")
        by = {x["mandate"]: x for x in r["mandates_to_renew"]}
        self.assertIn("is verlopen op 10 januari 2025, 36 maanden na de laatste domiciliëring op dit mandaat.",
                      by["M1"]["mail"]["body"])
        self.assertNotIn("erop", by["M1"]["mail"]["body"])
        # expiring, customer still active: no mail, the advice to collect before the expiry date
        self.assertEqual((by["M2"]["mail"], by["M2"]["advice"]), (None, "collect_before_expiry"))
        text = self.render(self.prep(store, mandates=mands))
        self.assertIn("mandate M2: expires on December 1, 2026", text)
        self.assertIn("A collection on it before December 1, 2026 keeps it valid, so there is no renewal mail.", text)
        self.assertIn("mandate M1: expired on January 10, 2025", text)
        self.assertNotIn("### C2, mandate M2", text)
        for lang, word in (("en", "expired on January 10, 2025"), ("fr", "a expiré le 10 janvier 2025")):
            r = self.prep(store, mandates=mands, mail_lang=lang)
            self.assertIn(word, [x for x in r["mandates_to_renew"] if x["mandate"] == "M1"][0]["mail"]["body"])

    # B3
    def test_a_mandate_presented_after_its_expiry_names_each_date(self):
        mands = [mandate("M1", "C1", last_collection_date="2023-04-20")]
        cs = [failed("2026-08-04", cust="C1", code="M1", reason="MD01", scheme="CORE")]
        r = self.prep(None, cs, mandates=mands, since=120)
        x = r["mandates_to_renew"][0]
        self.assertEqual((x["counted_from"], x["expiry_date"], x["last_collection"], x["failed_after_expiry"]),
                         ("2023-04-20", "2026-04-20", "2026-08-04", 1))
        self.assertIn("mandate M1: expired on April 20, 2026, 36 months after the last collection presented on it "
                      "before then (April 20, 2023). A collection was presented on it after that, on August 4, 2026, "
                      "and failed.", self.render(r))

    # B2, D4
    def test_new_attempt_mail_asks_for_funds_only_for_insufficient_funds(self):
        cs = self.runs(4, (8, 9), 12, failed_first=3, prefix="A") + self.runs(18, (8, 9), 10, prefix="B")
        am04 = failed("2026-10-05", cust="C1", code="M1", reason="AM04")
        ms03 = failed("2026-10-05", cust="C2", code="M2", reason="MS03")
        r = self.prep(collections=cs + [am04, ms03])
        by = {m["customer"]: m for m in r["mails"]}
        self.assertEqual(by["C1"]["subject"], "New collection of €100.00 on November 18, 2026")
        self.assertIn("Could you make sure there are enough funds in your account that day?", by["C1"]["body"])
        self.assertEqual(by["C2"]["template"], "new_attempt_neutral")
        self.assertNotIn("funds", by["C2"]["body"])
        self.assertIn("If anything changed on your side, just reply to this email.", by["C2"]["body"])
        nl = {m["customer"]: m for m in self.prep(collections=cs + [am04, ms03], mail_lang="nl")["mails"]}
        self.assertEqual(nl["C1"]["subject"], "Nieuwe domiciliëring van €100,00 op 18 november 2026")
        self.assertIn("Wil je ervoor zorgen dat er die dag voldoende saldo op je rekening staat?", nl["C1"]["body"])
        self.assertNotIn("saldo", nl["C2"]["body"])

    def test_conversation_mail_wording(self):
        one = [failed("2026-10-05", cust="C1", code="M1", reason="MS02")]
        two = one + [failed("2026-09-04", cust="C1", code="M1", reason="MD06")]
        self.assertIn("You can simply reply to this email.", self.prep(None, one)["mails"][0]["body"])
        fr1 = self.prep(None, one, mail_lang="fr")["mails"][0]["body"]
        fr2 = self.prep(None, two, mail_lang="fr")["mails"][0]["body"]
        self.assertIn("Nous avons constaté que le prélèvement suivant a été remboursé ou refusé :", fr1)
        self.assertIn("Nous avons constaté que les prélèvements suivants ont été remboursés ou refusés :", fr2)

    # B4
    def test_closing_lines_have_no_doubled_twikey_label(self):
        text = self.render(self.prep(None, [failed("2026-10-05")]))
        after = text.split("What Twikey does:", 1)[1]
        self.assertNotIn("- Twikey:", after)
        self.assertIn("- “This allows us", after)
        fr = self.render(self.prep(None, [failed("2026-10-05")], lang="fr"))
        self.assertIn("Formule : ", fr)
        self.assertNotRegex(fr, r"\S: Professional|Formule:")

    # D5, D8
    def test_partial_payment_says_what_stays_open_and_double_payments_have_their_own_list(self):
        store = {"invoices": {"I1": inv("I1", "C1", 1175.5, ogm="R0001", due="2026-10-01"),
                              "I2": inv("I2", "C2", 80.0, "PAID", ogm="R0002", paid="2026-10-01", due="2026-10-01")}}
        bank = [dict(line(1, "2026-10-02", 600.0, "C1", ogm="R0001"), ogm_invoices=["I1"]),
                dict(line(2, "2026-10-01", 80.0, "C2", ogm="R0002"), ogm_invoices=["I2"]),
                dict(line(3, "2026-10-09", 80.0, "C2", ogm="R0002"), ogm_invoices=["I2"])]
        r = self.prep(store, bank=bank)
        ms = r["match_suggestions"]
        self.assertEqual((ms["lines"][0]["partial_of"], ms["lines"][0]["still_open"]), ("I1", 575.5))
        self.assertEqual([(x["invoice"], x["customer"], x["amount"]) for x in ms["double_payment"]],
                         [("I2", "C2", 80.0)])
        self.assertEqual(r["counts"]["double_payment"], 1)
        text = self.render(r)
        self.assertIn("(the structured communication names this invoice). €600.00 paid, €575.50 still open on "
                      "invoice I1.", text)
        self.assertIn("### Paid twice", text)
        self.assertIn("- Payment of €80.00 on October 9, 2026 from **C2** pays invoice I2 a second time.", text)


class StepsFixTest(unittest.TestCase):
    def test_per_month_totals_are_rounded_once(self):
        # three item types, one item each over three months: 0.3 each when shown, 1.0 together
        cs = [coll("2026-08-04", "failed", reason="AM04"), coll("2026-09-04", "failed", reason="MS02"),
              coll("2026-10-05", "failed", reason="ED05")]
        r = checks.steps({"invoices": {}}, [], cs, [], D(2026, 10, 31))
        shown = [i["per_month"] for i in r["items"] if i["per_month"]]
        self.assertEqual(shown, [0.3, 0.3, 0.3])
        self.assertEqual(r["per_month_total"], 1.0)
        self.assertEqual(r["per_month_steps_total"], round((4 + 4 + 2) / 3.0, 1))

    def test_double_payments_are_their_own_item(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, "PAID", "R0001", paid="2026-09-01")}}
        bank = [line(1, "2026-09-01", 100.0, "C1", "R0001"), line(2, "2026-09-02", 100.0, "C1", "R0001")]
        by = {i["id"]: i for i in checks.steps(store, [], [], bank, D(2026, 10, 31))["items"]}
        self.assertEqual((by["double_payment"]["count"], by["unmatched"]["count"]), (1, 0))
        self.assertEqual(by["double_payment"]["checklist"], ["contact the customer", "refund or credit the amount",
                                                             "record it"])
        self.assertEqual(by["unmatched"]["label"], "payments to book by hand (no match, partial or bundled)")

    def test_an_item_type_without_its_export_is_not_checked(self):
        store = {"invoices": {"I1": inv("I1", "C1", 10.0, "BOOKED", due="2026-10-01", date="2026-09-01")}}
        r = checks.steps(store, [], [coll("2026-09-01", "failed", reason="AM04")], [], D(2026, 10, 31))
        by = {i["id"]: i for i in r["items"]}
        self.assertFalse(by["unmatched"]["checked"])
        self.assertEqual(by["unmatched"]["not_checked"], "Not checked: no bank statement in your exports.")
        self.assertFalse(by["mandate_renew"]["checked"])
        self.assertTrue(by["late_invoice"]["checked"])
        self.assertIn("unmatched", r["not_checked"])


class GoliveFixTest(unittest.TestCase):
    def test_never_used_mandates_are_not_counted_to_renew(self):
        mands = [mandate("M1", "C1", last_collection_date="2022-01-10"), mandate("M2", "C2", signed_date="2020-01-01")]
        mand = checks.mandate_health(mands, [], D(2026, 10, 31))
        term = checks.terms({"invoices": {}}, dict(DEFAULT_CONFIG), D(2026, 10, 31))
        g = checks.golive({"invoices": {}}, [], mand, term)
        self.assertEqual((g["mandates_to_renew"], g["mandates_never_used"]), (1, 1))
        self.assertEqual(mand["to_renew"], 1)


class MonthFinalTest(MonthHelpers, unittest.TestCase):
    """Part 1 agrees with the one mail, a conversation mail says what else to ask, mails with several debts read
    in the plural, the B2B mail names the right mandate, and every new date has 14 days' notice."""

    def render(self, r):
        from xray import month
        return month.render(r, today=self.TODAY)

    def test_a_new_attempt_waits_for_the_new_mandate_or_registration_the_mail_asks_for(self):
        # AM04 on M1 is worth a new attempt, AC04 on M2 needs a new mandate: one mail, new_mandate
        cs = [failed("2026-10-05", cust="C1", code="M1"), failed("2026-10-05", cust="C1", code="M2", reason="AC04")]
        r = self.prep(collections=cs)
        self.assertEqual([a["mail_reason"] for a in r["new_attempts"]], ["new_mandate"])
        self.assertIn("The mail in part 2 asks this customer to sign a new mandate: present it again once it is "
                      "signed.", self.render(r))
        # MD01 on B2B mandate M2: the mail asks to register it, part 1 waits for that
        cs = [failed("2026-10-05", cust="C1", code="M1"),
              failed("2026-10-05", cust="C1", code="M2", reason="MD01", scheme="B2B")]
        r = self.prep(collections=cs)
        self.assertEqual([a["mail_reason"] for a in r["new_attempts"]], ["b2b_register"])
        self.assertIn("present it again once that is done.", self.render(r))
        # the B2B mail names only the mandate the bank does not know
        self.assertIn("B2B mandate M2 is not registered", r["mails"][0]["body"])
        self.assertNotIn("M1 and M2", r["mails"][0]["subject"] + r["mails"][0]["body"])
        # alone, a new attempt has no note
        r = self.prep(collections=cs[:1])
        self.assertNotIn("The mail in part 2", self.render(r))

    def test_a_conversation_mail_says_what_else_to_ask_for(self):
        cs = [failed("2026-09-04", cust="C1", code="M1", reason="MS02"),
              failed("2026-10-05", cust="C1", code="M2", reason="AC04")]
        r = self.prep(collections=cs)
        self.assertEqual([m["reason"] for m in r["mails"]], ["conversation"])
        self.assertIn("This customer also needs a new mandate (mandate M2): add the request to sign one to this "
                      "mail.", self.render(r))
        cs[1] = failed("2026-10-05", cust="C1", code="M2", reason="MD01", scheme="B2B")
        for lang, want in (("en", "B2B mandate M2 is not registered at this customer's bank"),
                           ("nl", "B2B-mandaat M2 is niet geregistreerd bij de bank van deze klant"),
                           ("fr", "Le mandat B2B M2 n'est pas enregistré auprès de la banque de ce client")):
            self.assertIn(want, self.render(self.prep(collections=cs, lang=lang)))
        # a conversation alone needs nothing more
        self.assertNotIn("also needs", self.render(self.prep(collections=cs[:1])))

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
            mails = {m["customer"]: m for m in self.prep(collections=cs, mail_lang=lang)["mails"]}
            self.assertEqual(mails["C1"]["subject"], subject)
            self.assertIn(attempt, mails["C1"]["body"])
            self.assertIn(mandate_line, mails["C2"]["body"])
            # one debt keeps the singular
            one = self.prep(collections=cs[:-3], mail_lang=lang)["mails"][0]
            self.assertNotRegex(one["subject"] + one["body"], r"(?i)\bthese\b|deze domiciliëringen|ces prélèvements")

    def test_a_part_paid_since_is_never_asked_again(self):
        cs = [failed("2026-10-05", cust="C1", code="M1")]
        # the customer paid €60 of the €100 invoice by transfer after the failure, the books not updated yet
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20", ogm="R0001")}}
        bank = [dict(line(1, "2026-10-12", 60.0, "C1", ogm="R0001"), ogm_invoices=["I1"])]
        # the same, with the books already showing €40 open and no bank statement
        booked = {"invoices": {"I1": dict(inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20"),
                                          xray={"open_amount": 40.0})}}
        for st, bk in ((store, bank), (booked, [])):
            r = self.prep(st, cs, bk)
            a, mail = r["new_attempts"][0], r["mails"][0]
            self.assertEqual((a["amount"], a["still_owed"], mail["amount"]), (100.0, 40.0, 40.0))
            self.assertIn("New collection of €40.00 on", mail["subject"])
            self.assertIn("- invoice I1: €40.00 of €100.00 still open, collection of October 5, 2026", mail["body"])
            self.assertIn("€40.00 of €100.00 still open, failed on October 5, 2026.", self.render(r))
            self.assertNotIn("€100.00 again", mail["body"])
        for lang, want in (("nl", "- factuur I1: €40,00 van €100,00 staat nog open, domiciliëring van 5 oktober 2026"),
                           ("fr", "- facture I1 : €40,00 sur €100,00 encore ouverts, prélèvement du 5 octobre 2026")):
            self.assertIn(want, self.prep(store, cs, bank, mail_lang=lang)["mails"][0]["body"])
        # a later unmatched payment that covers what is still open closes it
        r = self.prep(booked, cs, [line(2, "2026-10-20", 40.0, "C1")])
        self.assertEqual((r["new_attempts"], r["closed"]["bank_credit"]), ([], 1))

    def test_older_open_debts_are_counted_apart(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-04-04", date="2026-03-05"),
                              "I2": inv("I2", "C1", 100.0, "PAID", paid="2026-05-20", due="2026-05-05",
                                        date="2026-04-05")}}
        cs = [failed("2026-04-07", cust="C1", code="M1", reason="MD06"),   # still open: counted apart
              failed("2026-05-05", cust="C1", code="M1", reason="MD06"),   # its invoice was paid since: closed
              failed("2026-10-05", cust="C1", code="M1", reason="MS02")]
        r = self.prep(store, cs)
        self.assertEqual((len(r["mails"][0]["items"]), r["older_open"]), (1, 1))
        self.assertIn("Nothing was sent. The drafts cover the failed collections of the last 90 days that are still "
                      "open.\n", self.render(r))
        self.assertIn("Older failed collections whose invoice is still open in your books, from before August 2, "
                      "2026: one. They are not in these drafts.", self.render(r))
        # Dutch writes the count one as "één", never the article "een"
        self.assertIn("van vóór 2 augustus 2026: één.", self.render(self.prep(store, cs, lang="nl")))
        # a longer window takes it in
        r = self.prep(store, cs, since=240)
        self.assertEqual((len(r["mails"][0]["items"]), r["older_open"]), (2, 0))
        self.assertNotIn("Older failed collections", self.render(r))
        # an old failure without a known invoice may well be paid: not counted
        r = self.prep(store, [failed("2025-11-05", cust="C1", code="M1", reason="MD06")] + cs[1:])
        self.assertEqual(r["older_open"], 0)

    def test_a_collection_without_a_known_invoice_asks_to_check_the_books(self):
        r = self.prep(collections=[failed("2026-10-05", cust="C1", code="M1")])
        self.assertIsNone(r["new_attempts"][0]["invoice"])
        text = self.render(r)
        self.assertIn("No invoice found for it in your export: check in your books that the amount is still owed.",
                      text)
        self.assertIn("No invoice was found in your export for a collection in this mail: check in your books that "
                      "the amount is still owed before you send it.", text)
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, due="2026-10-05", date="2026-09-20")}}
        self.assertNotIn("No invoice", self.render(self.prep(store, [failed("2026-10-05", cust="C1", code="M1")])))

    def test_left_out_debts_are_called_no_longer_owed(self):
        store = {"invoices": {"I1": inv("I1", "C1", 100.0, "CANCELLED", due="2026-10-05", date="2026-09-20")}}
        text = self.render(self.prep(store, [failed("2026-10-05", cust="C1", code="M1")]))
        self.assertIn("Left out because they are no longer owed: one", text)
        self.assertNotIn("money came in", text)

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


if __name__ == "__main__":
    unittest.main()
