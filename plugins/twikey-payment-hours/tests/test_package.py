"""Plugin manifest, skill folders, shared copies, zips and the copy rules for every shipped file."""
import glob
import importlib.util
import json
import os
import re
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ["process-map", "method-compare", "chasing-check", "matching-check", "automation-report"]
SHARED = ["scripts/hours.py", "references/twikey-claims.md", "references/formulas.md"]
SKILL_PATH = '"${CLAUDE_SKILL_DIR}/scripts/hours.py"'

# Words that must appear in no shipped file. Built from pieces, so this file does not contain them either.
BRAND = "auto" + "pay"
PEOPLE = ["sa" + "bir", "ko" + "en", "domin" + "ique", "domin" + "iek", "fri" + "so"]
INTERNAL = ["to" + "do", "fix" + "me", "x" + "xx", "lorem", "build" + "-brief", "claims" + "-notes", "con" + "tract.md"]
# Build and working files that must never sit inside the plugin folder.
INTERNAL_FILES = ["CON" + "TRACT.md", "OP" + "EN.md", "RES" + "UME.md", "HIS" + "TORY.md", "CLAIMS" + "-NOTES.md",
                  "BUILD" + "-BRIEF.md"]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def shipped_files():
    out = [os.path.join(ROOT, "README.md"), os.path.join(ROOT, ".claude-plugin", "plugin.json"),
           os.path.join(ROOT, "build_zips.py")]
    for pattern in ("scripts/*.py", "references/*.md", "skills/*/SKILL.md", "skills/*/references/*.md",
                    "skills/*/scripts/*.py"):
        out += glob.glob(os.path.join(ROOT, pattern))
    return sorted(out)


def parse_frontmatter(text):
    """The YAML frontmatter as a dict: PyYAML when installed, else a strict reader of `key: scalar` lines."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    block = m.group(1)
    try:
        import yaml
        return yaml.safe_load(block), text[m.end():]
    except ImportError:
        pass
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(": ")
        if not sep or not re.fullmatch(r"[a-z-]+", key):
            raise ValueError("not a key: value line: %r" % line)
        value = value.strip()
        if value[:1] in "\"'":
            if value[-1:] != value[:1]:
                raise ValueError("unclosed quote: %r" % line)
            value = value[1:-1]
        elif ": " in value or " #" in value:
            raise ValueError("plain scalar with ': ' or ' #': %r" % line)
        fields[key] = value
    return fields, text[m.end():]


class ManifestTest(unittest.TestCase):
    def test_plugin_json(self):
        p = json.loads(read(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        self.assertEqual(p["name"], "twikey-payment-hours")
        self.assertEqual(p["displayName"], "Payment Hours")
        self.assertEqual(p["author"]["name"], "Twikey")
        self.assertEqual(load_module("hours", os.path.join(ROOT, "scripts", "hours.py")).VERSION, p["version"])


class SkillTest(unittest.TestCase):
    def test_the_five_skills(self):
        found = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))
        self.assertEqual(found, sorted(SKILLS))

    def test_frontmatter_parses_and_description_fits(self):
        for name in SKILLS:
            fields, body = parse_frontmatter(read(os.path.join(ROOT, "skills", name, "SKILL.md")))
            self.assertIsInstance(fields, dict, name)
            self.assertEqual(fields.get("name"), name)
            desc = fields.get("description", "")
            # 200: the claude.ai help center limit, well under the 1,024 of the Agent Skills docs.
            self.assertLessEqual(len(desc), 200, "%s: %d characters" % (name, len(desc)))
            self.assertIn("Use ", desc, name)
            self.assertIn("formulas.md", body, name)  # the fallback when code execution is off
            self.assertLess(len(body.splitlines()), 150, name)  # short SKILL.md, details in references

    def test_script_path_uses_skill_dir_with_fallback(self):
        docs = glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")) + [
            p for p in glob.glob(os.path.join(ROOT, "skills", "*", "references", "*.md"))
            if os.path.basename(p) not in ("twikey-claims.md", "formulas.md")]
        for path in docs:
            text = read(path)
            for token in ("<skill folder>", "SKILL/scripts", "SKILL_DIR/scripts", "/mnt/skills"):
                self.assertNotIn(token, text, path)
            for m in re.finditer(r"python3 -B (\S+)", text):
                self.assertEqual(m.group(1), SKILL_PATH, path)
        for name in SKILLS:
            body = read(os.path.join(ROOT, "skills", name, "SKILL.md"))
            self.assertIn(SKILL_PATH, body, name)
            self.assertIn("folder this SKILL.md is in", body, name)

    def test_windows_python_fallback(self):
        for name in SKILLS:
            body = read(os.path.join(ROOT, "skills", name, "SKILL.md"))
            self.assertIn("`py -3`, then with `python`", body, name)
            self.assertIn(SKILL_PATH, body, name)  # quoted, so a path with spaces works

    def test_no_number_picked_for_the_user(self):
        for name in SKILLS:
            self.assertIn("never pick one", read(os.path.join(ROOT, "skills", name, "SKILL.md")), name)

    def test_shared_copies_match_the_source(self):
        for name in SKILLS:
            for rel in SHARED:
                copy = os.path.join(ROOT, "skills", name, rel)
                self.assertTrue(os.path.isfile(copy), "%s: %s missing, run build_zips.py --sync" % (name, rel))
                self.assertEqual(read(copy), read(os.path.join(ROOT, rel)), "%s: %s is stale, run build_zips.py --sync" % (name, rel))


class NeutralCopyTest(unittest.TestCase):
    def test_readme_names_twikey_only_as_the_maker(self):
        text = read(os.path.join(ROOT, "README.md"))
        head, _, maker = text.partition("## Made by Twikey")
        self.assertTrue(maker, "README needs a 'Made by Twikey' section")
        body = head.split("\n", 3)[3]  # after the title and the "by Twikey" line
        for line in body.splitlines():
            if "Twikey" in line:
                self.assertRegex(line, r"Nothing is sent to Twikey|twikey-payment-hours|twikey/twikey-aiskills", line)
        for phrase in ("site says it automates", "word for word", "pricing", "package", "publishes the marketplace"):
            self.assertNotIn(phrase, text.lower(), phrase)

    def test_skill_intros_do_not_name_twikey(self):
        for name in SKILLS:
            fields, body = parse_frontmatter(read(os.path.join(ROOT, "skills", name, "SKILL.md")))
            self.assertNotIn("Twikey", fields["description"], name)
            intro = body.split("## ", 1)[0]
            self.assertNotIn("Twikey", intro.replace("Where Twikey fits", ""), name)


class CopyRulesTest(unittest.TestCase):
    def test_no_forbidden_words(self):
        for path in shipped_files():
            low = read(path).lower()
            for word in [BRAND] + PEOPLE + INTERNAL:
                self.assertNotIn(word, low, "%s: %r" % (os.path.relpath(path, ROOT), word))

    def test_no_m_dash_in_prose(self):
        for path in shipped_files():
            if path.endswith(".md"):
                self.assertNotIn("—", read(path), os.path.relpath(path, ROOT))

    def test_no_price_in_claims(self):
        self.assertNotIn("€", read(os.path.join(ROOT, "references", "twikey-claims.md")))

    def test_no_internal_files_in_the_plugin(self):
        found = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            if "dist" in dirnames:
                found.append(os.path.join(dirpath, "dist"))
            found += [os.path.join(dirpath, f) for f in filenames if f in INTERNAL_FILES or "NOTES" in f.upper()]
        self.assertEqual(found, [])


class ZipTest(unittest.TestCase):
    def setUp(self):
        import contextlib
        import io
        import tempfile
        self.build = load_module("build_zips", os.path.join(ROOT, "build_zips.py"))
        self.tmp = tempfile.TemporaryDirectory()
        self.out1, self.out2 = os.path.join(self.tmp.name, "a"), os.path.join(self.tmp.name, "b")
        with contextlib.redirect_stdout(io.StringIO()):
            self.build.build(self.out1)
            self.build.build(self.out2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_zips_hold_every_file_of_their_skill(self):
        for name in SKILLS:
            base = os.path.join(ROOT, "skills", name)
            expected = {name + "/" + os.path.relpath(f, base).replace(os.sep, "/"): f for f in self.build.files_of(base)}
            with zipfile.ZipFile(os.path.join(self.out1, name + ".zip")) as z:
                self.assertEqual(sorted(z.namelist()), sorted(expected), name)
                self.assertFalse(any("\\" in n for n in z.namelist()), name)  # zip entries use forward slashes
                for arc, src in expected.items():
                    with open(src, "rb") as f:
                        self.assertEqual(z.read(arc), f.read(), arc)

    def test_build_is_reproducible(self):
        for name in SKILLS:
            with open(os.path.join(self.out1, name + ".zip"), "rb") as a, open(os.path.join(self.out2, name + ".zip"), "rb") as b:
                self.assertEqual(a.read(), b.read(), name)

    def test_arcname_uses_forward_slashes_on_windows(self):
        import ntpath
        import types
        real = self.build.os
        self.build.os = types.SimpleNamespace(path=ntpath, sep="\\")
        try:
            self.assertEqual(self.build.arcname("process-map", "C:\\Users\\Jan de Vries\\skills\\process-map",
                                                "C:\\Users\\Jan de Vries\\skills\\process-map\\scripts\\hours.py"),
                             "process-map/scripts/hours.py")
        finally:
            self.build.os = real


if __name__ == "__main__":
    unittest.main()
