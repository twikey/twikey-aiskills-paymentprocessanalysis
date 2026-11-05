"""
Standard receivables formulas: invoice helpers, days late, on-time share, a payer score, aging buckets
and countback DSO. The function bodies are pinned by hash in tests/test_claims.py, so they do not
change by accident.

- TODAY is set by twikey_xray.py to the as-of date of the workspace before any call.
- DEFAULT_CONFIG holds the one key that money() reads.

The functions read a store.json with customer codes in place of names
(customer.customerNumber = customer.companyName = "C001", no e-mail).
"""
import datetime as dt

TODAY = dt.date.today()
DEFAULT_CONFIG = {"currency": "EUR"}


# --------------------------------------------------------------------------- invoice helpers

def d(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def cust_key(inv):
    c = inv.get("customer") or {}
    return str(c.get("customerNumber") or c.get("companyName") or c.get("email") or "unknown")


def cust_name(inv):
    c = inv.get("customer") or {}
    if c.get("companyName"):
        return c["companyName"]
    n = " ".join(x for x in [c.get("firstname"), c.get("lastname")] if x)
    return n or cust_key(inv)


def paid_date(inv):
    pays = inv.get("lastpayment") or []
    dates = [d(p.get("date")) for p in pays if d(p.get("date"))]
    return max(dates) if dates else None


def pay_method(inv):
    pays = inv.get("lastpayment") or []
    return pays[-1].get("method") if pays else None


def has_mandate(inv):
    pays = inv.get("lastpayment") or []
    meta = inv.get("meta") or {}
    return bool(meta.get("mndtId") or meta.get("mandate") or any(p.get("method") == "sdd" for p in pays))


def is_paid(inv, cfg):
    return inv.get("state") in cfg["paid_states"]


def is_closed(inv, cfg):
    return inv.get("state") in cfg["closed_states"]


def is_open(inv, cfg):
    return not is_paid(inv, cfg) and not is_closed(inv, cfg)


def days_overdue(inv, on=None):
    due = d(inv.get("duedate"))
    return ((on or TODAY) - due).days if due else None


def money(x, cfg=None):
    return "%s %s" % ((cfg or DEFAULT_CONFIG)["currency"], format(round(float(x or 0), 2), ",.2f"))


def slim(inv, cfg):
    return {
        "id": inv.get("id"), "number": inv.get("number"), "customer": cust_name(inv),
        "customer_number": cust_key(inv), "email": (inv.get("customer") or {}).get("email"),
        "lang": (inv.get("customer") or {}).get("l") or (inv.get("customer") or {}).get("lang"),
        "amount": float(inv.get("amount") or 0), "date": inv.get("date"), "duedate": inv.get("duedate"),
        "state": inv.get("state"), "days_overdue": days_overdue(inv),
        "mandate": has_mandate(inv), "pay_url": inv.get("url"),
        "key_client": cust_key(inv) in cfg["key_clients"] or cust_name(inv) in cfg["key_clients"],
    }


# --------------------------------------------------------------------------- analytics

def customer_stats(store, cfg):
    by = {}
    for inv in store["invoices"].values():
        if is_closed(inv, cfg):
            continue
        k = cust_key(inv)
        s = by.setdefault(k, {"customer_number": k, "customer": cust_name(inv), "email": (inv.get("customer") or {}).get("email"),
                              "invoices": 0, "paid": 0, "open_amount": 0.0, "overdue_amount": 0.0,
                              "max_days_overdue": 0, "late_days": [], "on_time": 0, "mandate": False,
                              "key_client": False})
        s["invoices"] += 1
        s["mandate"] = s["mandate"] or has_mandate(inv)
        s["key_client"] = k in cfg["key_clients"] or s["customer"] in cfg["key_clients"]
        if is_paid(inv, cfg):
            pd_, due = paid_date(inv), d(inv.get("duedate"))
            if pd_ and due:
                s["paid"] += 1
                late = (pd_ - due).days
                s["late_days"].append(late)
                s["on_time"] += late <= 0
        else:
            amt = float(inv.get("amount") or 0)
            s["open_amount"] += amt
            od = days_overdue(inv) or 0
            if od > 0:
                s["overdue_amount"] += amt
                s["max_days_overdue"] = max(s["max_days_overdue"], od)
    for s in by.values():
        ld = s.pop("late_days")
        s["avg_days_late"] = round(sum(ld) / len(ld), 1) if ld else None
        s["on_time_pct"] = round(100 * s["on_time"] / s["paid"]) if s["paid"] else None
        # score 0-100 (100 = great payer)
        score = 100.0
        if s["avg_days_late"] is not None:
            score -= max(0, s["avg_days_late"]) * 1.5
        if s["on_time_pct"] is not None:
            score -= (100 - s["on_time_pct"]) * 0.3
        score -= min(30, s["max_days_overdue"] * 0.5)
        if s["mandate"]:
            score += 10
        s["score"] = int(max(0, min(100, round(score))))
        s["risk"] = "low" if s["score"] >= 75 else "medium" if s["score"] >= 50 else "high"
        s["repeat_late"] = (s["paid"] >= 3 and (s["on_time_pct"] or 0) < 50)
        s["open_amount"] = round(s["open_amount"], 2)
        s["overdue_amount"] = round(s["overdue_amount"], 2)
    return by


def aging(store, cfg):
    buckets = ["not_due", "1-30", "31-60", "61-90", "90+"]
    rows, total = {}, dict.fromkeys(buckets, 0.0)
    for inv in store["invoices"].values():
        if not is_open(inv, cfg):
            continue
        od = days_overdue(inv) or 0
        b = "not_due" if od <= 0 else "1-30" if od <= 30 else "31-60" if od <= 60 else "61-90" if od <= 90 else "90+"
        r = rows.setdefault(cust_key(inv), dict({"customer": cust_name(inv)}, **dict.fromkeys(buckets, 0.0)))
        amt = float(inv.get("amount") or 0)
        r[b] += amt
        total[b] += amt
    for r in rows.values():
        r["total"] = round(sum(r[b] for b in buckets), 2)
    total["total"] = round(sum(total[b] for b in buckets), 2)
    return {"as_of": str(TODAY), "buckets": buckets,
            "customers": sorted(rows.values(), key=lambda r: -r["total"]), "total": total}


def dso(store, cfg):
    months = {}
    for inv in store["invoices"].values():
        if not is_paid(inv, cfg):
            continue
        pd_, issued, due = paid_date(inv), d(inv.get("date")), d(inv.get("duedate"))
        if not (pd_ and issued):
            continue
        m = months.setdefault(pd_.strftime("%Y-%m"), {"paid": 0, "days_to_pay": [], "days_late": []})
        m["paid"] += 1
        m["days_to_pay"].append((pd_ - issued).days)
        if due:
            m["days_late"].append((pd_ - due).days)
    trend = []
    for k in sorted(months):
        m = months[k]
        trend.append({"month": k, "paid_invoices": m["paid"],
                      "avg_days_to_pay": round(sum(m["days_to_pay"]) / len(m["days_to_pay"]), 1),
                      "avg_days_late": round(sum(m["days_late"]) / len(m["days_late"]), 1) if m["days_late"] else None})
    # countback-style DSO: open receivables / trailing 90d billing * 90
    since = TODAY - dt.timedelta(days=90)
    billed = sum(float(i.get("amount") or 0) for i in store["invoices"].values()
                 if d(i.get("date")) and d(i.get("date")) >= since and not is_closed(i, cfg))
    open_ar = sum(float(i.get("amount") or 0) for i in store["invoices"].values() if is_open(i, cfg))
    return {"as_of": str(TODAY), "dso_90d": round(open_ar / billed * 90, 1) if billed else None,
            "open_receivables": round(open_ar, 2), "billed_last_90d": round(billed, 2), "trend": trend}
