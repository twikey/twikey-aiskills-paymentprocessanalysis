#!/usr/bin/env python3
"""
Twikey Payment X-ray guard: a PreToolUse hook that keeps Claude's tools away from the raw export folder.

It runs on every tool call (hooks.json matcher "*", so MCP tools and Monitor too). It knows two zones.

In the X-ray folder (the folder Claude was started in when it set up the X-ray, or any folder that holds a
twikey-xray-workspace/config.json), a shell command may only be the plugin's own script in its exact form:
`python3|python [-B] <this plugin>/scripts/twikey_xray.py [--home X] [--as-of X] [--lang X] [--json] <command> ...`
with no shell operators. Every other shell command is denied. Claude reads the results with Read.

Everywhere, and as the only rule outside the X-ray folder, a call is denied when:
- a file tool (Read, Write, Edit, MultiEdit, NotebookEdit) points into a registered raw folder,
- Glob or Grep searches a raw folder, a folder above it, or uses a pattern that names it,
- any string in the tool input names a raw folder or is a path to the key file,
- a shell word with a wildcard has the raw folder, a folder in it or a folder above it as its base,
- a shell command runs a recursive tool (grep -r, rg, find, ls -R, cp -r, tar, zip, rsync, mdfind and similar)
  on a raw folder or on any folder above it.
A shell command line is split on `;`, `&&`, `||`, `|` and newlines. `cd`, `pushd` and `cd -` move the folder later
paths are resolved against, CDPATH included, also inside `{ }`, `if`, `for`, `while`, `case` and functions.
Variables set in the command are expanded, and the text after `bash -c`, `sh -c` and `eval` is checked as a
command of its own. Code after `python -c` and similar, and code an interpreter or shell reads from a heredoc, a
here-string or a pipe, may not name the raw folder. A command that builds a path at run time (`$(...)`,
backticks, `eval`, `cd -`, `CDPATH=`, a variable set in the command) is denied when it also names the raw folder,
uses a wildcard or reaches a folder above the raw folder.

Paths are compared without regard to case (the macOS and Windows disks ignore case), after expanding `~` and
environment variables, with relative paths resolved against the cwd of the event. A path is checked both the way
the system opens it (links first, so link/.. is the folder above the link's target) and the way `cd` reads it.

Failure modes:
- No raw folder registered: no decision, even on malformed input. Without a registered folder there is nothing to
  protect. hooks.json has no "onFailure" setting, so when python3 is missing the hook fails to start and Claude
  Code goes on without it. Without Python, intake cannot run either, so no raw folder can exist.
- A raw folder registered and the input malformed, or the registry unreadable: the guard denies (fail closed).

This is a guard against accidental reads by Claude's tools, not a lock. A command or script built to reach the
folder another way (one that assembles the folder name from pieces, or one written to disk and run later), an
MCP tool that gets the folder and the file name as separate fields, or a determined user gets past it.

Standalone on purpose: standard library only, no imports from the rest of the plugin.
Input: the PreToolUse JSON on stdin. Output: a deny decision as JSON, or nothing (no decision).
"""
import json
import os
import re
import shlex
import sys

KEY_FILE = "twikey-xray-key.json"
REGISTRY = "raw-folders.json"
WORKSPACE = "twikey-xray-workspace"
CLI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "twikey_xray.py")
CLI_SUBCOMMANDS = {"init", "demo", "intake", "decode", "payments", "steps", "month", "golive", "report", "status"}
CLI_OPTIONS_WITH_VALUE = {"--home", "--as-of", "--lang"}
ALLOWED_INTERPRETERS = {"python3", "python"}
FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "NotebookRead": "notebook_path"}
SEARCH_TOOLS = {"Glob", "Grep"}
_SHELL_META = re.compile(r"[;&|<>`()\n\r]")
_GLOB = re.compile(r"[*?\[{]")
_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

# Recursive commands: name -> flags that make them recursive (None: always recursive).
RECURSIVE = {
    "grep": {"-r", "-R", "--recursive", "--dereference-recursive"},
    "egrep": {"-r", "-R", "--recursive"},
    "fgrep": {"-r", "-R", "--recursive"},
    "rg": None, "ag": None, "ack": None, "find": None, "fd": None, "tree": None, "du": None,
    "ls": {"-R", "--recursive"},
    "cp": {"-r", "-R", "-a", "--recursive", "--archive"},
    "scp": {"-r"},
    "rm": {"-r", "-R", "--recursive"},
    "chmod": {"-R", "--recursive"},
    "tar": None, "zip": None, "7z": None, "rsync": None, "mdfind": None, "locate": None,
    # PowerShell
    "get-childitem": {"-recurse"}, "gci": {"-recurse"}, "dir": {"-recurse"},
    "select-string": {"-recurse"}, "copy-item": {"-recurse"}, "compress-archive": None,
}
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "select-string"}
WRAPPERS = {"sudo", "env", "nice", "time", "command", "exec", "xargs", "nohup", "builtin"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
INTERPRETERS = {"python", "python3", "python2", "node", "ruby", "perl", "php", "osascript", "pwsh", "powershell"}
CHDIR = {"cd", "pushd", "chdir", "set-location", "sl"}
CODE_FLAGS = {"-c", "-e", "-r", "--eval", "-Command", "-m"}
SHELL_KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "for", "while", "until", "case",
                  "esac"}
_FUNC_DEF = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*\(\)$")  # name() when written as one word


# --------------------------------------------------------------------------- paths

def state_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("TWIKEY_XRAY_STATE_DIR") or "~/.twikey-xray"))


def expand(s, local=None):
    """~ and $VARS, with variables set inside the command line first."""
    if local:
        s = _VAR.sub(lambda m: local.get(m.group(1) or m.group(2), m.group(0)), s)
    return os.path.expandvars(os.path.expanduser(s))


def real(path, cwd=None, local=None, logical=False):
    """The folder or file a path reaches. By default the way the system opens it: links first, then `..`
    (link/.. is the folder above the link's target). logical=True is the way `cd` moves: `..` first, then links."""
    p = expand(path, local)
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    if logical:
        p = os.path.abspath(p)
    return os.path.realpath(p)


def reaches(path, cwd=None, local=None):
    """Both readings of a path: as the system opens it, and as `cd` and some tools read it."""
    a, b = real(path, cwd, local), real(path, cwd, local, logical=True)
    return [a] if a == b else [a, b]


def fold(path):
    """Case-insensitive form of a path for comparisons."""
    return path.lower()


def inside(path, folder):
    p, f = fold(path), fold(folder)
    return p == f or p.startswith(f.rstrip("/\\") + os.sep)


def _spellings(dirs, cwd):
    out = []
    for d in dirs:
        p = expand(d)
        given = os.path.abspath(p if os.path.isabs(p) else os.path.join(cwd, p))
        for form in (given, real(d, cwd)):  # both spellings, e.g. /tmp and /private/tmp on macOS
            if form not in out:
                out.append(form)
    return out


def load_state(cwd):
    """(raw folders, X-ray folders) from the registry that init and demo write, plus the workspace configs we can
    find. A file that exists but cannot be read raises, so the caller denies (fail closed)."""
    raws, works = [], []
    reg = os.path.join(state_dir(), REGISTRY)
    if os.path.exists(reg):
        with open(reg, encoding="utf-8") as f:
            data = json.load(f)
        raws.extend(data.get("raw_dirs", []))
        works.extend(data.get("work_dirs", []))
    homes = [os.environ.get("TWIKEY_XRAY_HOME"), os.path.join(cwd, WORKSPACE)]
    for home in homes:
        if not home:
            continue
        folder = real(home, cwd)
        cfg = os.path.join(folder, "config.json")
        if os.path.exists(cfg):
            with open(cfg, encoding="utf-8") as f:
                raw = json.load(f).get("raw_dir")
            if raw:
                raws.append(raw)
            works.append(os.path.dirname(folder))
    return _spellings(raws, cwd), _spellings(works, cwd)


def load_raw_dirs(cwd):
    return load_state(cwd)[0]


def needles(raw, cwd):
    """Ways a string can name the raw folder."""
    home = os.path.expanduser("~")
    forms = {raw}
    if raw.startswith("/private/"):  # macOS: /tmp and /var are links into /private
        forms.add(raw[len("/private"):])
    for base in list(forms):
        if inside(base, home) and fold(base) != fold(home):
            rest = base[len(home):].lstrip(os.sep)
            forms.update({"~/" + rest, "$HOME/" + rest, "${HOME}/" + rest})
    try:
        rel = os.path.relpath(raw, cwd)
        if rel not in (".", "") and not inside(cwd, raw):
            forms.add(rel)
    except ValueError:
        pass
    return [fold(f) for f in forms if f and len(f) > 3]


def mentions(text, raws, cwd, local=None):
    """A string that contains a spelling of a raw folder. (The key file is matched as a path, in path_hit.)"""
    if not text:
        return None
    low = fold(text)
    expanded = fold(expand(text, local))
    for raw in raws:
        for n in needles(raw, cwd):
            if n in low or n in expanded:
                return raw
    return None


def names_basename(text, raws):
    """The raw folder's own name anywhere in a text (any case)."""
    low = fold(text or "")
    for raw in raws:
        base = fold(os.path.basename(raw.rstrip("/\\")))
        if len(base) >= 3 and base in low:
            return raw
    return None


def path_hit(value, raws, cwd, local=None):
    """A string that is a path into a raw folder (any case, ~, $VARS, relative to cwd)."""
    if not value or len(value) > 4096 or "\n" in value:
        return None
    if os.path.basename(expand(value, local).rstrip("/\\")).lower() == KEY_FILE:
        return "the X-ray key file"
    for p in reaches(value, cwd, local):
        for raw in raws:
            if inside(p, raw):
                return raw
    return None


def search_bases(arg, cwd, local=None):
    """The folders a path argument reaches (both readings): for a glob, the part before the first wildcard."""
    a = expand(arg, local)
    m = _GLOB.search(a)
    if m:
        a = os.path.dirname(a[:m.start()]) or "."
    return reaches(a, cwd)


def near(bases, raws):
    """A raw folder that is one of the bases, inside one, or above one."""
    for base in bases:
        for raw in raws:
            if inside(raw, base) or inside(base, raw):
                return raw
    return None


def glob_hit(word, raws, cwd, local=None):
    """A word with a wildcard whose base folder is a raw folder, a folder inside one, or a folder above one."""
    if not _GLOB.search(expand(word, local)):
        return None
    return near(search_bases(word, cwd, local), raws)


def above_raw(word, raws, cwd, local=None):
    """A word that is a folder above a raw folder (.., ~, /, ~/Documents ...)."""
    if not word or word.startswith("-") or len(word) > 4096:
        return None
    for p in reaches(word, cwd, local):
        for raw in raws:
            if inside(raw, p) and fold(raw) != fold(p):
                return raw
    return None


# --------------------------------------------------------------------------- the plugin's own script

def cli_form(command):
    """The tokens when the command is exactly
    `python3|python [-B] <this plugin>/scripts/twikey_xray.py [--home X] [--as-of X] [--lang X] [--json] <command> ...`
    with no shell operators, else None."""
    if _SHELL_META.search(command) or "$(" in command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if len(tokens) < 3 or tokens[0] not in ALLOWED_INTERPRETERS:
        return None
    i = 1
    if tokens[i] == "-B":
        i += 1
    if i >= len(tokens) or fold(real(tokens[i])) != fold(os.path.realpath(CLI_PATH)):
        return None
    i += 1
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] in CLI_OPTIONS_WITH_VALUE:
            i += 2
        elif tokens[i] == "--json":
            i += 1
        else:
            return None
    if i >= len(tokens) or tokens[i] not in CLI_SUBCOMMANDS:
        return None
    return tokens


def allowed_cli(command):
    return cli_form(command) is not None


def cli_hit(tokens, raws, cwd):
    """The plugin's own script may name the raw folder only as the value of --raw (init, demo)."""
    i = 3 if tokens[1] == "-B" else 2
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in CLI_OPTIONS_WITH_VALUE else 1
    sub = tokens[i] if i < len(tokens) else None
    for j, w in enumerate(tokens):
        if j and tokens[j - 1] == "--raw" and sub in ("init", "demo"):
            continue
        hit = mentions(w, raws, cwd) or path_hit(w, raws, cwd) or glob_hit(w, raws, cwd)
        if hit:
            return "the X-ray script with an argument that names %s" % hit
    return None


# --------------------------------------------------------------------------- shell commands

def segments(command):
    """Split a shell command into simple commands (lists of words). Newlines separate commands too.
    Raises ValueError when the line cannot be split."""
    command = command.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ; ")
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    segs, cur = [], []
    for tok in lex:
        if tok and all(c in ";&|()<>" for c in tok):
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        segs.append(cur)
    return segs


def _command_index(words, local):
    """Index of the command word after shell keywords and grouping ({, !, if, then, do ...), variable assignments
    (recorded in local) and wrappers (sudo, env ...). So a cd inside { }, if, for, while or a function counts."""
    i = 0
    while i < len(words):
        m = _ASSIGN.match(words[i])
        if words[i] in SHELL_KEYWORDS or _FUNC_DEF.match(words[i]):
            i += 1
        elif words[i] == "function":
            i += 2  # the keyword and the function's name
        elif m:
            local[m.group(1)] = expand(m.group(2), local)
            i += 1
        elif os.path.basename(words[i]).lower() in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
        else:
            break
    return i


def _command_name(word):
    name = os.path.basename(word).lower()
    return name[:-4] if name.endswith(".exe") else name


def dynamic(command):
    """Parts of a command line that build a path at run time."""
    found = []
    if "$(" in command or "`" in command:
        found.append("command substitution")
    if re.search(r"(^|[\s;&|(])eval\s", command):
        found.append("eval")
    if re.search(r"(^|[\s;&|(])(cd|pushd)\s+-(\s|$|;|&|\|)", command):
        found.append("cd -")
    if "CDPATH" in command:
        found.append("CDPATH")
    if re.search(r"(^|[\s;&|(])(export\s+)?[A-Za-z_][A-Za-z0-9_]*=", command):
        found.append("a variable set in the command")
    if re.search(r"\$\{?(PWD|OLDPWD)\b", command):
        found.append("$PWD")
    return found


def recursive_hit(words, i, name, raws, cwd, every_word, local=None):
    piped = any(os.path.basename(w).lower() == "xargs" for w in words[:i])
    if name in ("mdfind", "locate") and "-onlyin" not in words[i + 1:]:
        return "%s over the whole disk, which holds %s" % (name, raws[0]) if raws else None
    if name not in RECURSIVE:
        return None
    args = words[i + 1:]
    powershell = name in ("get-childitem", "gci", "dir", "select-string", "copy-item")
    flags = [a.lower() if powershell else a for a in args if a.startswith("-")]
    need = RECURSIVE[name]
    if need is not None:
        short = set()
        for f in flags:
            if f.startswith("-") and not f.startswith("--") and len(f) > 2:
                short |= {"-" + c for c in f[1:]}
        if not (set(flags) | short) & need:
            return None
    paths = [a for a in args if not a.startswith("-")]
    if name in PATTERN_FIRST and len(paths) <= 1:
        paths.append(".")  # only a pattern: the search runs in the current folder
    paths = paths or ["."]
    if piped:  # xargs: the paths come from another part of the command
        paths += every_word
    for a in paths:
        for base in search_bases(a, cwd, local):
            for raw in raws:
                if inside(raw, base):
                    return "%s on a folder that holds %s" % (name, raw)
    return None


def reads_code_from_stdin(name, args, command):
    """An interpreter or shell that takes its code from a pipe, a heredoc or a here-string (python3 - <<EOF,
    node <<EOF, bash <<EOF, echo ... | python3)."""
    if any(a in CODE_FLAGS for a in args):
        return False
    scripts = [a for a in args if not a.startswith("-") or a == "-"]
    return not scripts or scripts[0] == "-" or "<<" in command


def shell_hit(command, raws, cwd, depth=0):
    """Check a shell command line outside the X-ray folder. Raises ValueError when it cannot be split."""
    if depth > 4:
        return "a shell command nested too deep to check"
    segs = segments(command)
    every_word = [w for s in segs for w in s if not w.startswith("-")]
    local, cur, previous, lost = {}, cwd, None, False
    cdpath = os.environ.get("CDPATH")
    for words in segs:
        i = _command_index(words, local)
        cdpath = local.get("CDPATH", cdpath)
        for w in words:
            hit = mentions(w, raws, cur, local) or path_hit(w, raws, cur, local)
            if hit:
                return "a shell command that names %s" % hit
            hit = glob_hit(w, raws, cur, local)
            if hit:
                return "a wildcard on a folder that holds %s" % hit
        if i >= len(words):
            continue
        name = _command_name(words[i])
        args = words[i + 1:]
        if name in SHELLS and "-c" in args and args.index("-c") + 1 < len(args):
            hit = shell_hit(args[args.index("-c") + 1], raws, cur, depth + 1)
            if hit:
                return "%s -c with %s" % (name, hit)
        if name == "eval":
            hit = shell_hit(" ".join(args), raws, cur, depth + 1)
            if hit:
                return "eval with %s" % hit
        interpreter = name in INTERPRETERS or re.match(r"^python\d(\.\d+)?$", name)
        if interpreter:
            for j, a in enumerate(args):
                if a in CODE_FLAGS and j + 1 < len(args):
                    hit = names_basename(args[j + 1], raws) or mentions(args[j + 1], raws, cur, local)
                    if hit:
                        return "%s code that names %s" % (name, hit)
        if (interpreter or name in SHELLS) and reads_code_from_stdin(name, args, command):
            # the code is in the command line (heredoc, here-string, echo ... |): the same rule as for -c
            hit = names_basename(command, raws) or mentions(command, raws, cur, local)
            if hit:
                return "%s code on its input that names %s" % (name, hit)
        if name in CHDIR:
            targets = [a for a in args if not a.startswith("-") or a == "-"]
            target = targets[0] if targets else "~"
            if target == "-":
                if previous is None:
                    lost = True
                    continue
                cur, previous = previous, cur
                continue
            # cd moves the logical way (`..` first); the other reading is checked too
            candidates = [real(target, cur, local, logical=True), real(target, cur, local)]
            if cdpath and not os.path.isabs(expand(target, local)) and not target.startswith("."):
                candidates += [real(os.path.join(expand(c, local) or ".", target), cur, local, logical=True)
                               for c in cdpath.split(":")]
            for c in candidates:
                for raw in raws:
                    if inside(c, raw):
                        return "cd into %s" % raw
            if "$" in target or "`" in target:
                lost = True
            previous, cur = cur, candidates[0]
            continue
        hit = recursive_hit(words, i, name, raws, cur, every_word, local)
        if hit:
            return hit
    built = dynamic(command)
    if built or lost:
        how = ", ".join(built) or "a folder change that cannot be followed"
        hit = names_basename(command, raws)
        if hit:
            return "a command that builds a path at run time (%s) and names %s" % (how, hit)
        for words in segs:
            for w in words:
                if _GLOB.search(w) and not w.startswith("-"):
                    return "a command that builds a path at run time (%s) and uses a wildcard" % how
                hit = above_raw(w, raws, cwd, local)
                if hit:
                    return "a command that builds a path at run time (%s) and reaches a folder above %s" % (how, hit)
    return None


# --------------------------------------------------------------------------- the decision

def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            for s in _strings(v):
                yield s
    elif isinstance(value, list):
        for v in value:
            for s in _strings(v):
                yield s


ZONE_MESSAGE = ("Twikey Payment X-ray blocked a shell command in the X-ray folder. In this folder X-ray only runs "
                "its own commands, exactly as the skills write them (python3 -B <plugin>/scripts/twikey_xray.py "
                "... without pipes, redirects or other commands). Read the results with the Read tool, for "
                "example twikey-xray-workspace/findings.md.")


def in_xray_folder(cwd, works):
    c = real(cwd)
    return any(inside(c, w) for w in works)


def decide(event, raws, works=()):
    """Return a deny reason, or None for no decision (the normal permission flow continues)."""
    tool = event.get("tool_name") or ""
    ti = event.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {"input": ti}
    cwd = event.get("cwd") or os.getcwd()

    if tool in FILE_TOOLS:
        hit = path_hit(ti.get(FILE_TOOLS[tool]), raws, cwd)
        if hit:
            return "%s on %s" % (tool, hit)
    if tool in SEARCH_TOOLS:
        hit = near(search_bases(ti.get("path") or ".", cwd), raws)
        if hit:
            return "%s over a folder that holds %s" % (tool, hit)
        for key in ("pattern", "glob"):
            v = ti.get(key)
            if v and (os.path.isabs(expand(v)) or v.startswith(("~", "$", "."))):
                hit = near(search_bases(v, cwd), raws)
                if hit:
                    return "%s with a pattern into %s" % (tool, hit)

    command = ti.get("command") if isinstance(ti.get("command"), str) else None
    tokens = cli_form(command) if command else None
    if command:
        if tokens is not None:
            hit = cli_hit(tokens, raws, cwd)
            if hit:
                return hit
        elif in_xray_folder(cwd, works):
            return ZONE
        else:
            try:
                hit = shell_hit(command, raws, cwd)
            except ValueError:
                hit = "a shell command that could not be checked"
            if hit:
                return hit
    rest = {k: v for k, v in ti.items() if not (tokens is not None and k in ("command", "description"))}
    for s in _strings(rest):
        hit = mentions(s, raws, cwd) or path_hit(s, raws, cwd)
        if hit:
            return "%s with input that names %s" % (tool or "a tool", hit)
    return None


ZONE = object()  # marker: the X-ray folder rule, with its own message

MESSAGE = ("Twikey Payment X-ray blocked %s. The raw exports hold names, IBANs and payer text, and Claude works "
           "only with the coded workspace. Read the exports with `twikey_xray.py intake` and write the final "
           "report with `twikey_xray.py report`. This guard prevents accidental reads by Claude's tools. It is not "
           "a lock: the user can switch it off by disabling the twikey-payment-xray plugin.")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    try:
        text = sys.stdin.read()
    except Exception:  # noqa: BLE001
        text = ""
    event, problem = None, None
    try:
        event = json.loads(text)
        if not isinstance(event, dict):
            raise ValueError("input is not a JSON object")
    except Exception as e:  # noqa: BLE001
        problem = e
    cwd = (event.get("cwd") if isinstance(event, dict) else None) or os.getcwd()
    try:
        raws, works = load_state(cwd)
    except Exception as e:  # noqa: BLE001 - a registry that exists but cannot be read: fail closed
        deny("Twikey Payment X-ray guard could not read its list of protected folders (%s: %s), so the call was "
             "blocked to be safe. Check %s or disable the twikey-payment-xray plugin."
             % (type(e).__name__, str(e)[:200], os.path.join(state_dir(), REGISTRY)))
        return 0
    if not raws:
        return 0  # nothing to protect: no decision, even on malformed input
    try:
        if problem is not None:
            raise problem
        reason = decide(event, raws, works)
        if reason is ZONE:
            deny(ZONE_MESSAGE)
        elif reason:
            deny(MESSAGE % reason)
    except Exception as e:  # noqa: BLE001 - fail closed while a raw folder is registered
        deny("Twikey Payment X-ray guard could not check this tool call (%s: %s), so it was blocked to be safe. "
             "If this repeats, check %s or disable the twikey-payment-xray plugin."
             % (type(e).__name__, str(e)[:200], os.path.join(state_dir(), REGISTRY)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
