"""The PreToolUse guard: decisions on sample hook input, run the way Claude Code runs it."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import GUARD, PLUGIN, load
from xray import guard
from xray.common import KEY_FILE

CLI = os.path.join(PLUGIN, "scripts", "twikey_xray.py")


class GuardSetup(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="xray-guard-"))
        self.work = os.path.join(self.root, "project")
        self.raw = os.path.join(self.root, "payment exports")  # a space on purpose
        self.state = os.path.join(self.root, "state")
        for d in (self.work, self.raw, self.state):
            os.makedirs(d)
        with open(os.path.join(self.state, "raw-folders.json"), "w") as f:
            json.dump({"raw_dirs": [self.raw]}, f)
        self.env = dict(os.environ, TWIKEY_XRAY_STATE_DIR=self.state)
        self.env.pop("TWIKEY_XRAY_HOME", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def event(self, tool, **tool_input):
        return {"session_id": "t", "hook_event_name": "PreToolUse", "cwd": self.work, "permission_mode": "default",
                "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_test"}

    def run_hook(self, payload):
        """Run guard.py exactly as hooks.json does: python3 <guard.py>, JSON on stdin."""
        data = payload if isinstance(payload, str) else json.dumps(payload)
        p = subprocess.run([sys.executable, GUARD], input=data, capture_output=True, text=True, env=self.env,
                           cwd=self.work, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout.strip():
            return None
        out = json.loads(p.stdout)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        return hso["permissionDecision"], hso["permissionDecisionReason"]


class DenyTest(GuardSetup):
    def assertDenied(self, payload):
        result = self.run_hook(payload)
        self.assertIsNotNone(result, payload)
        self.assertEqual(result[0], "deny")
        return result[1]

    def test_file_tools_on_raw_files(self):
        f = os.path.join(self.raw, "afschrift.xml")
        for tool in ("Read", "Write", "Edit", "MultiEdit"):
            reason = self.assertDenied(self.event(tool, file_path=f))
            self.assertIn("not a lock", reason)
        self.assertDenied(self.event("NotebookEdit", notebook_path=os.path.join(self.raw, "x.ipynb")))

    def test_key_file_anywhere(self):
        self.assertDenied(self.event("Read", file_path=os.path.join(self.work, KEY_FILE)))
        self.assertDenied(self.event("Bash", command="cat ~/Downloads/%s" % KEY_FILE))
        self.assertDenied(self.event("Bash", command='cp "$HOME/x/%s" .' % KEY_FILE))

    def test_key_file_name_in_plain_text_is_not_a_path(self):
        # the deny matches the key file as a path, not any text that contains its name
        self.assertIsNone(self.run_hook(self.event("Write", file_path=os.path.join(self.work, "notes.md"),
                                                   content="Never share %s with anyone." % KEY_FILE)))
        self.assertIsNone(self.run_hook(self.event("Bash", command="echo done",
                                                   description="Explain what %s is for" % KEY_FILE)))

    def test_search_tools(self):
        self.assertDenied(self.event("Grep", pattern="IBAN", path=self.raw))
        self.assertDenied(self.event("Grep", pattern="IBAN", path=self.root))       # a folder above the raw folder
        self.assertDenied(self.event("Glob", pattern="*.xml", path=self.raw))
        self.assertDenied(self.event("Glob", pattern=os.path.join(self.raw, "*.xml")))
        self.assertDenied(self.event("Grep", pattern="x", glob=os.path.join(self.raw, "**")))

    def test_shell_commands(self):
        q = '"%s"' % self.raw
        for cmd in ("cat %s/afschrift.xml" % q, "ls %s" % q, "head -5 %s/bank.xml" % q,
                    "cp %s/bank.xml ." % q, "grep -r IBAN %s" % q):
            self.assertDenied(self.event("Bash", command=cmd))
        rel = os.path.relpath(self.raw, self.work)
        self.assertDenied(self.event("Bash", command="cat '%s/x.xml'" % rel))
        self.assertDenied(self.event("PowerShell", command="Get-Content %s\\x.xml" % q))

    def test_allowed_cli_cannot_be_chained(self):
        q = '"%s"' % self.raw
        for cmd in ('python3 "%s" intake && cat %s/x.xml' % (CLI, q),
                    'python3 "%s" intake; cat %s/x.xml' % (CLI, q),
                    'python3 "%s" init --raw %s | tee out.txt' % (CLI, q),
                    'python3 "%s" init --raw %s > out.txt' % (CLI, q),
                    'python3 "%s" init --raw $(echo %s)' % (CLI, q),
                    'python3 "%s" decode --raw %s' % (CLI, q),
                    'python3 other.py init --raw %s' % q,
                    # a script name inside -c code is not the script
                    'python3 -c "import os; os.system(\'cat %s/x.xml\') #/twikey_xray.py" intake' % self.raw,
                    'python3 -c "print(open(\'%s/x.xml\').read())#/twikey_xray.py" intake' % self.raw,
                    'python3 -I "%s" init --raw %s' % (CLI, q),
                    'TWIKEY_XRAY_HOME=ws python3 "%s" init --raw %s' % (CLI, q),
                    '/tmp/evil/python3 "%s" init --raw %s' % (CLI, q),
                    'python3 /tmp/elsewhere/twikey_xray.py init --raw %s' % q):
            self.assertDenied(self.event("Bash", command=cmd))

    def test_fail_closed_on_bad_input(self):
        self.assertDenied("this is not json")
        self.assertDenied("[1, 2]")

    def test_fail_closed_on_broken_registry(self):
        with open(os.path.join(self.state, "raw-folders.json"), "w") as f:
            f.write("{broken")
        reason = self.assertDenied(self.event("Read", file_path=os.path.join(self.work, "notes.md")))
        self.assertIn("blocked to be safe", reason)

    # ------------------------------------------------------------------ case, ~, variables, relative paths

    def test_paths_ignore_case_and_expand_home_vars_and_relative(self):
        self.env["HOME"] = self.root
        self.env["EXPORTS"] = self.raw
        self.assertDenied(self.event("Read", file_path=os.path.join(self.raw.upper(), "afschrift.xml")))
        self.assertDenied(self.event("Read", file_path="~/payment exports/afschrift.xml"))
        self.assertDenied(self.event("Read", file_path="~/PAYMENT EXPORTS/afschrift.xml"))
        self.assertDenied(self.event("Read", file_path="$EXPORTS/afschrift.xml"))
        self.assertDenied(self.event("Read", file_path="../payment exports/afschrift.xml"))
        self.assertDenied(self.event("Bash", command='cat "$EXPORTS/afschrift.xml"'))
        self.assertDenied(self.event("Bash", command="cat ~/Payment\\ Exports/afschrift.xml"))
        self.assertDenied(self.event("Read", file_path=os.path.join(self.work, "TWIKEY-XRAY-KEY.json")))

    def test_every_tool_and_every_string(self):
        f = os.path.join(self.raw, "afschrift.xml")
        self.assertDenied(self.event("mcp__filesystem__read_file", path=f))
        self.assertDenied(self.event("mcp__x__tool", options={"files": [f]}))
        self.assertDenied(self.event("Monitor", command="tail -f %s" % f, description="watch"))
        self.assertDenied(self.event("WebFetch", url="file://%s" % f, prompt="x"))

    def test_recursive_commands_on_an_ancestor(self):
        self.env["HOME"] = self.root
        root = '"%s"' % self.root
        for cmd in ("grep -r IBAN %s" % root, "grep -rn IBAN ~", "rg IBAN ~", "rg BE68 /",
                    "find %s -name '*.xml'" % root, "find ~ -type f", "ls -R %s" % root, "ls -laR ~",
                    "cp -r %s /tmp/copy" % root, "tar czf /tmp/x.tgz %s" % root, "zip -r /tmp/x.zip ~",
                    "rsync -a ~/ /tmp/backup", "cd /tmp && grep -R IBAN ~/pay*", "du -sh ~/*",
                    "sudo find / -name x", "echo ~ | xargs grep -r IBAN"):
            self.assertDenied(self.event("Bash", command=cmd))
        # only a pattern: rg and grep -r search the current folder, here a folder above the raw folder
        ev = self.event("Bash", command="rg IBAN")
        ev["cwd"] = self.root
        self.assertDenied(ev)
        ev = self.event("Bash", command="grep -rl BE68")
        ev["cwd"] = self.root
        self.assertDenied(ev)

    def test_recursive_commands_elsewhere_pass(self):
        self.env["HOME"] = self.root
        for cmd in ("grep -r FIXME .", "rg C001 twikey-xray-workspace", "find . -name '*.py'", "ls -R src",
                    "cp -r src /tmp/src-copy", "tar czf /tmp/w.tgz twikey-xray-workspace", "grep IBAN notes.md"):
            self.assertIsNone(self.run_hook(self.event("Bash", command=cmd)), cmd)

    # ------------------------------------------------------------------ failure modes

    def test_fail_open_when_nothing_is_registered(self):
        os.remove(os.path.join(self.state, "raw-folders.json"))
        self.assertIsNone(self.run_hook("this is not json"))
        self.assertIsNone(self.run_hook("[1, 2]"))
        self.assertIsNone(self.run_hook(self.event("Bash", command="grep -r x /")))

    def test_workspace_config_alone_protects_the_raw_folder(self):
        os.remove(os.path.join(self.state, "raw-folders.json"))
        ws = os.path.join(self.work, "twikey-xray-workspace")
        os.makedirs(ws)
        with open(os.path.join(ws, "config.json"), "w") as f:
            json.dump({"raw_dir": self.raw}, f)
        self.assertDenied(self.event("Read", file_path=os.path.join(self.raw, "a.xml")))


class HomeLayoutTest(unittest.TestCase):
    """The exports in ~/Documents/payment-exports, Claude started in ~/Documents/project (a reviewer's layout)."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="xray-home-"))
        self.home = os.path.join(self.root, "home")
        self.raw = os.path.join(self.home, "Documents", "payment-exports")
        self.cwd = os.path.join(self.home, "Documents", "project")
        self.state = os.path.join(self.root, "state")
        for d in (self.raw, self.cwd, self.state, os.path.join(self.home, "payment-xray")):
            os.makedirs(d)
        # a link in the project to a folder one level below home: link/.. is home, not the project
        os.symlink(os.path.join(self.home, "payment-xray"), os.path.join(self.cwd, "xlink-in-project"))
        with open(os.path.join(self.raw, "bank.xml"), "w") as f:
            f.write("x\n")
        with open(os.path.join(self.state, "raw-folders.json"), "w") as f:
            json.dump({"raw_dirs": [self.raw]}, f)
        self.env = dict(os.environ, HOME=self.home, TWIKEY_XRAY_STATE_DIR=self.state)
        self.env.pop("TWIKEY_XRAY_HOME", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def decision(self, tool, **ti):
        ev = {"tool_name": tool, "tool_input": ti, "cwd": self.cwd, "hook_event_name": "PreToolUse"}
        p = subprocess.run([sys.executable, GUARD], input=json.dumps(ev), capture_output=True, text=True,
                           env=self.env, cwd=self.cwd, timeout=20)
        return "deny" if '"deny"' in p.stdout else "allow"

    def test_wildcards_cd_and_spellings(self):
        cli = 'python3 "%s"' % CLI
        cases = [
            ("Bash", {"command": "cat ~/Documents/payment-exports/bank.xml"}),
            ("Bash", {"command": "cat ~/Documents/pay*/bank.xml"}),
            ("Bash", {"command": "ls ~/Documents/*"}),
            ("Bash", {"command": "head -n 3 ../*/*.xml"}),
            ("Bash", {"command": "head -1 ../p*/bank.xml"}),
            ("Bash", {"command": "cd ~/Documents && cat payment-exports/bank.xml"}),
            ("Bash", {"command": "cd .. && grep -r IBAN ."}),
            ("Bash", {"command": "cd .. && ls payment-exports"}),
            ("Bash", {"command": "pushd .. && cat payment-exports/bank.xml"}),
            ("Bash", {"command": "cd ..; cd payment-exports; cat bank.xml"}),
            ("Bash", {"command": 'cat "$HOME"/Documents/payment-exports/bank.xml'}),
            ("Bash", {"command": "cat ~/Documents/payment-export?/bank.xml"}),
            ("Bash", {"command": "cat ~/Documents/payment-exports/../payment-exports/bank.xml"}),
            ("Bash", {"command": "cat ~/Documents/Payment-Exports/bank.xml"}),
            ("Bash", {"command": "mdfind -onlyin ~/Documents IBAN"}),
            ("Bash", {"command": "mdfind IBAN"}),
            ("Bash", {"command": "zipinfo ~/Documents/x.zip; cat ~/Documents/payment-exports/bank.xml"}),
            ("Read", {"file_path": os.path.join(self.raw, "bank.xml")}),
            ("Read", {"file_path": "../payment-exports/bank.xml"}),
            ("Grep", {"pattern": "IBAN", "path": os.path.join(self.home, "Documents")}),
            ("Glob", {"pattern": "../*/*.xml"}),
            ("Glob", {"pattern": "**/*.xml", "path": ".."}),
            ("Bash", {"command": "%s --home ~/Documents/payment-exports status" % cli}),
            ("Bash", {"command": "%s --home ws report --findings ~/Documents/payment-exports/bank.xml" % cli}),
            ("Bash", {"command": "%s --home ~/Documents/payment-exports intake" % cli}),
        ]
        for tool, ti in cases:
            self.assertEqual(self.decision(tool, **ti), "deny", (tool, ti))

    def test_the_x_ray_script_still_runs(self):
        cli = 'python3 "%s"' % CLI
        for cmd in ("%s --home ws intake --json" % cli, "%s --home ws init --raw ~/Documents/payment-exports" % cli,
                    "ls", "cat notes.md", "grep -r FIXME .", "ls ../project/*.md"):
            self.assertEqual(self.decision("Bash", command=cmd), "allow", cmd)

    def test_known_limit_a_script_built_for_the_purpose(self):
        # Documented in the README: a script that assembles the folder name from pieces gets past the guard
        # outside the X-ray folder. Inside the X-ray folder no shell command but X-ray's own runs at all.
        cmd = ("python3 -c \"import glob;print([open(f).read() for f in "
               "glob.glob('/'.join(['..','payment-'+'exports','*']))])\"")
        self.assertEqual(self.decision("Bash", command=cmd), "allow")
        self.make_xray_folder()
        self.assertEqual(self.decision("Bash", command=cmd), "deny")

    # every attempt from the round-3 verifier, in both zones
    ATTEMPTS = [
        "head -1 ../p*/bank.xml",
        "cd .. && grep -r IBAN .",
        "ls ~/Documents/*",
        "cat ~/Documents/pay*/bank.xml",
        "cd ~/Documents && cat payment-exports/bank.xml",
        "cd ..\ncat payment-exports/bank.xml",
        "bash -c 'cd .. && cat payment-exports/bank.xml'",
        "sh -c \"cd ..; cat payment-exports/bank.xml\"",
        "eval 'cd ..; cat payment-exports/bank.xml'",
        "cd ~/Documents; cd project; cd -; cat payment-exports/bank.xml",
        "D=~/Documents; cat $D/payment-exports/bank.xml",
        "cat \"$(echo ~/Documents)/payment-exports/bank.xml\"",
        "cat \"$(dirname \"$PWD\")/payment-exports/bank.xml\"",
        "cd \"$(dirname \"$PWD\")\" && cat payment-exports/bank.xml",
        "CDPATH=.. cd payment-exports && cat bank.xml",
        "cd .. && cat payment-exports/bank.xml",
        "pushd .. >/dev/null; cat payment-exports/bank.xml",
        "cd ..; cd payment-exports; cat bank.xml",
        "cat ~/Documents/payment-export\"s\"/bank.xml",
        "cat ~/Documents/{payment-exports,x}/bank.xml",
        "awk 1 ../payment-exports/bank.xml",
        "python3 -c \"import os;os.chdir('..');print(open('payment-exports/bank.xml').read())\"",
        "cd .. && python3 -c \"print(open('payment-exports/bank.xml').read())\"",
        "cd ~/Documents/payment-exports && cat *",
        "for d in ../*; do cat $d/bank.xml; done",
        "cat $(ls -d ../p*)/bank.xml",
        "xargs cat <<< ../payment-exports/bank.xml",
        "cat ../payment-exports/twikey-xray-key.json",
        "cp ../payment-exports/bank.xml /tmp/cpout.xml",
        "bash -c \"$(printf 'cat ../payment-exports/bank.xml')\"",
        "X=..; Y=payment-exports; cat $X/$Y/bank.xml",
        # round 4: cd inside compound commands, code on an interpreter's input
        "{ cd ..; cat payment-exports/bank.xml; }",
        "if true; then cd ..; fi; cat payment-exports/bank.xml",
        "for i in 1; do cd ..; done; cat payment-exports/bank.xml",
        "while true; do cd ..; break; done; cat payment-exports/bank.xml",
        "until false; do cd ..; break; done; cat payment-exports/bank.xml",
        "! cd ..; cat payment-exports/bank.xml",
        "function f { cd ..; }; f; cat payment-exports/bank.xml",
        "f() { cd ..; }; f; cat payment-exports/bank.xml",
        "case x in x) cd ..;; esac; cat payment-exports/bank.xml",
        "python3 - <<'EOF'\nimport os\nos.chdir('..')\nprint(open('payment-exports/bank.xml').read())\nEOF",
        "python3 - <<'EOF'\nimport glob\nprint([open(f).read() for f in glob.glob('../*/bank.xml')])\nEOF",
        "node <<'EOF'\nprocess.chdir('..');console.log(require('fs').readFileSync('payment-exports/bank.xml','utf8'))\nEOF",
        "bash <<'EOF'\ncd ..\ncat payment-exports/bank.xml\nEOF",
        "echo \"import os;os.chdir('..');print(open('payment-exports/bank.xml').read())\" | python3",
        "python3 <<< \"import os;os.chdir('..');print(open('payment-exports/bank.xml').read())\"",
        "cd xlink-in-project/.. && cat ../payment-exports/bank.xml",
        "cat xlink-in-project/../Documents/payment-exports/bank.xml",
    ]
    OTHER_TOOLS = [
        ("Read", {"file_path": "xlink-in-project/../Documents/payment-exports/bank.xml"}),
        ("Read", {"file_path": "../payment-exports/bank.xml"}),
        ("Read", {"file_path": "~/DOCUMENTS/Payment-Exports/bank.xml"}),
        ("Grep", {"pattern": "IBAN", "path": ".."}),
        ("Glob", {"pattern": "../*/*.xml"}),
        ("Glob", {"pattern": "**/*.xml", "path": "~"}),
        ("NotebookEdit", {"notebook_path": "../payment-exports/x.ipynb", "new_source": "x"}),
    ]

    def make_xray_folder(self):
        ws = os.path.join(self.cwd, "twikey-xray-workspace")
        os.makedirs(ws, exist_ok=True)
        with open(os.path.join(ws, "config.json"), "w") as f:
            json.dump({"raw_dir": self.raw}, f)

    def test_attempts_outside_the_xray_folder(self):
        for cmd in self.ATTEMPTS:
            self.assertEqual(self.decision("Bash", command=cmd), "deny", cmd)
        for tool, ti in self.OTHER_TOOLS:
            self.assertEqual(self.decision(tool, **ti), "deny", (tool, ti))
        for cmd in ("ls -la ..", "ls", "git status", "python3 -c \"print(1)\"", "echo $HOME",
                    "if true; then echo hi; fi", "for f in *.md; do wc -l $f; done", "{ cd src; ls; }",
                    "python3 - <<'EOF'\nprint(1)\nEOF", "echo 'print(2)' | python3", "python3 script.py",
                    "cd xlink-in-project && ls"):
            self.assertEqual(self.decision("Bash", command=cmd), "allow", cmd)

    def test_known_limit_mcp_fields_apart(self):
        # Documented in the README: an MCP tool that gets the folder and the file name as separate fields is
        # not caught, in either zone. Each field alone names no export folder.
        ti = {"root": "..", "path": "payment-exports/bank.xml"}
        self.assertEqual(self.decision("mcp__fs__read_text_file", **ti), "allow")
        self.make_xray_folder()
        self.assertEqual(self.decision("mcp__fs__read_text_file", **ti), "allow")

    def test_attempts_inside_the_xray_folder(self):
        self.make_xray_folder()
        for cmd in self.ATTEMPTS + ["ls -la ..", "ls", "cat twikey-xray-workspace/findings.md", "echo hi"]:
            self.assertEqual(self.decision("Bash", command=cmd), "deny", cmd)
        self.assertEqual(self.decision("Monitor", command="tail -f notes.txt"), "deny")
        for tool, ti in self.OTHER_TOOLS:
            self.assertEqual(self.decision(tool, **ti), "deny", (tool, ti))
        # X-ray's own commands, in their exact form, still run, and Claude reads results with Read
        cli = 'python3 -B "%s"' % CLI
        for cmd in ("%s --home twikey-xray-workspace decode --json" % cli,
                    "%s --lang nl --home twikey-xray-workspace payments" % cli,
                    "%s --home twikey-xray-workspace --lang nl steps --json" % cli,
                    "%s --home twikey-xray-workspace --lang en month --json" % cli,
                    "%s --home twikey-xray-workspace --lang en month --mail-lang fr --since-days 60 --json" % cli,
                    "%s --home twikey-xray-workspace init --raw ~/Documents/payment-exports" % cli):
            self.assertEqual(self.decision("Bash", command=cmd), "allow", cmd)
        for cmd in ("%s --home twikey-xray-workspace hours --minutes reconcile=3 --json" % cli,  # removed in 0.2.0
                    "%s --home twikey-xray-workspace month --json > month.txt" % cli,
                    "%s --home twikey-xray-workspace decode --json 2>&1" % cli,
                    "%s --home twikey-xray-workspace decode | head" % cli,
                    "%s --home twikey-xray-workspace decode --raw ~/Documents/payment-exports" % cli):
            self.assertEqual(self.decision("Bash", command=cmd), "deny", cmd)
        self.assertEqual(self.decision("Read", file_path=os.path.join(self.cwd, "twikey-xray-workspace",
                                                                      "findings.md")), "allow")

    def test_registered_xray_folder(self):
        with open(os.path.join(self.state, "raw-folders.json"), "w") as f:
            json.dump({"raw_dirs": [self.raw], "work_dirs": [self.cwd]}, f)
        self.assertEqual(self.decision("Bash", command="ls"), "deny")


class AllowTest(GuardSetup):
    def assertNoDecision(self, payload):
        self.assertIsNone(self.run_hook(payload), payload)

    def test_workspace_and_project_files(self):
        ws = os.path.join(self.work, "twikey-xray-workspace")
        self.assertNoDecision(self.event("Read", file_path=os.path.join(ws, "store.json")))
        self.assertNoDecision(self.event("Write", file_path=os.path.join(ws, "findings.md"), content="C001"))
        self.assertNoDecision(self.event("Grep", pattern="C001", path=ws))
        self.assertNoDecision(self.event("Glob", pattern="**/*.json"))
        self.assertNoDecision(self.event("Bash", command="ls -la"))

    def test_the_cli_may_name_the_raw_folder(self):
        q = '"%s"' % self.raw
        for cmd in ('python3 "%s" init --raw %s' % (CLI, q),
                    'python3 "%s" --home twikey-xray-workspace intake --json' % CLI,
                    'python3 "%s" --json demo --raw %s' % (CLI, q),
                    'python "%s" --home ws --as-of 2026-10-31 report' % CLI,
                    'python3 "%s" intake --map "1:#3=invoice_number"' % CLI):
            self.assertNoDecision(self.event("Bash", command=cmd))
        # the skills write ${CLAUDE_PLUGIN_ROOT}; the guard expands it like the shell does
        self.env["CLAUDE_PLUGIN_ROOT"] = PLUGIN
        self.assertNoDecision(self.event(
            "Bash", command='python3 "${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py" init --raw %s' % q,
            description="Point the X-ray at %s" % self.raw))

    def test_nothing_registered_means_no_decision(self):
        os.remove(os.path.join(self.state, "raw-folders.json"))
        self.assertNoDecision(self.event("Read", file_path=os.path.join(self.raw, "a.xml")))

    def test_other_tools_pass(self):
        self.assertNoDecision(self.event("WebSearch", query="SEPA AM04"))


class DecideUnitTest(unittest.TestCase):
    def test_constants_match_the_plugin(self):
        from xray import common
        self.assertEqual(guard.KEY_FILE, common.KEY_FILE)
        self.assertEqual(guard.REGISTRY, common.REGISTRY_FILE)

    def test_macos_private_spelling(self):
        raws = ["/private/var/folders/x/raw"]
        ev = {"tool_name": "Bash", "tool_input": {"command": "cat /var/folders/x/raw/a.xml"}, "cwd": "/Users/u/p"}
        self.assertIsNotNone(guard.decide(ev, raws))

    def test_subcommands(self):
        self.assertEqual(guard.CLI_SUBCOMMANDS, {"init", "demo", "intake", "decode", "payments", "steps", "month",
                                                 "golive", "report", "status"})
        self.assertTrue(guard.allowed_cli('python3 -B "%s" --home ws month --mail-lang nl --json' % CLI))
        self.assertFalse(guard.allowed_cli('python3 -B "%s" --home ws hours --minutes chase=5' % CLI))

    def test_allowed_cli_parser(self):
        self.assertTrue(guard.allowed_cli('python3 "%s" intake' % CLI))
        self.assertTrue(guard.allowed_cli('python "%s" --home "a b" --as-of 2026-10-31 --json report' % CLI))
        self.assertTrue(guard.allowed_cli('python3 "%s" intake' % CLI.upper()))  # the disk ignores case
        self.assertFalse(guard.allowed_cli('python3 /p/scripts/twikey_xray.py intake'))  # not this plugin
        self.assertFalse(guard.allowed_cli('python3.12 "%s" intake' % CLI))
        self.assertFalse(guard.allowed_cli('python3 -I "%s" intake' % CLI))
        self.assertTrue(guard.allowed_cli('python3 -B "%s" --lang nl status' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s" cat' % CLI))
        self.assertFalse(guard.allowed_cli('python3 -B -I "%s" status' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s" --verbose intake' % CLI))
        self.assertFalse(guard.allowed_cli('bash -c "python3 %s intake"' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s" intake `cat x`' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s" intake $(cat x)' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s" intake || cat x' % CLI))
        self.assertFalse(guard.allowed_cli('python3 "%s intake' % CLI))
        self.assertFalse(guard.allowed_cli('python3 -c "x#/twikey_xray.py" intake'))

    def test_hooks_json_runs_this_guard(self):
        hooks = load(os.path.join(PLUGIN, "hooks", "hooks.json"))
        h = hooks["hooks"]["PreToolUse"][0]
        self.assertEqual(h["matcher"], "*")  # every tool, MCP tools and Monitor included
        cmd = h["hooks"][0]
        self.assertEqual(cmd["args"], ["-B", "${CLAUDE_PLUGIN_ROOT}/scripts/xray/guard.py"])  # -B: no .pyc files
        self.assertNotIn("onFailure", cmd)  # without python3 the hook must not block every tool
        self.assertTrue(os.path.exists(os.path.join(PLUGIN, "scripts", "xray", "guard.py")))


if __name__ == "__main__":
    unittest.main()
