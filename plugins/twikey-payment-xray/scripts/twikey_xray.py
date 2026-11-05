#!/usr/bin/env python3
"""
twikey_xray.py - Twikey Payment X-ray: where a company's payment process leaks, from its own exports.

Standard library only (Python 3.8+). No network calls. Read-only: it never sends, collects or changes
anything. Only `intake` opens the raw exports, and it writes coded data to the workspace and the key
(codes back to names) next to the raw files. `report` puts the names back into the final report on
this computer and prints only its path, and so does `month` for its work pack (customer mail drafts and match
suggestions: drafts only, nothing is sent, no bank file is written). Every other command prints counts, amounts,
dates and codes.

Workspace folder (config.json + the coded ledger) is resolved from:
  --home PATH  >  $TWIKEY_XRAY_HOME  >  ./twikey-xray-workspace

  init --raw FOLDER [--lang en|nl|fr] [--force]    set the raw export folder (outside Claude's folder)
  demo [--raw FOLDER]                               load the fictional demo company and run intake
  intake [--map N:COLUMN=FIELD ...] [--skip N ...]  N is the file number intake shows ("file 2" is 2),
                                                    COLUMN a header intake shows or #position (#3)
  decode                                            failed collections by bank reason code
  mandates [--on YYYY-MM-DD]                        36-month rule and other mandate checks
  match                                             bank payments against invoices
  terms                                             agreed terms against days to pay, payer profiles
  steps                                             manual steps per finding, counted from the files
  month [--mail-lang en|nl|fr] [--since-days 90]    this month's work, prepared: month.json (codes) in the
                                                    workspace, the work pack with names next to the raw files
  golive [--tool NAME]                              facts for the go-live plan
  report [--findings FILE]                          final report with names, written next to the raw files
  status                                            what the workspace holds

Add --json to any command for machine-readable output, and --lang en|nl|fr (before or after the command) for
dates, amounts and Twikey lines in that language. Exit codes: 0 ok, 1 error, 2 intake needs input.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xray import VERSION, checks, claims, csvparse, intake  # noqa: E402
from xray import month as monthmod  # noqa: E402
from xray import report as reportmod  # noqa: E402
from xray import common  # noqa: E402
from xray.cli_text import INTAKE_PHRASES, NOUNS, SHAPES, TEXT  # noqa: E402
from xray.common import (DEFAULT_CONFIG, DEFAULT_HOME, DEMO_DIR, KEY_FILE, REPORT_PREFIX, XrayError,  # noqa: E402
                         inside, long_date, month_year, parse_iso, read_json, real,
                         registry_path, state_dir, write_json)

# The language of the command being run: every text line, amount and decimal follows it (€1.234,50 in nl and fr).
CURRENT = {"lang": "en"}


def money(amount):
    return common.money(amount, lang=CURRENT["lang"])


def dec(x, places=1):
    return common.dec(x, places, CURRENT["lang"])


def pct(x):
    return common.pct(x, CURRENT["lang"])


def T(key):
    """A text line in the language of the command being run."""
    return TEXT[CURRENT["lang"]][key]


def num(n):
    return common.num(n, CURRENT["lang"])


def pl(n, noun):
    """'no invoices', 'one invoice', '12 invoices' in the language of the command."""
    one, many = NOUNS[CURRENT["lang"]][noun]
    return common.plural(n, one, many, CURRENT["lang"])


def count(n):
    """A count on its own: 'none' / 'geen' / '0' for zero."""
    return num(n) if n else T("none")


def dlong(d):
    return long_date(d, CURRENT["lang"])


def tr(s, table=INTAKE_PHRASES):
    """What a file reader said (in English), in the language of the command."""
    for pattern, repl in table.get(CURRENT["lang"], []):
        s = re.sub(pattern, repl, s)
    return s

DEMO_AS_OF = "2026-10-31"


# --------------------------------------------------------------------------- workspace

def home_dir(args):
    return os.path.abspath(args.home or os.environ.get("TWIKEY_XRAY_HOME") or DEFAULT_HOME)


def load_config(home, required=True):
    path = os.path.join(home, "config.json")
    if not os.path.exists(path):
        if required:
            raise XrayError("No workspace at %s yet. Run `init --raw <folder>` or `demo` first." % home)
        return dict(DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    try:
        data = read_json(path, {})
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, OSError):
        raise XrayError("The workspace file %s cannot be read (it is not valid JSON). Delete it and run `init` or "
                        "`demo` again." % path)
    cfg.update(data)
    return cfg


WINDOWS = "macOS and Linux. Windows is not supported yet."


def check_start(raw=None):
    """Refuse to start on Windows, or with Claude started in the home folder or a folder above the exports."""
    if os.name == "nt" or sys.platform.startswith(("win", "cygwin", "msys")):
        raise XrayError(WINDOWS)
    cwd, home = real(os.getcwd()), real("~")
    above = raw is not None and cwd != raw and inside(raw, cwd)
    if cwd in (home, os.sep) or above:
        where = ("your home folder" if cwd == home else "the disk root" if cwd == os.sep
                 else "a folder that holds your exports")
        raise XrayError("Claude was started in %s. Start Claude in a new, empty folder (for example ~/payment-xray) "
                        "and set up the X-ray there." % where)


def save_config(home, cfg):
    write_json(os.path.join(home, "config.json"), cfg)


def as_of(cfg, args):
    s = getattr(args, "as_of", None) or cfg.get("as_of")
    if s:
        d = parse_iso(s)
        if not d:
            raise XrayError("As-of date must look like 2026-10-31.")
        return d
    return common.today()


def register_raw(raw):
    """Tell the guard about the raw folder and the X-ray folder (the folder Claude works in). In the X-ray folder
    the guard lets only X-ray's own commands run in the shell."""
    path = registry_path()
    data = read_json(path, {"raw_dirs": []}) or {"raw_dirs": []}
    changed = False
    for key, value in (("raw_dirs", raw), ("work_dirs", real(os.getcwd()))):
        data.setdefault(key, [])
        if value not in data[key]:
            data[key].append(value)
            changed = True
    if changed:
        write_json(path, data)


def check_raw_location(raw, home, allow_inside_cwd=False):
    cwd = real(os.getcwd())
    if raw in ("/", real("~")):
        raise XrayError("Pick a dedicated folder for the exports, not your home folder or the disk root.")
    if inside(cwd, raw):
        raise XrayError("The raw folder contains the folder Claude works in. Pick a folder next to it instead.")
    if inside(raw, cwd) and not allow_inside_cwd:
        raise XrayError("The raw folder is inside the folder Claude works in. Move it outside, for example to "
                        "~/Documents/payment-exports, so Claude's tools cannot reach it by accident.")
    if inside(home, raw):
        raise XrayError("The workspace cannot be inside the raw folder.")
    return inside(raw, cwd)


LEDGER_FILES = ("store.json", "mandates.json", "collections.json", "bank.json", "intake.json", "findings.md",
                "go-live-plan.md", "month.json")


def clear_ledger(home):
    """Remove the coded ledger and findings of a previous raw folder, so two folders never mix."""
    removed = 0
    for name in LEDGER_FILES:
        p = os.path.join(home, name)
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    return removed


def load_ledger(home):
    store = read_json(os.path.join(home, "store.json"))
    if store is None:
        raise XrayError("No ledger yet. Run `intake` (or `demo`) first.")
    return (store, read_json(os.path.join(home, "mandates.json"), []),
            read_json(os.path.join(home, "collections.json"), []), read_json(os.path.join(home, "bank.json"), []))


def ledger_sources(home, store, mandates, collections, bank):
    """Which exports the ledger was built from (intake.json), so a check whose export is missing says so."""
    info = read_json(os.path.join(home, "intake.json")) or {}
    return checks.sources(info.get("files"), store, mandates, collections, bank)


def out(args, data, text_fn):
    if args.json:
        print(json.dumps(data, indent=1, ensure_ascii=False, default=str))
    else:
        text_fn(data)


def twikey_lines(lines):
    for t in lines if isinstance(lines, list) else [lines]:
        print(claims.render(t))


def dash(v):
    return "-" if v is None else v


def lang_of(cfg, args=None):
    lang = getattr(args, "lang", None) or cfg.get("lang") or "en"
    lang = lang if lang in ("en", "nl", "fr") else "en"
    CURRENT["lang"] = lang
    return lang


def codes(items, key="customer", limit=12):
    vals = [i[key] if isinstance(i, dict) else i for i in items]
    vals = [v for v in vals if v]
    more = len(vals) - limit
    return ", ".join(vals[:limit]) + (T("and_more") % num(more) if more > 0 else "")


# --------------------------------------------------------------------------- init, demo, intake

def cmd_init(args):
    home = home_dir(args)
    raw = real(args.raw)
    check_start(raw)
    if not os.path.isdir(raw):
        raise XrayError("Folder not found. Create it, put your exports in it, and run init again.")
    check_raw_location(raw, home)
    cfg = load_config(home, required=False)
    switching = bool(cfg.get("raw_dir")) and real(cfg["raw_dir"]) != raw
    if switching and not args.force:
        raise XrayError("This workspace already uses another raw folder. Add --force to switch.")
    if switching:
        clear_ledger(home)
        cfg.update({"column_maps": {}, "skip_files": []})
    cfg.update({"version": VERSION, "raw_dir": raw, "demo": False, "as_of": args.as_of or None,
                "lang": args.lang or cfg.get("lang") or "en"})
    save_config(home, cfg)
    register_raw(raw)
    lang_of(cfg, args)
    data = {"version": VERSION, "workspace": home, "raw_dir": raw, "registry": registry_path()}
    out(args, data, lambda d: print(T("init").format(workspace=d["workspace"], raw=d["raw_dir"])))


def print_intake(res):
    if res["status"] == "blocked":
        print(T("blocked"))
        for b in res["blocked"]:
            n = b["file"].split()[-1]
            print("\n  %s%s %s" % (tr(b["description"]), claims.COLON[CURRENT["lang"]], tr(b["reason"])))
            if b.get("columns"):
                print(T("no_header") if not b.get("has_header", True) else T("columns"))
                for c in b["columns"]:
                    print("      #%d  %s  (%s)" % (c["position"], c["header"] or T("header_not_shown"),
                                                   tr(c["values"], SHAPES)))
                kind = b.get("kind")
                fields = csvparse.ALLOWED.get(kind) if kind else sorted(set(csvparse.MAP_TARGETS) - {"ignore"})
                print(T("map_hint").format(n=n))
                print(T("fields").format(kind=T("fields_for").format(kind=kind.replace("_", " ")) if kind else "",
                                         fields=", ".join(fields)))
                if not kind:
                    print(T("kind_hint").format(n=n, kinds="|".join(csvparse.KINDS)))
            print(T("skip_hint").format(n=n))
        return
    rep = res["report"]
    t = rep["totals"]
    print(T("intake").format(files=pl(len(rep["files"]), "file")))
    for f in rep["files"]:
        print(T("kept_one" if f["kept"] == 1 else "kept").format(desc=tr(f["description"]), n=pl(f["kept"], "record")))
        if f.get("columns_dropped"):
            print(T("dropped").format(cols=", ".join(f["columns_dropped"])))
        if f.get("read_not_stored"):
            print(T("not_stored").format(cols=", ".join(f["read_not_stored"])))
        for why, n in sorted((f.get("skipped") or {}).items()):
            if why == csvparse.STATUS_UNKNOWN:
                print(T("status_unknown").format(n=pl(n, "invoice")))
            else:
                print(T("skipped").format(n=num(n), why=tr(why)))
    skipped_files = [tr(f["description"]) for f in res["files"] if f["status"] == "skipped"]
    if skipped_files:
        print(T("left_out").format(files=", ".join(skipped_files)))
    print(T("ledger").format(invoices=pl(t["invoices"], "invoice"), customers=pl(t["customers"], "customer"),
                             others=pl(t["other_parties"], "other_party"), codes=pl(t["parties"], "code"),
                             rows=pl(t["mandate_rows"], "mandate_row"), refs=pl(t["mandate_codes"], "reference")))
    for line in ledger_periods(t, rep.get("periods") or {}):
        print("  " + line)
    print(T("not_in_ledger").format(out=pl(t["debit_lines_skipped"], "payment"),
                                    own=pl(t["own_transfers_skipped"], "transfer"),
                                    dups=pl(t["duplicates_removed"], "copy")))
    if t["invalid_structured_communications"]:
        print(T("bad_ogm").format(n=num(t["invalid_structured_communications"])))
    if t["other_references"]:
        print(T("other_refs").format(n=num(t["other_references"])))
    if t["failed_amount_unknown"]:
        print(T("unknown_amount").format(n=num(t["failed_amount_unknown"])))
    for a in rep["assumptions"]:
        print(T("assumption").format(a=tr(a)))
    print(T("coded"))


def ledger_periods(t, periods):
    """One line per source, each with its own period, so counts from different periods never share a line."""
    def span(p):
        return T("span").format(start=dlong(p["from"]), end=dlong(p["to"])) if p else ""

    return [T("bank_in").format(n=count(t["bank_credit_lines"]), span=span(periods.get("bank"))),
            T("coll_in").format(n=count(t["collections_collected"]), span=span(periods.get("collections"))),
            T("failed_in").format(n=count(t["failed_collections"]), span=span(periods.get("failed_collections")))]


def intake_data(res):
    if res["status"] == "blocked":
        return {"version": VERSION, "status": "blocked", "files": res["files"],
                "blocked": [{k: b.get(k) for k in ("file", "description", "status", "reason", "columns", "has_header",
                                                   "kind")} for b in res["blocked"]],
                "map_syntax": "intake --map \"<file number>:#<column position>=<field>\"",
                "fields": csvparse.ALLOWED, "kinds": csvparse.KINDS}
    return {"version": VERSION, "status": "ok", "files": res["report"]["files"],
            "skipped_files": [f["file"] for f in res["files"] if f["status"] == "skipped"],
            "totals": res["report"]["totals"], "periods": res["report"]["periods"],
            "assumptions": res["report"]["assumptions"]}


def run_intake(args, home, cfg):
    res = intake.run(cfg["raw_dir"], cfg, cfg.get("column_maps") or {}, cfg.get("skip_files") or [])
    res["lang"] = lang_of(cfg, args)
    if res["status"] == "ok":
        intake.write(home, cfg["raw_dir"], res)
    out(args, intake_data(res), lambda d: print_intake(res))
    return 0 if res["status"] == "ok" else 2


def parse_maps(entries, raw_dir):
    """--map "2:#3=invoice_number": file number (or file name), column position or header, field."""
    maps = {}
    for e in entries or []:
        if ":" not in e or "=" not in e.split(":", 1)[1]:
            raise XrayError("Use --map \"<file number>:#<column position>=<field>\", for example --map "
                            "\"2:#3=invoice_number\".")
        fref, rest = e.split(":", 1)
        col, field = rest.rsplit("=", 1)
        col, field = col.strip(), field.strip()
        if col == "@kind":
            if field not in csvparse.KINDS:
                raise XrayError("Kind must be one of: %s" % ", ".join(csvparse.KINDS))
        elif field not in csvparse.MAP_TARGETS:
            raise XrayError("Unknown field. Fields: %s" % ", ".join(csvparse.MAP_TARGETS))
        maps.setdefault(intake.resolve_file(raw_dir, fref), {})[col] = field
    return maps


def cmd_intake(args):
    home = home_dir(args)
    cfg = load_config(home)
    lang_of(cfg, args)
    if not cfg.get("raw_dir"):
        raise XrayError("No raw folder set. Run `init --raw <folder>` first.")
    maps = cfg.get("column_maps") or {}
    for fid, m in parse_maps(args.map, cfg["raw_dir"]).items():
        maps.setdefault(fid, {}).update(m)
    cfg["column_maps"] = maps
    skips = {intake.resolve_file(cfg["raw_dir"], s) for s in args.skip or []}
    cfg["skip_files"] = sorted(set(cfg.get("skip_files") or []) | skips)
    save_config(home, cfg)
    return run_intake(args, home, cfg)


def cmd_demo(args):
    home = home_dir(args)
    raw = real(args.raw or os.path.join(state_dir(), "demo-raw"))
    check_start(raw)
    os.makedirs(raw, exist_ok=True)
    demo_files = sorted(f for f in os.listdir(DEMO_DIR) if f.endswith((".csv", ".xml")))
    foreign = [f for f in os.listdir(raw) if not f.startswith(".") and f not in demo_files and not intake.is_ours(f)]
    if foreign:
        raise XrayError("That folder already holds other files. Pick an empty folder for the demo.")
    check_raw_location(raw, home, allow_inside_cwd=True)
    for f in demo_files:
        shutil.copyfile(os.path.join(DEMO_DIR, f), os.path.join(raw, f))
    cfg = load_config(home, required=False)
    if cfg.get("raw_dir") and real(cfg["raw_dir"]) != raw:
        clear_ledger(home)
    cfg.update({"version": VERSION, "raw_dir": raw, "demo": True, "as_of": DEMO_AS_OF,
                "lang": args.lang or cfg.get("lang") or "en", "column_maps": {}, "skip_files": []})
    save_config(home, cfg)
    register_raw(raw)
    if not args.json:
        lang = lang_of(cfg, args)
        print(T("demo").format(start=month_year("2025-11-01", lang), end=month_year("2026-10-01", lang), raw=raw,
                               as_of=long_date(DEMO_AS_OF, lang)))
    return run_intake(args, home, cfg)


# --------------------------------------------------------------------------- checks

def cmd_decode(args):
    home = home_dir(args)
    cfg = load_config(home)
    store, mandates, collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = checks.decode(collections, lang, ledger_sources(home, store, mandates, collections, bank)["failures"])

    def amount(v):
        s = money(v["amount"])
        if v.get("amount_unknown_count"):
            s += T("plus_unknown").format(n=num(v["amount_unknown_count"]))
        return s

    def txt(d):
        if not d["checked"]:
            print(d["not_checked"])
            twikey_lines(d["twikey"])
            return
        p = d["period"]
        print(T("dec_total").format(n=num(d["total"]["count"]), amount=amount(d["total"]), start=dlong(p["from"]),
                                    end=dlong(p["to"]), months=pl(p["months"], "month")))
        print("\n" + T("by_code"))
        cat_names = T("cat")
        colon = claims.COLON[lang]  # French: a space before the colon
        for r in d["by_code"]:
            cats = ", ".join("%s%s %s" % (cat_names.get(k, k), colon, num(v))
                             for k, v in sorted(r["categories"].items()))
            meaning = r["meaning"] or T("no_code")
            if r.get("meaning_source"):
                meaning = T("epc").format(meaning=meaning)
            print("  %-5s %3d  %12s  %s  %s%s" % (r["label"] or "?", r["count"], amount(r), cats, meaning,
                                                 "  " + r["page"] if r["page"] else ""))
        print("\n" + T("points_to"))
        width = max([13] + [len(cat_names.get(cat, cat)) for cat in d["by_category"]])
        for cat, v in d["by_category"].items():
            print("  %-*s %3d  %12s  %s" % (width, cat_names.get(cat, cat), v["count"], amount(v), v["meaning"]))
        if d["days_of_month"]:
            per = d["days_of_month_period"]
            print("\n" + T("rate_head").format(start=month_year(per["from"] + "-01", lang),
                                              end=month_year(per["to"] + "-01", lang)))
            for day, v in d["days_of_month"].items():
                print(T("rate_line").format(day=day, rate=pct(v["rate_pct"]), failed=count(v["failed"]),
                                            presented=num(v["presented"]), months=pl(v["months"], "month"),
                                            few="" if v["qualifies"] else T("few")))
            o = d["days_of_month_overall"]
            print(T("rate_all").format(rate=pct(o["rate_pct"]), failed=count(o["failed"]), presented=num(o["presented"])))
        if d["days_of_month_return_booked"]:
            print(T("booked").format(list=", ".join("%s%s %s" % (k, colon, num(v))
                                                    for k, v in d["days_of_month_return_booked"].items())))
        if d["repeat_customers"]:
            print(T("repeat").format(list=", ".join("%s (%s)" % (c, num(n)) for c, n in d["repeat_customers"].items())))
        if d["unknown_codes"]:
            by = {r["code"]: r for r in d["by_code"]}
            print(T("not_on_page").format(list=", ".join(
                T("epc_short").format(code=c, meaning=by[c]["meaning"]) if by.get(c, {}).get("meaning_source") else c
                for c in d["unknown_codes"])))
        twikey_lines(d["twikey"])
    out(args, data, txt)


ISSUES_SHOWN = ("expired", "expiring_90_days", "unused_since_signing", "last_collection_unknown", "missing_reference",
                "missing_signature_date", "signature_missing", "duplicate_reference", "possible_duplicate",
                "iban_changed", "b2b_not_confirmed")


def cmd_mandates(args):
    home = home_dir(args)
    cfg = load_config(home)
    store, mandates, collections, bank = load_ledger(home)
    on = parse_iso(args.on) if args.on else as_of(cfg, args)
    if args.on and not on:
        raise XrayError("--on must look like 2026-10-31.")
    lang = lang_of(cfg, args)
    data = checks.mandate_health(mandates, collections, on, lang,
                                 ledger_sources(home, store, mandates, collections, bank)["mandates"])

    def item_text(i):
        if "customers" in i:
            return "%s (%s)" % (i["mandate"], (" %s " % T("and")).join(i["customers"]))
        if "mandates" in i:
            return "%s (%s)" % (i["customer"], (" %s " % T("and")).join(i["mandates"]))
        extra = i.get("expired_on") or i.get("expires_on") or i.get("signed_on") or i.get("return_booked_on")
        s = "%s (%s%s)" % (i["mandate"], i.get("customer") or "?", " " + dlong(extra) if extra else "")
        if i.get("presented_after_expiry"):
            n = i["presented_after_expiry"]
            one, many = NOUNS[lang]["time"]
            # a sentence: French spells the number too ("une fois", feminine)
            s += T("after_expiry").format(n=common.num_fr(n, fem=True) if lang == "fr" else num(n),
                                          times=one if n == 1 else many)
        return s

    def txt(d):
        if not d["checked"]:
            print(d["not_checked"])
            twikey_lines(d["twikey"])
            return
        print(T("mand_head").format(date=dlong(d["on"]), rows=pl(d["rows"], "row"), core=num(d["core"]),
                                    b2b=num(d["b2b"]),
                                    unknown=T("scheme_unknown").format(n=num(d["scheme_unknown"]))
                                    if d["scheme_unknown"] else "", refs=pl(d["codes"], "reference")))
        print(T("rule").format(rule=d["rule"]))
        labels = T("issues")
        for k in ISSUES_SHOWN:
            items = d["issues"][k]
            line = "  %s%s %s" % (labels[k], claims.COLON[lang], count(len(items)))
            if items:
                line += "  " + " | ".join(item_text(i) for i in items[:10])
            if d["failed_amount_on"].get(k):
                line += T("failed_on").format(amount=money(d["failed_amount_on"][k]))
            print(line)
        print(T("to_renew").format(n=count(d["to_renew"]), m=count(d["counts"]["unused_since_signing"])))
        twikey_lines(d["twikey"])
    out(args, data, txt)


MATCH_ROWS = ("matched", "paid_but_open", "partial", "bundled", "double", "overpaid", "unmatched", "other_receipts")


def cmd_match(args):
    home = home_dir(args)
    cfg = load_config(home)
    lang = lang_of(cfg, args)
    store, mandates, collections, bank = load_ledger(home)
    data = checks.match(store, bank, lang, ledger_sources(home, store, mandates, collections, bank)["bank"])

    def txt(d):
        if not d["checked"]:
            print(d["not_checked"])
            twikey_lines(d["twikey"])
            return
        p = d["period"]
        print(T("match_head").format(n=num(d["credit_lines"]["count"]), amount=money(d["credit_lines"]["amount"]),
                                     start=dlong(p["from"]), end=dlong(p["to"])))
        labels = T("match_rows")
        for k in MATCH_ROWS:
            c = d[k]
            line = "  %s%s %s, %s" % (labels[k], claims.COLON[lang], count(c["count"]), money(c["amount"]))
            if k == "partial" and c["count"]:
                line += T("still_open").format(amount=money(c["still_open"]))
            if k == "bundled" and c["count"]:
                line += " (%s%s)" % (pl(c["invoices"], "invoice"),
                                     T("netted").format(n=pl(c["credit_notes"], "credit_note"))
                                     if c.get("credit_notes") else "")
            if k == "unmatched" and c["count"]:
                m = c["mentions_open_invoice"]
                line += T("unmatched_detail").format(known=count(c["known_customer"]), unknown=count(c["unknown_party"]),
                                                     m=count(m), verb=T("names_one") if m == 1 else T("names_many"))
            if k != "matched" and c["customers"]:
                line += "  %s" % codes(c["customers"])
            if k == "paid_but_open" and c["invoices"]:
                line += T("invoices").format(list=codes(c["invoices"]))
            print(line)
        print(T("method").format(method=d["method"]))
        twikey_lines(d["twikey"])
    out(args, data, txt)


def cmd_terms(args):
    home = home_dir(args)
    cfg = load_config(home)
    lang = lang_of(cfg, args)
    store, _, collections, _ = load_ledger(home)
    data = checks.terms(store, cfg, as_of(cfg, args), collections, lang)

    def txt(d):
        print(T("terms_head").format(date=dlong(d["as_of"])))
        labels = T("profiles")
        for k in checks.PROFILES:
            p = d["profiles"][k]
            print(T("profile_line").format(label=labels[k], rule=d["rules"][k], customers=pl(p["count"], "customer"),
                                           open=money(p["open_amount"]), overdue=money(p["overdue_amount"]),
                                           codes=codes(p["customers"])))
        print("\n" + T("not_clockwork"))
        print(T("table"))
        for r in d["customers"]:
            if r["profile"] == "clockwork":
                continue
            print("  %-6s %5s  %11s  %9s  %13s  %-12s  %s" % (
                r["customer"], dash(r["agreed_terms_days"]), dec(r["avg_days_to_pay"]), dec(r["avg_days_late"]),
                dec(r["late_trend_days_per_invoice"], 2), money(r["open_amount"]), r["max_days_overdue"]))
        print("\n" + T("open_line").format(open=money(d["open_receivables"]), overdue=money(d["overdue"])))
        print(T("aging").format(list=", ".join("%s %s" % (T("not_due") if k == "not_due" else k, money(v))
                                               for k, v in d["aging"].items())))
        if d["dso_90d"] is not None:
            terms_txt = T("dso_terms").format(terms=dec(d["terms_days_90d"])) if d["terms_days_90d"] is not None else ""
            print(T("dso").format(dso=dec(d["dso_90d"]), terms=terms_txt))
        twikey_lines(d["twikey"])
    out(args, data, txt)


def cmd_steps(args):
    home = home_dir(args)
    cfg = load_config(home)
    store, mandates, collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = checks.steps(store, mandates, collections, bank, as_of(cfg, args), lang,
                        ledger_sources(home, store, mandates, collections, bank))
    t = checks.manual_steps(lang)["text"]

    def txt(d):
        print(t["title"].format(date=dlong(d["as_of"])))
        for i in d["items"]:
            if not i["count"] or not i["checked"]:
                continue
            line = t["line"].format(count=i["count"], label=i["label_one"] if i["count"] == 1 else i["label"],
                                    checklist=" · ".join(i["checklist"]), steps_total=i["steps_total"])
            if i["per_month"] is not None:
                line += t["per_month"].format(per_month=dec(i["per_month"]), months=i["months"],
                                              months_word=t["month_one"] if i["months"] == 1 else t["month_many"])
            print(line)
        print(t["total"].format(items=d["total_items"], steps=d["total_steps"]))
        if d["per_month_total"] is not None:
            print(t["per_month_total"].format(items=dec(d["per_month_total"]), steps=dec(d["per_month_steps_total"])))
        zero = [i["label"] for i in d["items"] if not i["count"] and i["checked"]]
        if zero:
            print(t["none"].format(labels=monthmod.join(zero, t["and"])))
        missing = {}
        for i in d["items"]:
            if not i["checked"]:
                missing.setdefault(i["not_checked"], []).append(i["label"])
        for line, labels in missing.items():
            print(t["not_checked"].format(line=line, labels=monthmod.join(labels, t["and"])))
        print(d["basis"])
        twikey_lines(d["twikey"])
    out(args, data, txt)


def cmd_month(args):
    home = home_dir(args)
    cfg = load_config(home)
    raw = cfg.get("raw_dir")
    if not raw or not os.path.isdir(raw):
        raise XrayError("Raw folder not found. Run `init --raw <folder>` first.")
    if not any(f.lower() == KEY_FILE.lower() for f in os.listdir(raw)):
        raise XrayError("No key file next to the exports. Run `intake` first.")
    if not 1 <= args.since_days <= 3660:
        raise XrayError("--since-days must be a number of days from 1 to 3660, for example 90.")
    store, mandates, collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = monthmod.prepare(store, mandates, collections, bank, as_of(cfg, args), args.since_days, lang,
                            args.mail_lang or lang, source=ledger_sources(home, store, mandates, collections, bank))
    # The work pack holds names: it goes next to the raw exports, and only its path is printed.
    path = monthmod.write_pack(raw, data, intake.load_key(raw))
    data["paths"] = {"month_report": path}
    write_json(os.path.join(home, "month.json"), data)
    out(args, data, lambda d: print(d["paths"]["month_report"]))


def cmd_golive(args):
    home = home_dir(args)
    cfg = load_config(home)
    store, mandates, collections, _ = load_ledger(home)
    on = as_of(cfg, args)
    lang = lang_of(cfg, args)
    mand = checks.mandate_health(mandates, collections, on, lang)
    term = checks.terms(store, cfg, on, collections, lang)
    data = checks.golive(store, collections, mand, term, args.tool, lang)

    def gl(n, word=num):
        """A count in the go-live facts. French spells one to ten too: mandates and customers are masculine."""
        return common.num_fr(n) if lang == "fr" else word(n)

    def s(n):
        """French agreement of the past participle after a count: 'un jamais utilisé', 'deux jamais utilisés'."""
        return "s" if n > 1 else ""

    def txt(d):
        print(T("golive_head"))
        print(T("gl_customers").format(n=num(d["customers"]), dd=num(d["direct_debit_customers"])))
        print(T("gl_invoices").format(n=dec(d["invoices_per_month"])))
        print(T("gl_mandates").format(core=gl(d["mandates_core"]), b2b=gl(d["mandates_b2b"]),
                                      renew=gl(d["mandates_to_renew"], count),
                                      never=gl(d["mandates_never_used"], count), never_s=s(d["mandates_never_used"]),
                                      nc=gl(d["b2b_not_confirmed"], count), nc_s=s(d["b2b_not_confirmed"])))
        print(T("gl_failed").format(n=dec(d["failed_per_month"])))
        print(T("gl_open").format(open=money(d["open_receivables"]), overdue=money(d["overdue"])))
        labels = T("profiles")
        print(T("gl_profiles").format(list=", ".join("%s %s" % (labels[k].lower(), gl(v, count))
                                                     for k, v in d["profiles"].items())))
        if "tool" in d:
            t = d["tool"]
            if t["listed_as"]:
                print(T("gl_tool_yes").format(tool=repr(t["asked"]), names=", ".join(t["listed_as"]),
                                              page=t["partners_page"]))
            else:
                print(T("gl_tool_no").format(tool=repr(t["asked"])))
        print(T("gl_questions").format(list=", ".join(d["questions"])))
        print(T("gl_existing").format(text=d["existing_mandates"]))
        print(T("gl_lines"))
        twikey_lines(d["twikey"])
        print(T("gl_pricing").format(page=d["pricing_page"]))
        print(T("gl_cta").format(text=d["demo"]["text"]))
    out(args, data, txt)


# --------------------------------------------------------------------------- report and status

def cmd_report(args):
    home = home_dir(args)
    cfg = load_config(home)
    raw = cfg.get("raw_dir")
    if not raw or not os.path.isdir(raw):
        raise XrayError("Raw folder not found. Run `init --raw <folder>` first.")
    findings = os.path.abspath(args.findings) if args.findings else os.path.join(home, "findings.md")
    if inside(findings, raw):
        raise XrayError("findings.md belongs in the workspace, not in the raw folder.")
    if not any(f.lower() == KEY_FILE.lower() for f in os.listdir(raw)):
        raise XrayError("No key file next to the exports. Run `intake` first.")
    key = intake.load_key(raw)
    path = reportmod.write_report(raw, findings, key, [os.path.join(home, "go-live-plan.md")], lang=lang_of(cfg, args))
    out(args, {"version": VERSION, "report": path}, lambda d: print(d["report"]))


def cmd_status(args):
    home = home_dir(args)
    cfg = load_config(home, required=False)
    exists = os.path.exists(os.path.join(home, "config.json"))
    raw = cfg.get("raw_dir")
    info = read_json(os.path.join(home, "intake.json"))
    reports = sorted(f for f in os.listdir(raw) if f.lower().startswith(REPORT_PREFIX)) \
        if raw and os.path.isdir(raw) else []
    data = {"version": VERSION, "workspace": home, "workspace_exists": exists, "raw_dir": raw,
            "raw_dir_exists": bool(raw and os.path.isdir(raw)), "demo": cfg.get("demo"), "as_of": cfg.get("as_of"),
            "language": lang_of(cfg, args), "intake": info and info.get("totals"), "intake_at": info and info.get("at"),
            "periods": (info or {}).get("periods") or {},
            "findings": os.path.exists(os.path.join(home, "findings.md")),
            "go_live_plan": os.path.exists(os.path.join(home, "go-live-plan.md")),
            "reports": len(reports), "latest_report": reports[-1] if reports else None,
            "registry": registry_path(), "start_problem": None}
    try:
        check_start()
    except XrayError as e:
        data["start_problem"] = str(e)

    def txt(d):
        print(T("st_title").format(version=d["version"]))
        if d["start_problem"]:
            print(T("st_stop").format(problem=d["start_problem"]))
        print(T("st_ws").format(ws=d["workspace"], extra="" if d["workspace_exists"] else T("st_not_set_up")))
        print(T("st_raw").format(raw=d["raw_dir"] or T("st_not_set"), extra=T("st_demo") if d["demo"] else ""))
        print(T("st_as_of").format(date=dlong(d["as_of"]) if d["as_of"] else T("st_today")))
        if d["intake"]:
            t = d["intake"]
            print(T("st_ledger").format(date=dlong(d["intake_at"][:10]), invoices=pl(t["invoices"], "invoice"),
                                        customers=pl(t.get("customers", t["parties"]), "customer"),
                                        rows=pl(t["mandate_rows"], "mandate_row")))
            for line in ledger_periods(t, d["periods"]):
                print("  " + line)
        else:
            print(T("st_no_ledger"))
        print(T("st_files").format(findings=T("yes") if d["findings"] else T("no"),
                                   plan=T("yes") if d["go_live_plan"] else T("no")))
        print(T("st_reports").format(n=d["reports"], latest=T("st_latest").format(name=d["latest_report"])
                                     if d["latest_report"] else ""))
    out(args, data, txt)


# --------------------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(prog="twikey_xray", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home", help="workspace folder")
    p.add_argument("--as-of", dest="as_of", help="date to measure against (default: config, else today)")
    p.add_argument("--lang", choices=LANGS, help="language of dates, amounts and Twikey lines")
    p.add_argument("--version", action="version", version="twikey-payment-xray " + VERSION)
    sp = p.add_subparsers(dest="cmd")
    sp.required = True

    def sub(name, help_text, f):
        s = sp.add_parser(name, help=help_text)
        # --lang after the command too. SUPPRESS keeps a --lang given before the command.
        s.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS)
        s.set_defaults(f=f)
        return s

    s = sub("init", "set the raw export folder", cmd_init)
    s.add_argument("--raw", required=True)
    s.add_argument("--force", action="store_true")
    s = sub("demo", "load the fictional demo company", cmd_demo)
    s.add_argument("--raw")
    s = sub("intake", "read the raw exports into the coded ledger", cmd_intake)
    # extend: "--map A --map B" keeps both, like "--map A B"
    s.add_argument("--map", nargs="+", action="extend", metavar="FILE:COLUMN=FIELD")
    s.add_argument("--skip", nargs="+", action="extend", metavar="FILE")
    sub("decode", "failed collections by reason code", cmd_decode)
    s = sub("mandates", "mandate health", cmd_mandates)
    s.add_argument("--on")
    sub("match", "bank payments against invoices", cmd_match)
    sub("terms", "terms against reality, payer profiles", cmd_terms)
    sub("steps", "manual steps per finding, counted from the files", cmd_steps)
    s = sub("month", "this month's work, prepared (drafts only, nothing is sent)", cmd_month)
    s.add_argument("--mail-lang", dest="mail_lang", choices=LANGS)
    s.add_argument("--since-days", dest="since_days", type=int, default=monthmod.DEFAULT_SINCE_DAYS)
    s = sub("golive", "facts for the go-live plan", cmd_golive)
    s.add_argument("--tool")
    s = sub("report", "write the final report with names next to the raw files", cmd_report)
    s.add_argument("--findings")
    sub("status", "what the workspace holds", cmd_status)
    return p


LANGS = ["en", "nl", "fr"]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    want_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    args = build_parser().parse_args(argv)
    args.json = want_json
    try:
        return args.f(args) or 0
    except XrayError as e:
        msg = str(e)
    except Exception as e:  # noqa: BLE001
        # Never the message or a traceback: they can carry a file name or a cell value from an export.
        msg = ("Unexpected error (%s). Nothing about your files is shown. Run the command again, or tell Twikey "
               "the error type above." % type(e).__name__)
    if want_json:
        print(json.dumps({"version": VERSION, "error": msg}))
    else:
        print("ERROR: %s" % msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
