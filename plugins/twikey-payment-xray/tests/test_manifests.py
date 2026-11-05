"""Plugin, marketplace and hook files, and the skills, in the shape the Claude Code docs describe."""
import glob
import os
import re
import unittest

from tests.helpers import PLUGIN, load, read_text

REPO = os.path.dirname(os.path.dirname(PLUGIN))
SKILLS = ["xray-setup", "xray-scan", "failure-decoder", "mandate-health", "unmatched-payments", "terms-vs-reality",
          "manual-steps", "month-prep", "go-live-plan"]


def frontmatter(path):
    text = read_text(path)
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields, text[m.end():]


class ManifestTest(unittest.TestCase):
    def test_plugin_json(self):
        p = load(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"))
        self.assertEqual(p["name"], "twikey-payment-xray")
        self.assertEqual(p["version"], "0.2.1")
        self.assertEqual(p["author"]["name"], "Twikey")
        self.assertTrue(p["keywords"])
        from xray import VERSION
        self.assertEqual(VERSION, p["version"])

    def test_marketplace_json(self):
        m = load(os.path.join(REPO, ".claude-plugin", "marketplace.json"))
        self.assertEqual(m["name"], "twikey-xray")
        self.assertEqual(m["owner"]["name"], "Twikey")
        names = [p["name"] for p in m["plugins"]]
        # The dev repo also lists Payment Hours. The public release lists X-ray only.
        self.assertIn(names, (["twikey-payment-hours", "twikey-payment-xray"], ["twikey-payment-xray"]))
        entry = m["plugins"][names.index("twikey-payment-xray")]
        self.assertTrue(entry["source"].startswith("./"))
        self.assertEqual(os.path.realpath(os.path.join(REPO, entry["source"])), os.path.realpath(PLUGIN))
        self.assertNotIn("version", entry)  # plugin.json holds the version

    def test_hooks_json_shape(self):
        h = load(os.path.join(PLUGIN, "hooks", "hooks.json"))
        self.assertEqual(list(h["hooks"]), ["PreToolUse"])  # wrapped in a top-level "hooks" key
        hook = h["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual((hook["type"], hook["command"]), ("command", "python3"))
        # No "onFailure": "block". Without python3 the hook fails to start and must not block every tool in
        # every project. A missing python3 also means no raw folder can exist.
        self.assertNotIn("onFailure", hook)
        self.assertLessEqual(hook["timeout"], 30)
        # every tool, MCP tools and Monitor included ("*" matches all tools per the hooks docs)
        self.assertEqual(h["hooks"]["PreToolUse"][0]["matcher"], "*")


class SkillTest(unittest.TestCase):
    def test_the_nine_skills(self):
        found = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
        self.assertEqual(found, sorted(SKILLS))

    def test_frontmatter_and_rules(self):
        for name in SKILLS:
            fields, body = frontmatter(os.path.join(PLUGIN, "skills", name, "SKILL.md"))
            self.assertEqual(fields.get("name"), name)
            desc = fields.get("description", "")
            self.assertIn("Use when", desc, name)
            self.assertLess(len(desc), 1024, name)
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/twikey_xray.py"', body, name)
            self.assertRegex(body, r"(?i)never (open, )?read", name)
            self.assertIn("user's language", body, name)
            for cmd in re.findall(r"twikey_xray\.py\" --home twikey-xray-workspace (?:--lang [a-z]+ )?([a-z<]+)",
                                  body):
                self.assertIn(cmd, ("init", "demo", "intake", "decode", "mandates", "match", "terms", "steps",
                                    "month", "golive", "report", "status", "<command>"), name)

    def test_every_python_call_uses_dash_b(self):
        # -B: no .pyc files with local paths next to the plugin
        texts = [os.path.join(PLUGIN, "skills", n, "SKILL.md") for n in SKILLS] + [os.path.join(REPO, "README.md"),
                                                                                    os.path.join(PLUGIN, "README.md")]
        for path in texts:
            for m in re.finditer(r"\bpython3? (?!-B\b)\S+", read_text(path)):
                self.assertFalse("twikey_xray.py" in m.group(0) or "unittest" in m.group(0)
                                 or "make_demo" in m.group(0), "%s: %s" % (os.path.basename(path), m.group(0)))
        hook = load(os.path.join(PLUGIN, "hooks", "hooks.json"))["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(hook["args"][0], "-B")


if __name__ == "__main__":
    unittest.main()
