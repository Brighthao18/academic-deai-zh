"""Build a reproducible, allowlisted Skill ZIP without touching original texts."""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from public_scope import ROOT, SKILL_NAME, public_paths, runtime_files, sha256, version


def build_release(output_dir: Path, root: Path = ROOT) -> dict:
    current = version(root)
    files = runtime_files(root)
    basename = SKILL_NAME + "-v" + current
    output_dir = Path(output_dir)
    archive = output_dir / (basename + ".zip")
    manifest_file = output_dir / (basename + "-manifest.json")
    sums = output_dir / "SHA256SUMS"
    if any(p.exists() for p in (archive, manifest_file, sums)):
        raise ValueError("Release output already exists; choose a new directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    # Stored entries avoid compression-library differences between platforms.
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as bundle:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(SKILL_NAME + "/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_STORED
            bundle.writestr(item, data)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("ZIP integrity verification failed")
        expected = {SKILL_NAME + "/" + p: data for p, data in files.items()}
        if set(bundle.namelist()) != set(expected):
            raise ValueError("Unexpected ZIP contents")
        if any(bundle.read(p) != data for p, data in expected.items()):
            raise ValueError("Packaged bytes differ from reviewed source")
    manifest = {"schema_version": "1.0", "version": current, "license": "MIT",
                "archive": {"name": archive.name, "bytes": archive.stat().st_size,
                            "sha256": sha256(archive.read_bytes())},
                "runtime_files": {name: {"bytes": len(data), "sha256": sha256(data)}
                                  for name, data in sorted(files.items())},
                "source_files": {p: sha256((root / p).read_bytes()) for p in public_paths(root)}}
    with manifest_file.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with sums.open("x", encoding="utf-8", newline="\n") as stream:
        for file in (archive, manifest_file):
            stream.write(sha256(file.read_bytes()) + "  " + file.name + "\n")
    return {"version": current, "archive": str(archive),
            "manifest": str(manifest_file), "sha256sums": str(sums),
            "zip_sha256": manifest["archive"]["sha256"], "files": len(files)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-tag", help="Require the release tag to match VERSION")
    args = parser.parse_args(argv)
    try:
        if args.expected_tag is not None and args.expected_tag != "v" + version():
            raise ValueError("Release tag does not match VERSION")
        print(json.dumps(build_release(args.output_dir), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
