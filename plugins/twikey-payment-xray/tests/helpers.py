"""Shared test setup: paths, a throwaway workspace, and an in-process CLI runner."""
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PLUGIN, "scripts")
TESTS = os.path.join(PLUGIN, "tests")
DEMO = os.path.join(PLUGIN, "demo")
CLI = os.path.join(SCRIPTS, "twikey_xray.py")
GUARD = os.path.join(SCRIPTS, "xray", "guard.py")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)

import twikey_xray  # noqa: E402
from xray import common  # noqa: E402

# Today's date for every test, so no test depends on the day it runs. The demo is as of October 31, 2026.
TODAY = dt.date(2026, 11, 3)
common.TODAY = TODAY


def expected():
    return load(os.path.join(TESTS, "expected_demo.json"))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Sandbox:
    """A temp folder with a work folder (Claude's cwd), a raw folder outside it and a state folder."""

    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="xray-test-"))
        self.work = os.path.join(self.root, "work")
        self.raw = os.path.join(self.root, "raw")
        self.state = os.path.join(self.root, "state")
        os.makedirs(self.work)
        os.makedirs(self.raw)
        self.home = os.path.join(self.work, "twikey-xray-workspace")
        self._cwd = None
        self._env = None

    def __enter__(self):
        self._cwd = os.getcwd()
        self._env = os.environ.get("TWIKEY_XRAY_STATE_DIR")
        os.chdir(self.work)
        os.environ["TWIKEY_XRAY_STATE_DIR"] = self.state
        return self

    def __exit__(self, *exc):
        os.chdir(self._cwd)
        if self._env is None:
            os.environ.pop("TWIKEY_XRAY_STATE_DIR", None)
        else:
            os.environ["TWIKEY_XRAY_STATE_DIR"] = self._env
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *argv):
        """Run the CLI in-process. Returns (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = twikey_xray.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def cli_json(self, *argv):
        code, out, err = self.cli(*(list(argv) + ["--json"]))
        return code, json.loads(out) if out.strip() else None

    def copy_demo(self, names=None):
        for f in sorted(os.listdir(DEMO)):
            if names is None or f in names:
                shutil.copyfile(os.path.join(DEMO, f), os.path.join(self.raw, f))

    def write_raw(self, name, text, encoding="utf-8"):
        with open(os.path.join(self.raw, name), "w", encoding=encoding, newline="") as f:
            f.write(text)
