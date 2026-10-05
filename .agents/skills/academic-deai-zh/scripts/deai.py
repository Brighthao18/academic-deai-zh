"""Stand-alone stdlib CLI for preparing, gating, and exporting Codex edits."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from deai_core import (InputError, apply_bundle, bind_review, build_bundle, build_review_request, check_review, document_from_path, export_result,
                      mechanical_check, prepare_path, result_envelope, scan_document, text_hash)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise InputError("Cannot parse UTF-8 JSON: " + str(path)) from exc


def write_json(path, value):
    path = Path(path)
    if path.exists():
        raise InputError("JSON output already exists; choose a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="")


def main(argv=None):
    parser = argparse.ArgumentParser(description="中文学术保真编辑本地工具（不含模型调用）")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "scan", "build-bundle", "review-request", "bind-review", "check-review", "apply", "export"):
        p = sub.add_parser(command)
        p.add_argument("--input", required=True)
        if command != "export":
            p.add_argument("--output", required=True)
        if command == "prepare":
            p.add_argument("--mode", choices=("diagnose", "conservative", "standard"), default="standard")
            p.add_argument("--genre", choices=("auto", "paper", "grant", "review", "report"), default="auto")
        if command == "build-bundle":
            p.add_argument("--edits", required=True)
        if command in ("review-request", "bind-review", "check-review"):
            p.add_argument("--patches", required=True)
        if command == "review-request":
            p.add_argument("--format", choices=("full", "compact"), default="full")
        if command in ("bind-review", "check-review"):
            p.add_argument("--review", required=True)
        if command == "apply":
            p.add_argument("--patches", required=True)
            p.add_argument("--review")
            p.add_argument("--repair-patches")
            p.add_argument("--repair-review")
            p.add_argument("--coherence-review")
            p.add_argument("--output-dir")
        if command == "export":
            p.add_argument("--result", required=True)
            p.add_argument("--output-dir", required=True)
    check = sub.add_parser("check")
    check.add_argument("--before", required=True)
    check.add_argument("--after", required=True)
    check.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            value = prepare_path(args.input, args.mode, args.genre)
        elif args.command == "scan":
            value = scan_document(document_from_path(args.input))
        elif args.command == "build-bundle":
            value = build_bundle(document_from_path(args.input), read_json(args.edits))
        elif args.command == "review-request":
            value = build_review_request(document_from_path(args.input), read_json(args.patches), args.format)
        elif args.command == "bind-review":
            value = bind_review(document_from_path(args.input), read_json(args.patches), read_json(args.review))
        elif args.command == "check-review":
            value = check_review(document_from_path(args.input), read_json(args.patches), read_json(args.review))
        elif args.command == "check":
            before, after = document_from_path(args.before), document_from_path(args.after)
            value = mechanical_check(before.text, after.text, before)
            value["status"] = "mechanical_pass_only" if value["status"] == "pass" else "mechanical_fail"
        elif args.command == "apply":
            doc = document_from_path(args.input)
            get = lambda path: read_json(path) if path else None
            final, report = apply_bundle(doc, get(args.patches), get(args.review),
                                        get(args.repair_patches), get(args.repair_review), get(args.coherence_review))
            value = result_envelope(doc, final, report)
            if args.output_dir:
                value["files"] = export_result(doc, final, report, args.output_dir)
        elif args.command == "export":
            doc, result = document_from_path(args.input), read_json(args.result)
            final = result.get("final_text")
            if not isinstance(final, str) or result.get("original_hash") != doc.hash or result.get("final_hash") != text_hash(final):
                raise InputError("Result envelope hash mismatch")
            files = export_result(doc, final, result["report"], args.output_dir)
            print(json.dumps({"files": files, "status": result["report"]["status"]}, ensure_ascii=False))
            return 0
        write_json(args.output, value)
        status = value.get("report", value).get("status", "prepared")
        print(json.dumps({"status": status, "output": str(Path(args.output).resolve())}, ensure_ascii=False))
        return 2 if status in {"execution_failed", "mechanical_fail"} else 0
    except (InputError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "execution_failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
