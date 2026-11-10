#!/usr/bin/env python3
"""
twikey_xray.py - Twikey Payment X-ray: where a company's direct debits fail and the manual work that follows, read
from its own camt.053 bank statements.

Standard library only (Python 3.8+). No network calls. Read-only: it never sends, collects or changes anything.
Only `intake` opens the raw statements, and it writes coded data to the workspace and the key (codes back to names)
next to the raw files. `report` puts the names back into the final report on this computer and prints only its
path, and so does `month` for its work pack (customer mail drafts: drafts only, nothing is sent, no bank file is
written). Every other command prints counts, amounts, dates and codes.

Workspace folder (config.json + the coded ledger) is resolved from:
  --home PATH  >  $TWIKEY_XRAY_HOME  >  ./twikey-xray-workspace

  init --raw FOLDER [--lang en|nl|fr] [--force]    set the raw folder with the statements (outside Claude's folder)
  demo [--raw FOLDER]                               load the fictional demo company and run intake
  intake                                            read the camt.053 statements into the coded ledger
  decode                                            failed collections by bank reason code
  payments                                          incoming payments and the ones to book by hand
  steps                                             manual steps per finding, counted from the statements
  month [--mail-lang en|nl|fr] [--since-days 90]    this month's work, prepared: month.json (codes) in the
                                                    workspace, the work pack with names next to the raw files
  golive [--tool NAME]                              facts for the go-live plan
  report [--findings FILE]                          final report with names, written next to the raw files
  status                                            what the workspace holds

Add --json to any command for machine-readable output, and --lang en|nl|fr (before or after the command) for
dates, amounts and Twikey lines in that language. Exit codes: 0 ok, 1 error.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xray import VERSION, checks, claims, intake  # noqa: E402
from xray import month as monthmod  # noqa: E402
from xray import report as reportmod  # noqa: E402
from xray import common  # noqa: E402
from xray.cli_text import INTAKE_PHRASES, NOUNS, TEXT  # noqa: E402
from xray.common import (DEFAULT_CONFIG, DEFAULT_HOME, DEMO_DIR, KEY_FILE, REPORT_PREFIX, XrayError,  # noqa: E402
                         inside, long_date, month_year, parse_iso, read_json, real, registry_path, state_dir,
                         write_json)

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
    """'no payments', 'one payment', '12 payments' in the language of the command."""
    one, many = NOUNS[CURRENT["lang"]][noun]
    return common.plural(n, one, many, CURRENT["lang"])


def count(n):
    """A count on its own: 'none' / 'geen' / '0' for zero."""
    return num(n) if n else T("none")


def dlong(d):
    return long_date(d, CURRENT["lang"])


def tr(s):
    """What the statement reader said (in English), in the language of the command."""
    for pattern, repl in INTAKE_PHRASES.get(CURRENT["lang"], []):
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


WINDOWS = "X-ray runs on macOS and Linux. Windows is not supported."


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


# The files the current version writes to the workspace. Any other .json there is from an earlier version.
LEDGER_JSON = ("collections.json", "bank.json", "intake.json", "month.json")


def clear_ledger(home):
    """Remove the coded ledger and findings of a previous raw folder, so two folders never mix. Every .json
    file except config.json goes, so files an earlier version wrote go too."""
    removed = 0
    if not os.path.isdir(home):
        return removed
    for name in sorted(os.listdir(home)):
        if (name.endswith(".json") and name != "config.json") or name in ("findings.md", "go-live-plan.md"):
            os.remove(os.path.join(home, name))
            removed += 1
    return removed


def drop_stale(home):
    """Remove the .json files an earlier version wrote to the workspace and this version no longer reads."""
    if os.path.isdir(home):
        for name in os.listdir(home):
            if name.endswith(".json") and name != "config.json" and name not in LEDGER_JSON:
                os.remove(os.path.join(home, name))


def load_ledger(home):
    """(collections, bank lines). Refuses a ledger an earlier version wrote."""
    collections = read_json(os.path.join(home, "collections.json"))
    if collections is None:
        raise XrayError("No ledger yet. Run `intake` (or `demo`) first.")
    info = read_json(os.path.join(home, "intake.json")) or {}
    if info.get("ledger_format") != intake.LEDGER_FORMAT:
        raise XrayError("This workspace was read by an older X-ray. Run intake again.")
    return collections, read_json(os.path.join(home, "bank.json"), [])


def out(args, data, text_fn):
    if args.json:
        print(json.dumps(data, indent=1, ensure_ascii=False, default=str))
    else:
        text_fn(data)


def twikey_lines(lines):
    for t in lines if isinstance(lines, list) else [lines]:
        print(claims.render(t))


def lang_of(cfg, args=None):
    lang = getattr(args, "lang", None) or cfg.get("lang") or "en"
    lang = lang if lang in ("en", "nl", "fr") else "en"
    CURRENT["lang"] = lang
    return lang


def codes(items, limit=12):
    vals = [v for v in items if v]
    more = len(vals) - limit
    return ", ".join(vals[:limit]) + (T("and_more") % num(more) if more > 0 else "")


# --------------------------------------------------------------------------- init, demo, intake

def cmd_init(args):
    home = home_dir(args)
    raw = real(args.raw)
    check_start(raw)
    if not os.path.isdir(raw):
        raise XrayError("Folder not found. Create it, put your camt.053 bank statements in it, and run init again.")
    check_raw_location(raw, home)
    cfg = load_config(home, required=False)
    switching = bool(cfg.get("raw_dir")) and real(cfg["raw_dir"]) != raw
    if switching and not args.force:
        raise XrayError("This workspace already uses another raw folder. Add --force to switch.")
    if switching:
        clear_ledger(home)
    cfg.update({"version": VERSION, "raw_dir": raw, "demo": False, "as_of": args.as_of or None,
                "lang": args.lang or cfg.get("lang") or "en"})
    save_config(home, cfg)
    register_raw(raw)
    lang_of(cfg, args)
    data = {"version": VERSION, "workspace": home, "raw_dir": raw, "registry": registry_path()}
    out(args, data, lambda d: print(T("init").format(workspace=d["workspace"], raw=d["raw_dir"])))


def print_intake(res):
    rep = res["report"]
    t = rep["totals"]
    print(T("intake").format(files=pl(len(rep["files"]), "statement")))
    for f in rep["files"]:
        print(T("kept_one" if f["kept"] == 1 else "kept").format(desc=tr(f["description"]), n=pl(f["kept"], "record")))
        for why, n in sorted((f.get("skipped") or {}).items()):
            print(T("skipped").format(n=num(n), why=tr(why)))
    for f in res["files"]:
        if f["status"] != "ok":
            print(T("skip_" + f["reason"]).format(file=tr(f["file"])))
    print(T("ledger").format(customers=pl(t["direct_debit_customers"], "customer"), payers=pl(t["payers"], "payer"),
                             codes=pl(t["parties"], "code"), mandates=pl(t["mandate_codes"], "mandate")))
    for line in ledger_periods(t, rep.get("periods") or {}):
        print("  " + line)
    print(T("not_in_ledger").format(out=pl(t["debit_lines_skipped"], "payment"),
                                    own=pl(t["own_transfers_skipped"], "transfer"),
                                    dups=pl(t["duplicates_removed"], "copy")))
    if t["invalid_structured_communications"]:
        print(T("bad_ogm").format(n=num(t["invalid_structured_communications"])))
    if t["other_references"]:
        print(T("other_refs").format(n=num(t["other_references"])))
    print(T("coded"))


def ledger_periods(t, periods):
    """One line per kind of record, each with its own period, so counts from different periods never share a line."""
    def span(p):
        return T("span").format(start=dlong(p["from"]), end=dlong(p["to"])) if p else ""

    rows = (("bank_in", "bank_credit_lines", "bank"), ("coll_in", "collections_collected", "collections"),
            ("failed_in", "failed_collections", "failed_collections"))
    return [T(key).format(n=count(t[total]), span=span(periods.get(period))) for key, total, period in rows]


def intake_data(res):
    return {"version": VERSION, "status": "ok", "files": res["report"]["files"],
            "skipped_files": [{"file": f["file"], "reason": f["reason"]} for f in res["files"] if f["status"] != "ok"],
            "totals": res["report"]["totals"], "periods": res["report"]["periods"]}


def run_intake(args, home, cfg):
    res = intake.run(cfg["raw_dir"], cfg)
    lang_of(cfg, args)
    drop_stale(home)
    intake.write(home, cfg["raw_dir"], res)
    out(args, intake_data(res), lambda d: print_intake(res))
    return 0


def cmd_intake(args):
    home = home_dir(args)
    cfg = load_config(home)
    lang_of(cfg, args)
    if not cfg.get("raw_dir"):
        raise XrayError("No raw folder set. Run `init --raw <folder>` first.")
    return run_intake(args, home, cfg)


def reset_demo_folder(path):
    """The plugin's own demo folder holds only fictional statements, their key and reports on them: empty it, so
    files and codes from an earlier demo never mix in. A symlink is removed, never followed."""
    if os.path.islink(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)


def cmd_demo(args):
    home = home_dir(args)
    raw = real(args.raw or os.path.join(state_dir(), "demo-raw"))
    check_start(raw)
    demo_files = sorted(f for f in os.listdir(DEMO_DIR) if f.endswith(".xml"))
    if args.raw:
        os.makedirs(raw, exist_ok=True)
        foreign = [f for f in os.listdir(raw)
                   if not f.startswith(".") and f not in demo_files and not intake.is_ours(f)]
        if foreign:
            raise XrayError("That folder already holds other files. Pick an empty folder for the demo.")
    check_raw_location(raw, home, allow_inside_cwd=True)
    if not args.raw:
        reset_demo_folder(os.path.join(state_dir(), "demo-raw"))
        raw = real(os.path.join(state_dir(), "demo-raw"))
    for f in demo_files:
        shutil.copyfile(os.path.join(DEMO_DIR, f), os.path.join(raw, f))
    cfg = load_config(home, required=False)
    if cfg.get("raw_dir") and real(cfg["raw_dir"]) != raw:
        clear_ledger(home)
    cfg.update({"version": VERSION, "raw_dir": raw, "demo": True, "as_of": DEMO_AS_OF,
                "lang": args.lang or cfg.get("lang") or "en"})
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
    collections, _bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = checks.decode(collections, lang)

    def txt(d):
        p = d["period"]
        cat_names = T("cat")
        colon = claims.COLON[lang]  # French: a space before the colon
        if not d["total"]["count"]:
            print(T("dec_none"))
        else:
            print(T("dec_total").format(n=num(d["total"]["count"]), amount=money(d["total"]["amount"]),
                                        start=dlong(p["from"]), end=dlong(p["to"]), months=pl(p["months"], "month")))
        if d["by_code"]:
            print("\n" + T("by_code"))
        for r in d["by_code"]:
            cats = ", ".join("%s%s %s" % (cat_names.get(k, k), colon, num(v))
                             for k, v in sorted(r["categories"].items()))
            meaning = r["meaning"] or T("no_code")
            if r.get("meaning_source"):
                meaning = T("epc").format(meaning=meaning)
            print("  %-5s %3d  %12s  %s  %s%s" % (r["label"] or "?", r["count"], money(r["amount"]), cats, meaning,
                                                 "  " + r["page"] if r["page"] else ""))
        if d["by_category"]:
            print("\n" + T("points_to"))
        width = max([13] + [len(cat_names.get(cat, cat)) for cat in d["by_category"]])
        for cat, v in d["by_category"].items():
            print("  %-*s %3d  %12s  %s" % (width, cat_names.get(cat, cat), v["count"], money(v["amount"]),
                                            v["meaning"]))
        if d["days_of_month"] and d["days_of_month_overall"]:
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
        print(d["basis"])
        twikey_lines(d["twikey"])
    out(args, data, txt)


def cmd_payments(args):
    home = home_dir(args)
    cfg = load_config(home)
    lang = lang_of(cfg, args)
    _collections, bank = load_ledger(home)
    data = checks.payments(bank, lang)

    def txt(d):
        p = d["period"]
        if not d["credit_lines"]["count"]:
            print(T("pay_none"))
            twikey_lines(d["twikey"])
            return
        print(T("pay_head").format(n=num(d["credit_lines"]["count"]), amount=money(d["credit_lines"]["amount"]),
                                   start=dlong(p["from"]), end=dlong(p["to"]), months=pl(p["months"], "month")))
        labels = T("pay_groups")
        for k in checks.PAYMENT_GROUPS:
            g = d["groups"][k]
            print(T("pay_line").format(label=labels[k], n=count(g["count"]), amount=money(g["amount"]),
                                       codes="  " + codes(g["customers"]) if k != "valid" and g["customers"] else ""))
        h = d["by_hand"]
        print(T("by_hand").format(n=num(h["count"]) if h["count"] else T("none"), total=num(d["credit_lines"]["count"]),
                                  share=pct(h["share_pct"]), amount=money(h["amount"]), per_month=dec(h["per_month"])))
        if h["customers"]:
            print(T("by_hand_most").format(list=codes(h["customers"])))
        print(T("method").format(method=d["method"]))
        twikey_lines(d["twikey"])
    out(args, data, txt)


def cmd_steps(args):
    home = home_dir(args)
    cfg = load_config(home)
    collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = checks.steps(collections, bank, as_of(cfg, args), lang)
    t = checks.manual_steps(lang)["text"]

    def txt(d):
        print(t["title"].format(date=dlong(d["as_of"])))
        for i in d["items"]:
            if not i["count"]:
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
        zero = [i["label"] for i in d["items"] if not i["count"]]
        if zero:
            print(t["none"].format(labels=monthmod.join(zero, t["and"])))
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
    collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = monthmod.prepare(collections, bank, as_of(cfg, args), args.since_days, lang, args.mail_lang or lang)
    # The work pack holds names: it goes next to the raw exports, and only its path is printed.
    path = monthmod.write_pack(raw, data, intake.load_key(raw))
    data["paths"] = {"month_report": path}
    write_json(os.path.join(home, "month.json"), data)
    out(args, data, lambda d: print(d["paths"]["month_report"]))


def cmd_golive(args):
    home = home_dir(args)
    cfg = load_config(home)
    collections, bank = load_ledger(home)
    lang = lang_of(cfg, args)
    data = checks.golive(collections, bank, args.tool, lang)

    def txt(d):
        print(T("golive_head"))
        print(T("gl_dd").format(n=num(d["direct_debit_customers"]), core=num(d["core_customers"]),
                                b2b=num(d["b2b_customers"]), mandates=pl(d["mandates"], "mandate")))
        if d["collections_per_month"] is not None:
            print(T("gl_collections").format(n=dec(d["collections_per_month"]), failed=dec(d["failed_per_month"] or 0),
                                             rate=pct(d["failure_rate_pct"])))
        print(T("gl_transfers").format(n=num(d["payers_by_transfer"]), transfers=dec(d["transfers_per_month"] or 0),
                                       by_hand=dec(d["by_hand_per_month"] or 0)))
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
        if d["intake"] and "statements" in d["intake"]:
            t = d["intake"]
            print(T("st_ledger").format(date=dlong(d["intake_at"][:10]), statements=pl(t["statements"], "statement"),
                                        customers=pl(t["direct_debit_customers"], "customer"),
                                        payers=pl(t["payers"], "payer")))
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

LANGS = ["en", "nl", "fr"]


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

    s = sub("init", "set the raw folder with the camt.053 statements", cmd_init)
    s.add_argument("--raw", required=True)
    s.add_argument("--force", action="store_true")
    s = sub("demo", "load the fictional demo company", cmd_demo)
    s.add_argument("--raw")
    sub("intake", "read the camt.053 statements into the coded ledger", cmd_intake)
    sub("decode", "failed collections by reason code", cmd_decode)
    sub("payments", "incoming payments and the ones to book by hand", cmd_payments)
    sub("steps", "manual steps per finding, counted from the statements", cmd_steps)
    s = sub("month", "this month's work, prepared (drafts only, nothing is sent)", cmd_month)
    s.add_argument("--mail-lang", dest="mail_lang", choices=LANGS)
    s.add_argument("--since-days", dest="since_days", type=int, default=monthmod.DEFAULT_SINCE_DAYS)
    s = sub("golive", "facts for the go-live plan", cmd_golive)
    s.add_argument("--tool")
    s = sub("report", "write the final report with names next to the raw files", cmd_report)
    s.add_argument("--findings")
    sub("status", "what the workspace holds", cmd_status)
    return p


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
        # Never the message or a traceback: they can carry a file name or a value from a statement.
        msg = ("Unexpected error (%s). Nothing about your files is shown. Run the command again, or tell Twikey "
               "the error type above." % type(e).__name__)
    if want_json:
        print(json.dumps({"version": VERSION, "error": msg}))
    else:
        print("ERROR: %s" % msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
