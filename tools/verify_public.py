"""Check public scope, metadata, local links, and common accidental disclosures."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

from public_scope import ROOT, public_paths, version

SECRET_PATTERNS = [re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
                   re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
                   re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
                   re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|Coding)[\\/]|" + "/" + r"home/[^/\s]+/)")
LINK = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")


def audit(root: Path = ROOT, tracked: bool = False) -> dict:
    paths = public_paths(root)
    current = version(root)
    errors = []
    for name in paths:
        file = root / name
        try:
            content = file.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append(name + ": invalid UTF-8")
            continue
        if "\ufffd" in content:
            errors.append(name + ": Unicode replacement character")
        if "\r" in content or b"\r" in file.read_bytes():
            errors.append(name + ": source files must use LF newlines")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            errors.append(name + ": potential credential")
        if PRIVATE_PATH.search(content):
            errors.append(name + ": private workstation path")
        if file.suffix == ".json":
            json.loads(content)
        elif file.suffix == ".py":
            ast.parse(content, filename=name)
        elif file.suffix == ".md":
            for target in LINK.findall(content):
                if ":" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                if target and not (file.parent / target).is_file():
                    errors.append(name + ": missing local link " + target)
    if tracked:
        result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
        listed = set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) - {""}
        if listed != set(paths):
            errors.append("Tracked files differ from public scope: " +
                          json.dumps({"unexpected": sorted(listed - set(paths)),
                                      "missing": sorted(set(paths) - listed)}))
    if errors:
        raise ValueError("\n".join(errors))
    return {"passed": True, "version": current, "public_files": len(paths),
            "tracked_scope_checked": tracked, "scope": "distribution hygiene; not a complete security audit"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(tracked=args.tracked), ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
