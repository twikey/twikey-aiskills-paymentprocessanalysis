"""Reason codes the plugin may show.

Only codes on this allow-list are kept and printed: Twikey's 25 reason codes (data/rcodes_en.json)
plus the SEPA Direct Debit R-transaction reason codes of the EPC "Guidance on reason codes for SDD
R-transactions" (EPC173-14, version 8.0, November 28, 2024, section 3), which applies to the SDD Core
and the SDD B2B rulebook. Anything else in a reason field, a four-letter word such as a first name
included, becomes "proprietary reason (not shown)" and its text is dropped.
"""
import json
import os

from .common import DATA_DIR

# EPC173-14 v8.0, section 3: code -> "Reason specified in the Rulebook", word for word.
EPC_SDD = {
    "AC01": "Account Identifier incorrect (i.e. invalid IBAN of the Debtor).",
    "AC04": "Account closed.",
    "AC06": "Account blocked.",
    "AC13": "Debtor account is a consumer account. (For SDD B2B collections only)",
    "AG01": "Direct Debit forbidden on this account for regulatory reasons.",
    "AG02": "Operation code/ transaction code/ sequence type incorrect, invalid file format.",
    "AM04": "Insufficient funds.",
    "AM05": "Duplicate collection.",
    "BE05": "Identifier of the Creditor Incorrect.",
    "CNOR": "Creditor PSP is not registered under this BIC in the CSM.",
    "DNOR": "Debtor PSP is not registered under this BIC in the CSM.",
    "ED05": "Settlement of the collection failed",
    "FF01": "Invalid file format.",
    "MD01": "No valid mandate",
    "MD02": "Mandate data missing or incorrect.",
    "MD06": "Disputed authorized transaction. (For SDD Core collections only)",
    "MD07": "Debtor Deceased.",
    "MS02": "Refusal by the Debtor.",
    "MS03": "Reason not specified.",
    "RC01": "PSP identifier incorrect (i.e. invalid BIC).",
    "RR01": "Regulatory Reason.",
    "RR02": "Regulatory Reason.",
    "RR03": "Regulatory Reason.",
    "RR04": "Regulatory Reason.",
    "SL01": "Due to specific service offered by the Debtor PSP.",
}
EPC_SOURCE = ("https://europeanpaymentscouncil.eu/sites/default/files/kb/file/2024-11/"
              "EPC173-14%20v8.0%20Guidance%20on%20Reason%20Codes%20for%20SDD%20R-transactions.pdf")


def _twikey_codes():
    with open(os.path.join(DATA_DIR, "rcodes_en.json"), encoding="utf-8") as f:
        return {r["CODE"].strip() for r in json.load(f)}


TWIKEY = frozenset(_twikey_codes())
ALLOWED = frozenset(TWIKEY | set(EPC_SDD))


def allowed(code):
    return (code or "").strip().upper() in ALLOWED
