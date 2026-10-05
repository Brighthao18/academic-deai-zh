"""Explicit distribution scope shared by audit, installation, and packaging."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "academic-deai-zh"
SKILL_PREFIX = ".agents/skills/" + SKILL_NAME + "/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_paths(root: Path = ROOT) -> list[str]:
    data = json.loads((root / "public-files.json").read_text(encoding="utf-8"))
    paths = data["files"]
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ValueError("Public scope must contain a list of relative paths")
    if len(set(paths)) != len(paths) or paths != sorted(paths):
        raise ValueError("Public paths must be unique and sorted")
    forbidden = {"Codex", "corpus", "execution", ".git", ".venv", "dist"}
    for name in paths:
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or "\\" in name
                or ":" in name or name != path.as_posix()
                or set(path.parts) & forbidden or "__pycache__" in path.parts
                or path.name.startswith(".env") or path.suffix in {".pyc", ".key", ".pem"}):
            raise ValueError("Unsafe public path: " + name)
        file = root / name
        if any(parent.is_symlink() for parent in [file, *file.parents] if parent != root.parent):
            raise ValueError("Public files must not use symlinks: " + name)
        if not file.is_file():
            raise ValueError("Missing public file: " + name)
    return paths


def version(root: Path = ROOT) -> str:
    value = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("VERSION must be a stable semantic version")
    tree = ast.parse((root / SKILL_PREFIX / "scripts/deai_core.py").read_text(encoding="utf-8"))
    declared = next((ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets)), None)
    if declared != value:
        raise ValueError("Runtime and distribution versions differ")
    for file in (root / SKILL_PREFIX / "SKILL.md", root / SKILL_PREFIX / "references/contracts.md",
                 root / "docs/runtime.md"):
        if value not in file.read_text(encoding="utf-8"):
            raise ValueError("Missing current version in " + file.name)
    return value


def runtime_files(root: Path = ROOT) -> dict[str, bytes]:
    paths = public_paths(root)
    files = {p[len(SKILL_PREFIX):]: (root / p).read_bytes()
             for p in paths if p.startswith(SKILL_PREFIX)}
    files.update({"LICENSE": (root / "LICENSE").read_bytes(),
                  "README.md": (root / "docs/runtime.md").read_bytes(),
                  "UPSTREAM.md": (root / "docs/upstream.md").read_bytes(),
                  "VERSION": (root / "VERSION").read_bytes()})
    manifest = {"schema_version": "1.0", "version": version(root), "license": "MIT",
                "files": {name: {"bytes": len(data), "sha256": sha256(data)}
                          for name, data in sorted(files.items())}}
    files["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return files
