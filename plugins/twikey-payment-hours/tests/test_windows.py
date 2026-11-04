"""Windows-proofing: output in any console code page, files in UTF-8, folders with spaces and accents."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOURS = os.path.join(ROOT, "scripts", "hours.py")
ANSWERS = ["company.lang=fr", "company.hourly_cost=48", "payments.per_month=400", "payments.avg_amount=310",
           "task.match.main.count=400*45%", "task.match.main.minutes=4", "task.match.main.mode=manual",
           "task.match.main.label=Rapprochement à la main, réglé", "task.chase.main.count=112",
           "task.chase.main.minutes=6", "task.chase.main.label=Relances écrites",
           "method.transfer.share=70", "method.transfer.minutes=1.8", "method.transfer.days=38",
           "method.card.share=30", "method.card.fee_fixed=0.25", "method.card.fee_pct=1.4", "method.card.days=2",
           "note.dso=DSO : 41 jours, votre chiffre"]


def run(args, cwd, **env):
    full = dict(os.environ)
    full.pop("PYTHONUTF8", None)
    full.update(env)
    return subprocess.run([sys.executable, "-B", HOURS] + args, cwd=cwd, env=full, capture_output=True)


class ConsoleEncodingTest(unittest.TestCase):
    """Windows consoles default to cp1252 (or another code page); the output holds €, ×, ÷ and accents."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertEqual(run(["set"] + ANSWERS, self.tmp).returncode, 0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, **env):
        for cmd in (["process"], ["methods"], ["report"], ["show"]):
            p = run(cmd, self.tmp, **env)
            self.assertEqual(p.returncode, 0, (cmd, env, p.stderr.decode("utf-8", "replace")))
            text = p.stdout.decode("utf-8")  # always UTF-8, whatever the console says
            self.assertIn("×" if cmd != ["show"] else "à", text, cmd)
        report = run(["report"], self.tmp, **env).stdout.decode("utf-8")
        self.assertIn(" €", report)  # French money: 1 790,40 €
        self.assertIn("Rapprochement à la main, réglé", report)

    def test_cp1252_console(self):
        self.check(PYTHONIOENCODING="cp1252")

    def test_ascii_locale_without_utf8_mode(self):
        self.check(PYTHONUTF8="0", LANG="C", LC_ALL="C", PYTHONIOENCODING="")

    def test_error_message_survives_cp1252(self):
        p = run(["set", "task.match.main.count=12é"], self.tmp, PYTHONIOENCODING="cp1252")
        self.assertEqual(p.returncode, 2)
        self.assertIn("error:", p.stderr.decode("utf-8"))


class FolderNameTest(unittest.TestCase):
    """A working folder with a space and an accent, like C:\\Users\\Jan\\Mijn Documenten\\é."""

    def test_space_and_accent_in_the_working_folder(self):
        base = tempfile.mkdtemp()
        try:
            work = os.path.join(base, "Mijn Documenten", "é")
            os.makedirs(work)
            self.assertEqual(run(["set"] + ANSWERS, work, PYTHONIOENCODING="cp1252").returncode, 0)
            for cmd in (["process"], ["methods"]):
                self.assertEqual(run(cmd, work, PYTHONIOENCODING="cp1252").returncode, 0, cmd)
            out = os.path.join(work, "rapport heures é.md")
            p = run(["report", "--out", out], work, PYTHONIOENCODING="cp1252")
            self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
            with open(out, "rb") as f:
                raw = f.read()
            self.assertNotIn(b"\r\n", raw)  # one line ending on every system
            self.assertIn("€", raw.decode("utf-8"))
            with open(os.path.join(work, "twikey-payment-hours.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["tasks"]["match"]["main"]["label"], "Rapprochement à la main, réglé")
            ledger = os.path.join(base, "Mijn Documenten", "é", "ledger copy.json")
            shutil.copyfile(os.path.join(work, "twikey-payment-hours.json"), ledger)
            self.assertEqual(run(["--ledger", ledger, "process"], base).returncode, 0)
        finally:
            shutil.rmtree(base)

    def test_ledger_with_a_byte_order_mark(self):
        """Notepad on Windows can save UTF-8 with a BOM."""
        base = tempfile.mkdtemp()
        try:
            path = os.path.join(base, "twikey-payment-hours.json")
            with open(path, "w", encoding="utf-8-sig") as f:
                json.dump({"company": {"lang": "nl"}, "tasks": {"match": {"main": {"count": 10, "minutes": 3}}}}, f)
            p = run(["process"], base)
            self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        finally:
            shutil.rmtree(base)


class PortableCodeTest(unittest.TestCase):
    def test_no_posix_only_modules_or_hard_coded_separators(self):
        for path in (HOURS, os.path.join(ROOT, "build_zips.py")):
            with open(path, encoding="utf-8") as f:
                code = f.read()
            for module in ("fcntl", "termios", "pwd", "grp", "resource", "posix"):
                self.assertNotRegex(code, r"(?m)^\s*(import|from) %s\b" % module, (path, module))
            self.assertNotIn('os.path.join(ROOT, "scripts/', code)
        with open(HOURS, encoding="utf-8") as f:
            code = f.read()
        for line in code.splitlines():
            if "open(" in line and "def " not in line:
                self.assertIn("encoding=", line, line)


if __name__ == "__main__":
    unittest.main()
