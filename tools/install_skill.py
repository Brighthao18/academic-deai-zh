"""Install this reviewed Skill locally; refuse to replace existing directories."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from public_scope import ROOT, SKILL_NAME, runtime_files


def install(destination: Path, root: Path = ROOT) -> dict:
    destination = Path(destination).expanduser()
    files = runtime_files(root)
    # mkdir with exist_ok=False also refuses an existing empty installation.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(files.items()):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    return {"installed": str(destination.resolve()), "files": len(files)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path,
                        default=Path.home() / ".agents" / "skills" / SKILL_NAME,
                        help="Complete destination directory; must not exist")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.dest), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
