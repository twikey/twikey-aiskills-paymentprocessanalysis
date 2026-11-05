import datetime as dt
import json
import unittest

from tests import helpers  # noqa: F401
from xray import csvparse


def read(text, name="x.csv", user_map=None, encoding="utf-8"):
    return csvparse.read_csv(text.encode(encoding), name, user_map)


class HeaderDetectionTest(unittest.TestCase):
    def test_english_invoices_comma_iso_dates(self):
        r = read('Invoice number,Customer,Customer number,Invoice date,Due date,Amount,Status,Paid date,Email,Address\n'
                 'INV-1,Acme Test Ltd,K1,2026-01-15,2026-02-14,"1,250.50",Paid,2026-02-10,a@x.example,"Street 1, City"\n'
                 'INV-2,Acme Test Ltd,K1,2026-02-15,2026-03-17,99.95,Open,,a@x.example,"Street 1, City"\n')
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "invoices")
        self.assertEqual(r["delimiter"], ",")
        self.assertEqual([x["amount"] for x in r["rows"]], [1250.5, 99.95])
        self.assertEqual(r["rows"][0]["status"], "paid")
        self.assertEqual(r["rows"][1]["status"], "open")
        self.assertEqual(r["rows"][0]["due_date"], dt.date(2026, 2, 14))
        self.assertEqual(r["columns_dropped"], ["Email", "Address"])
        self.assertNotIn("email", json.dumps(r["rows"], default=str).lower())

    def test_dutch_invoices_with_preamble_and_decimal_comma(self):
        r = read("Export boekhouding Fictief\n\nFactuurnr;Klant;Factuurdatum;Vervaldatum;Bedrag;Openstaand\n"
                 "F1;Klant A;15-01-2026;14-02-2026;1.025,50;0,00\nF2;Klant B;20-01-2026;19-02-2026;99,00;99,00\n")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "invoices")
        self.assertEqual(r["delimiter"], ";")
        self.assertEqual([x["amount"] for x in r["rows"]], [1025.5, 99.0])
        self.assertEqual([x["open_amount"] for x in r["rows"]], [0.0, 99.0])
        self.assertEqual(r["rows"][0]["invoice_date"], dt.date(2026, 1, 15))

    def test_french_failed_collections(self):
        r = read("Date d'échéance;Montant;Nom du débiteur;Code retour;Référence du mandat;Schéma\n"
                 "04/08/2026;125,00;Client Un;AM04 Provision insuffisante;M-1;Core\n"
                 "14/08/2026;80,00;Client Deux;md01;M-2;B2B\n")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "failed_collections")
        self.assertEqual(r["columns_kept"]["Date d'échéance"], "collection_date")
        self.assertEqual([x["reason_code"] for x in r["rows"]], ["AM04", "MD01"])
        self.assertEqual([x["scheme"] for x in r["rows"]], ["CORE", "B2B"])

    def test_bank_export_with_credit_and_debit_columns(self):
        r = read("Rekeningnummer;Datum;Omschrijving;Naam tegenpartij;Rekening tegenpartij;Credit;Debet\n"
                 "BE00;03/08/2026;Factuur 7;KLANT A;BE111;100,00;\nBE00;13/08/2026;Huur;IMMO;BE222;;-50,00\n")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "bank")
        self.assertEqual([x["amount"] for x in r["rows"]], [100.0, -50.0])
        # the company's own account is read for one check (own transfers, the same account twice), not stored
        self.assertNotIn("Rekeningnummer", r["columns_dropped"])
        self.assertEqual(r["read_not_stored"], ["Omschrijving", "Rekeningnummer"])

    def test_cp1252_file(self):
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status\nF1;Débiteur Één;15/01/2026;10,00;Open\n",
                 encoding="cp1252")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["encoding"], "cp1252")
        self.assertEqual(r["rows"][0]["customer_name"], "Débiteur Één")


class FailClosedTest(unittest.TestCase):
    SECRET = "Klant Geheim"

    def test_unknown_layout_prints_no_cell_values(self):
        r = read("Doc;Rel;Dat;Verv;Bedr\nF1;%s;01/02/2026;03/03/2026;10,00\n" % self.SECRET)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertNotIn(self.SECRET, json.dumps(r))

    def test_known_headers_but_unknown_kind_shows_headers_only(self):
        r = read("Datum;Bedrag;Naam\n01/02/2026;10,00;%s\n" % self.SECRET)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertEqual([c["header"] for c in r["columns"]], ["Datum", "Bedrag", "Naam"])
        self.assertEqual([c["values"] for c in r["columns"]], ["date", "amount", "text, 12 chars"])
        self.assertNotIn(self.SECRET, json.dumps(r))

    # ------------------------------------------------------------------ cell values never shown

    def test_preamble_with_values_is_never_shown_as_headers(self):
        text = ("Rekening;BE68539007547034;Naam;Jan Peeters\n"
                "Datum;Bedrag;Omschrijving;Tegenpartij\n"
                "01/02/2026;10,00;betaling jan.peeters@mail.example;Jan Peeters\n")
        r = read(text)
        dump = json.dumps(r)
        for secret in ("BE68539007547034", "Jan Peeters", "jan.peeters@mail.example"):
            self.assertNotIn(secret, dump)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertEqual([c["header"] for c in r["columns"]], ["Datum", "Bedrag", "Omschrijving", None])

    def test_file_without_a_header_row_shows_positions_and_shapes(self):
        text = ("Bakkerij Geheim BV;BE68539007547034;boekhouding@geheim.example;01/02/2026;121,00\n"
                "Slagerij Geheim BV;BE71096123456769;info@slager.example;02/02/2026;99,50\n")
        r = read(text)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertFalse(r["has_header"])
        self.assertEqual([c["header"] for c in r["columns"]], [None] * 5)
        self.assertEqual([c["values"] for c in r["columns"]],
                         ["text, 18 chars", "IBAN-like", "e-mail-like", "date", "amount"])
        for secret in ("Geheim", "BE68539007547034", "geheim.example", "Slagerij"):
            self.assertNotIn(secret, json.dumps(r))

    def test_header_row_with_a_name_among_the_headers(self):
        # a known header next to an unknown one: the unknown header is shown by position only
        r = read("Factuurnummer;Bedrag;Jan Peeters\nF1;10,00;x\n")
        self.assertEqual(r["status"], "needs_mapping")
        self.assertNotIn("Jan Peeters", json.dumps(r))

    def test_headerless_file_mapped_by_position(self):
        text = "F1;Klant Een;01/02/2026;121,00;0,00\nF2;Klant Twee;03/02/2026;99,50;99,50\n"
        m = {"#1": "invoice_number", "#2": "customer_name", "#3": "invoice_date", "#4": "amount", "#5": "open_amount"}
        r = read(text, user_map=m)
        self.assertEqual(r["status"], "ok", r.get("reason"))
        self.assertEqual(len(r["rows"]), 2)
        self.assertEqual(r["columns_kept"], {"column 1": "invoice_number", "column 2": "customer_name",
                                             "column 3": "invoice_date", "column 4": "amount",
                                             "column 5": "open_amount"})

    def test_user_map_recovers_unknown_layout(self):
        text = "Doc;Rel;Dat;Verv;Bedr;Bet\nF1;%s;01/02/2026;03/03/2026;10,00;02/03/2026\n" % self.SECRET
        m = {"Doc": "invoice_number", "Rel": "customer_name", "Dat": "invoice_date", "Verv": "due_date",
             "Bedr": "amount", "Bet": "paid_date"}
        r = read(text, user_map=m)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "invoices")
        self.assertEqual(r["rows"][0]["due_date"], dt.date(2026, 3, 3))

    def test_user_kind_override(self):
        r = read("Datum;Bedrag;Naam\n01/02/2026;10,00;%s\n" % self.SECRET,
                 user_map={"@kind": "bank", "Datum": "booking_date"})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["kind"], "bank")

    def test_missing_required_field(self):
        r = read("Factuurnummer;Klant;Factuurdatum\nF1;A;01/02/2026\n")
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("amount", r["reason"])

    def test_two_columns_for_one_field(self):
        r = read("Factuurnummer;Klant;Klantnaam;Factuurdatum;Bedrag\nF1;A;A;01/02/2026;1,00\n")
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("customer_name", r["reason"])

    def test_mixed_decimal_marks(self):
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag\nF1;A;01/02/2026;1.234,56\nF2;B;01/02/2026;\"1,234.56\"\n")
        self.assertEqual(r["status"], "needs_mapping")

    def test_day_and_month_cannot_be_told_apart(self):
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag\nF1;A;13/02/2026;1,00\nF2;B;02/13/2026;1,00\n")
        self.assertEqual(r["status"], "needs_mapping")

    def test_month_first_dates(self):
        r = read("Invoice number,Customer,Invoice date,Amount,Status\nI1,A,02/13/2026,1.00,Open\n")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["rows"][0]["invoice_date"], dt.date(2026, 2, 13))

    def test_ambiguous_dates_are_reported_as_assumption(self):
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status\nF1;A;05/02/2026;1,00;Open\n")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["rows"][0]["invoice_date"], dt.date(2026, 2, 5))
        self.assertTrue(any("day/month/year" in a for a in r["assumptions"]))

    def test_too_many_unreadable_rows(self):
        rows = "".join("F%d;A;%s;1,00;Open\n" % (i, "01/02/2026" if i < 6 else "geen datum") for i in range(10))
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status\n" + rows)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("could not be read", r["reason"])

    def test_invoices_without_status_paid_date_or_open_amount_stop(self):
        # Without one of them every invoice would count as open and overdue (60 invoices, DSO 360).
        rows = "".join("F%02d%02d;Klant %d BV;15/%02d/2026;1.000,00\n" % (m, c, c, m)
                       for m in range(1, 13) for c in range(1, 6))
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag\n" + rows)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("status, paid_date or open_amount", r["reason"])
        for extra, value in (("Status", "Betaald"), ("Betaaldatum", "20/01/2026"), ("Openstaand", "0,00")):
            ok = read("Factuurnummer;Klant;Factuurdatum;Bedrag;%s\nF1;A;15/01/2026;1,00;%s\n" % (extra, value))
            self.assertEqual(ok["status"], "ok", extra)

    def test_empty_status_paid_date_and_open_amount_columns_stop(self):
        # the columns are there, but no row holds a value in any of them
        rows = "".join("F%02d;Klant %d BV;15/01/2026;1.000,00;;;\n" % (c, c) for c in range(1, 46))
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status;Betaaldatum;Openstaand\n" + rows)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("no row has a status, a paid date or an open amount", r["reason"])
        # rows left out for another reason keep their own message
        rows = "".join(";Klant %d BV;15/01/2026;1.000,00;Open;;\n" % c for c in range(1, 46))
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status;Betaaldatum;Openstaand\n" + rows)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("no invoice number or amount", r["reason"])

    def test_rows_without_status_are_left_out_and_counted(self):
        rows = ("F1;A;15/01/2026;1,00;Betaald\nF2;B;15/01/2026;2,00;\nF3;C;15/01/2026;3,00;Open\n"
                "F4;D;15/01/2026;4,00;\nF5;E;15/01/2026;5,00;\n")
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status\n" + rows)
        self.assertEqual(r["status"], "ok", r.get("reason"))  # three of five left out does not stop intake
        self.assertEqual([x["invoice_number"] for x in r["rows"]], ["F1", "F3"])
        self.assertEqual(r["skipped"], {"status unknown": 3})

    def test_unknown_bank_direction_words_stop(self):
        r = read("Boekingsdatum;Bedrag;D/C;Rekening tegenpartij;Naam tegenpartij\n"
                 "10/10/2026;800,00;Inkomend;BE68539007547034;Alfa BV\n"
                 "11/10/2026;5.200,00;Uitgaand;BE71096123456769;Verhuurder NV\n")
        self.assertEqual(r["status"], "needs_mapping")
        self.assertIn("money in or out", r["reason"])
        self.assertNotIn("Inkomend", json.dumps(r))
        ok = read("Boekingsdatum;Bedrag;D/C;Rekening tegenpartij;Naam tegenpartij\n"
                  "10/10/2026;800,00;C;BE68539007547034;Alfa BV\n11/10/2026;5.200,00;D;BE71096123456769;X\n")
        self.assertEqual([x["amount"] for x in ok["rows"]], [800.0, -5200.0])

    def test_reason_words_are_never_kept(self):
        r = read("Datum inning;Bedrag;Debiteur;Reden\n05/10/2026;100,00;Jan Peeters;MD06\n"
                 "05/10/2026;120,00;Anna Claes;Anna weigert betaling\n05/10/2026;130,00;Marc Dubois;Marc: geen dekking\n"
                 "05/10/2026;140,00;Luc Smet;LUC1 bank\n05/10/2026;150,00;Emma Wouters;EMMA\n")
        self.assertEqual(r["status"], "ok", r.get("reason"))
        self.assertEqual([x["reason_code"] for x in r["rows"]], ["MD06", None, None, None, None])
        self.assertEqual([x["reason_proprietary"] for x in r["rows"]], [False, True, True, True, True])
        dump = json.dumps([{k: v for k, v in x.items() if k in ("reason_code", "reason_proprietary")}
                           for x in r["rows"]])
        for word in ("ANNA", "MARC", "LUC1", "EMMA", "Anna", "Emma"):
            self.assertNotIn(word, dump)

    def test_unknown_status_values_without_paid_info(self):
        r = read("Factuurnummer;Klant;Factuurdatum;Bedrag;Status\nF1;A;01/02/2026;1,00;%s\n" % self.SECRET)
        self.assertEqual(r["status"], "needs_mapping")
        self.assertNotIn(self.SECRET, json.dumps(r))

    def test_no_header_row(self):
        r = read("a;b;c\n1;2;3\n")
        self.assertEqual(r["status"], "needs_mapping")
        self.assertEqual([c["header"] for c in r["columns"]], [None, None, None])


class ValueTest(unittest.TestCase):
    def test_amounts(self):
        cases = [("1.025,50", ",", 1025.5), ("-845,20", ",", -845.2), ("845,20-", ",", -845.2), ("(12.50)", ".", -12.5),
                 ("€ 1 250,00", ",", 1250.0), ("EUR 99.99", ".", 99.99), ("1'234.50", ".", 1234.5), ("abc", ".", None)]
        for value, mark, want in cases:
            self.assertEqual(csvparse.parse_amount(value, mark), want, value)

    def test_decimal_mark_detection(self):
        self.assertEqual(csvparse.detect_decimal_mark(["1.025,50", "3,00"], ";")[0], ",")
        self.assertEqual(csvparse.detect_decimal_mark(["1,025.50", "3.00"], ",")[0], ".")
        mark, note = csvparse.detect_decimal_mark(["1.025", "300"], ";")
        self.assertEqual(mark, ",")
        self.assertIsNotNone(note)

    def test_reason_code_reading(self):
        self.assertEqual(csvparse.reason_code("AM04"), ("AM04", "ok"))
        self.assertEqual(csvparse.reason_code("ms02 - refused"), ("MS02", "ok"))
        self.assertEqual(csvparse.reason_code("CNOR"), ("CNOR", "ok"))
        self.assertEqual(csvparse.reason_code("ED05"), ("ED05", "ok"))  # EPC list
        self.assertEqual(csvparse.reason_code("insufficient funds"), (None, "proprietary"))
        self.assertEqual(csvparse.reason_code("ANNA"), (None, "proprietary"))  # four letters, not a code
        self.assertEqual(csvparse.reason_code("SL11"), (None, "proprietary"))  # in neither list
        self.assertEqual(csvparse.reason_code(""), (None, "empty"))

    def test_allow_list(self):
        from xray import reasons
        self.assertEqual(len(reasons.TWIKEY), 25)
        self.assertEqual(len(reasons.EPC_SDD), 25)
        self.assertEqual(sorted(reasons.ALLOWED - reasons.TWIKEY), ["ED05"])
        self.assertEqual(sorted(reasons.TWIKEY - set(reasons.EPC_SDD)), ["PY01"])

    def test_words(self):
        self.assertEqual(csvparse.word("method", "Domiciliëring"), ("sdd", True))
        self.assertEqual(csvparse.word("method", "Virement"), ("transfer", True))
        self.assertEqual(csvparse.word("yesno", "Nee"), (False, True))
        self.assertEqual(csvparse.word("status", "Gedeeltelijk betaald"), ("open", True))
        self.assertEqual(csvparse.word("status", "zzz"), (None, False))

    def test_synonym_table_has_no_double_meaning(self):
        # building the table raises on a header that maps to two fields; check a few on purpose
        self.assertEqual(csvparse.SYNONYMS["vervaldatum"], "due_date")
        self.assertEqual(csvparse.SYNONYMS["rekening tegenpartij"], "counterparty_iban")
        self.assertEqual(csvparse.SYNONYMS["rekening"], "own_account")
        self.assertNotIn("valuta", csvparse.SYNONYMS)  # currency in NL, value date in BE bank exports


if __name__ == "__main__":
    unittest.main()
