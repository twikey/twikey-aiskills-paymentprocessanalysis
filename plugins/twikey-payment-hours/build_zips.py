#!/usr/bin/env python3
"""Copy the shared files into every skill, then build one zip per skill for claude.ai.

  python3 -B build_zips.py [--out DIR]     sync, then zip
  python3 -B build_zips.py --sync          sync only

The calculator and the shared references have one source each (scripts/hours.py, references/*.md). Every skill
gets a copy, so each skill folder works on its own: as a claude.ai upload and inside the Claude Code plugin.
Each zip holds one folder named after the skill, with SKILL.md at its top, the upload format claude.ai expects.
Zips are reproducible: fixed timestamps and file order. By default they are written to the repository's
claude-ai/ folder (two levels up from this plugin: repo/plugins/<plugin>).
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS = ["process-map", "method-compare", "chasing-check", "matching-check", "automation-report"]
SHARED = {"scripts/hours.py": "scripts/hours.py",
          "references/twikey-claims.md": "references/twikey-claims.md",
          "references/formulas.md": "references/formulas.md"}
SKIP = {"__pycache__", ".DS_Store"}
STAMP = (2026, 11, 4, 0, 0, 0)
DEFAULT_OUT = os.path.normpath(os.path.join(ROOT, os.pardir, os.pardir, "claude-ai"))


def sync():
    for skill in SKILLS:
        base = os.path.join(ROOT, "skills", skill)
        if not os.path.isfile(os.path.join(base, "SKILL.md")):
            sys.exit("missing skills/%s/SKILL.md" % skill)
        for src, dst in SHARED.items():
            target = os.path.join(base, dst)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, src), target)
    print("synced %s into %d skills" % (", ".join(SHARED), len(SKILLS)))


def files_of(base):
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP)
        for name in sorted(filenames):
            if name not in SKIP and not name.endswith(".pyc"):
                out.append(os.path.join(dirpath, name))
    return out


def build(out):
    os.makedirs(out, exist_ok=True)
    for skill in SKILLS:
        base = os.path.join(ROOT, "skills", skill)
        path = os.path.join(out, skill + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files_of(base):
                info = zipfile.ZipInfo(os.path.join(skill, os.path.relpath(f, base)), STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if f.endswith(".py") else 0o644) << 16
                with open(f, "rb") as fh:
                    z.writestr(info, fh.read())
        print(path)


if __name__ == "__main__":
    args = sys.argv[1:]
    sync()
    if "--sync" not in args:
        build(os.path.abspath(args[args.index("--out") + 1]) if "--out" in args else DEFAULT_OUT)
