"""Offline distribution and installation tests; no model or efficacy evidence."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_release import build_release
from install_skill import install
from public_scope import SKILL_PREFIX, public_paths, runtime_files, version
from verify_public import audit


def copy_public(destination):
    for name in public_paths():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)


class PublicDistribution(unittest.TestCase):
    def test_same_sources_produce_identical_archive_and_hash_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            first = build_release(Path(temp) / "first")
            second = build_release(Path(temp) / "second")
            for key in ("archive", "manifest", "sha256sums"):
                self.assertEqual(Path(first[key]).read_bytes(), Path(second[key]).read_bytes())
            with zipfile.ZipFile(first["archive"]) as bundle:
                expected = runtime_files()
                self.assertEqual(set(bundle.namelist()), {"academic-deai-zh/" + p for p in expected})
                for name, data in expected.items():
                    self.assertEqual(bundle.read("academic-deai-zh/" + name), data)

    def test_extra_research_and_private_files_do_not_enter_release(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "独立 源码"
            copy_public(source)
            for name in ("Codex/work/private.json", "corpus/article.txt", ".env"):
                extra = source / name
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text("PRIVATE_SYNTHETIC_SENTINEL", encoding="utf-8")
            result = build_release(Path(temp) / "out", source)
            with zipfile.ZipFile(result["archive"]) as bundle:
                self.assertFalse(any(b"PRIVATE_SYNTHETIC_SENTINEL" in bundle.read(p) for p in bundle.namelist()))
            self.assertTrue(audit(source)["passed"])

    def test_forbidden_manifest_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            copy_public(source)
            manifest = source / "public-files.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["files"] = sorted(data["files"] + ["corpus/private.txt"])
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_release(source / "out", source)
            self.assertFalse((source / "out").exists())

    def test_mismatched_runtime_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            copy_public(source)
            core = source / SKILL_PREFIX / "scripts/deai_core.py"
            core.write_text(core.read_text(encoding="utf-8").replace(
                'VERSION = "' + version() + '"', 'VERSION = "9.9.9"'), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_release(source / "out", source)
            self.assertFalse((source / "out").exists())

    def test_existing_release_assets_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = build_release(target)
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with self.assertRaises(ValueError):
                build_release(target)
            self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
            self.assertTrue(Path(result["archive"]).is_file())


class LocalInstallation(unittest.TestCase):
    def test_fresh_install_matches_packaged_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "中文 安装" / "academic-deai-zh"
            result = install(destination)
            self.assertEqual(result["files"], len(runtime_files()))
            for name, data in runtime_files().items():
                self.assertEqual((destination / name).read_bytes(), data)

    def test_existing_nonempty_or_empty_installation_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            for populated in (False, True):
                destination = Path(temp) / str(populated)
                destination.mkdir()
                if populated:
                    (destination / "original.txt").write_bytes(b"ORIGINAL")
                before = {p.name: p.read_bytes() for p in destination.iterdir()}
                with self.assertRaises(FileExistsError):
                    install(destination)
                self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, before)

    def test_installer_cli_handles_unicode_path_without_global_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "独立 中文路径" / "academic-deai-zh"
            result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools/install_skill.py"),
                                     "--dest", str(target)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / "SKILL.md").read_bytes(), runtime_files()["SKILL.md"])


class ExtractedCLI(unittest.TestCase):
    def test_archive_runs_outside_repo_preserves_bom_newlines_and_refuses_bad_number(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "中文 空格验证"
            folder.mkdir()
            result = build_release(Path(temp) / "release")
            with zipfile.ZipFile(result["archive"]) as bundle:
                bundle.extractall(folder)
            script = folder / "academic-deai-zh/scripts/deai.py"
            original = b"\xef\xbb\xbf" + "# 方法\r\n\r\n甲组18例，乙组24例。\n\n尚未完成分析。\r\n".encode("utf-8")
            source = folder / "原件.md"
            source.write_bytes(original)

            def run(*args, expected=0):
                call = subprocess.run([sys.executable, "-X", "utf8", str(script), *args], cwd=folder,
                                      capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(call.returncode, expected, call.stderr or call.stdout)

            run("prepare", "--input", "原件.md", "--output", "task.json")
            task = json.loads((folder / "task.json").read_text(encoding="utf-8"))
            proposal = {"original_hash": task["original_hash"], "edits": []}
            (folder / "edits.json").write_text(json.dumps(proposal), encoding="utf-8")
            run("build-bundle", "--input", "原件.md", "--edits", "edits.json", "--output", "patches.json")
            run("review-request", "--input", "原件.md", "--patches", "patches.json", "--format", "compact", "--output", "request.json")
            run("apply", "--input", "原件.md", "--patches", "patches.json", "--output", "result.json")
            run("export", "--input", "原件.md", "--result", "result.json", "--output-dir", "delivery")
            exported = folder / "delivery/原件.edited.md"
            self.assertEqual(exported.read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            run("check", "--before", "原件.md", "--after", "delivery/原件.edited.md", "--output", "check.json")
            self.assertEqual(json.loads((folder / "result.json").read_text(encoding="utf-8"))["report"]["status"], "no_op")
            run("export", "--input", "原件.md", "--result", "result.json", "--output-dir", "delivery", expected=2)
            numeric_paragraph = next(p for p in task["paragraphs"] if "甲组18例" in p["text"])
            proposal["edits"] = [{"paragraph_id": numeric_paragraph["id"], "new": "甲组19例，乙组24例。", "reason": "SIMULATED invalid number"}]
            (folder / "bad-edits.json").write_text(json.dumps(proposal), encoding="utf-8")
            run("build-bundle", "--input", "原件.md", "--edits", "bad-edits.json", "--output", "bad-patches.json", expected=2)
            self.assertFalse((folder / "bad-patches.json").exists())
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(exported.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
