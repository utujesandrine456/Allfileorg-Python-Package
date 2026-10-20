"""
Unit and integration tests for fileorg.
"""

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from fileorg import (
    FileOrganizer,
    DEFAULT_CATEGORIES,
    build_extension_map,
    load_rules_from_file,
    organize_directory,
    undo_organization,
)
from fileorg.cli import main as cli_main


class TestRules(unittest.TestCase):
    def test_default_categories(self):
        ext_map = build_extension_map()
        self.assertEqual(ext_map[".docx"], "Documents")
        self.assertEqual(ext_map[".doc"], "Documents")
        self.assertEqual(ext_map[".pdf"], "PDFs")
        self.assertEqual(ext_map[".png"], "Images")
        self.assertEqual(ext_map[".jpg"], "Images")
        self.assertEqual(ext_map[".xlsx"], "Spreadsheets")
        self.assertEqual(ext_map[".csv"], "Spreadsheets")
        self.assertEqual(ext_map[".mp4"], "Videos")
        self.assertEqual(ext_map[".mp3"], "Audio")
        self.assertEqual(ext_map[".zip"], "Archives")
        self.assertEqual(ext_map[".py"], "Code")

    def test_custom_rule_loading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom_rules.json"
            config_file.write_text(json.dumps({
                "CustomDocs": [".myext", ".notes"]
            }), encoding="utf-8")

            rules = load_rules_from_file(config_file)
            self.assertIn("CustomDocs", rules)
            ext_map = build_extension_map(rules)
            self.assertEqual(ext_map[".myext"], "CustomDocs")


class TestFileOrganizer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = Path(self.test_dir) / "source"
        self.src_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_sample_files(self) -> list[Path]:
        sample_filenames = [
            "report.docx",
            "resume.pdf",
            "photo.png",
            "data.xlsx",
            "archive.zip",
            "script.py",
            "notes.txt",
            "song.mp3",
            "movie.mp4",
            "unknown.randomext",
        ]
        created = []
        for name in sample_filenames:
            f = self.src_dir / name
            f.write_text(f"content of {name}", encoding="utf-8")
            created.append(f)
        return created

    def test_basic_organization(self):
        self._create_sample_files()
        organizer = FileOrganizer(source_dir=self.src_dir)
        summary = organizer.organize()

        self.assertEqual(summary.total_files_scanned, 10)
        self.assertEqual(summary.total_moved, 10)
        self.assertEqual(summary.total_errors, 0)

        # Check organized structure
        self.assertTrue((self.src_dir / "Documents" / "report.docx").exists())
        self.assertTrue((self.src_dir / "Documents" / "notes.txt").exists())
        self.assertTrue((self.src_dir / "PDFs" / "resume.pdf").exists())
        self.assertTrue((self.src_dir / "Images" / "photo.png").exists())
        self.assertTrue((self.src_dir / "Spreadsheets" / "data.xlsx").exists())
        self.assertTrue((self.src_dir / "Archives" / "archive.zip").exists())
        self.assertTrue((self.src_dir / "Code" / "script.py").exists())
        self.assertTrue((self.src_dir / "Audio" / "song.mp3").exists())
        self.assertTrue((self.src_dir / "Videos" / "movie.mp4").exists())
        self.assertTrue((self.src_dir / "Others" / "unknown.randomext").exists())

    def test_dry_run(self):
        self._create_sample_files()
        organizer = FileOrganizer(source_dir=self.src_dir, dry_run=True)
        summary = organizer.organize()

        self.assertEqual(summary.total_files_scanned, 10)
        self.assertEqual(summary.total_moved, 10)

        # In dry run, files must remain in their original place
        self.assertTrue((self.src_dir / "report.docx").exists())
        self.assertFalse((self.src_dir / "Documents" / "report.docx").exists())

    def test_conflict_rename(self):
        # Create an existing file in target category folder
        doc_dir = self.src_dir / "Documents"
        doc_dir.mkdir()
        (doc_dir / "report.docx").write_text("existing", encoding="utf-8")

        # Create new file in source with same name
        (self.src_dir / "report.docx").write_text("new content", encoding="utf-8")

        organizer = FileOrganizer(source_dir=self.src_dir, conflict_strategy="rename")
        summary = organizer.organize()

        self.assertTrue((doc_dir / "report.docx").exists())
        self.assertTrue((doc_dir / "report (1).docx").exists())
        self.assertEqual((doc_dir / "report (1).docx").read_text(encoding="utf-8"), "new content")

    def test_conflict_skip(self):
        doc_dir = self.src_dir / "Documents"
        doc_dir.mkdir()
        (doc_dir / "report.docx").write_text("existing", encoding="utf-8")

        (self.src_dir / "report.docx").write_text("new content", encoding="utf-8")

        organizer = FileOrganizer(source_dir=self.src_dir, conflict_strategy="skip")
        summary = organizer.organize()

        self.assertEqual(summary.total_skipped, 1)
        self.assertTrue((self.src_dir / "report.docx").exists())
        self.assertEqual((doc_dir / "report.docx").read_text(encoding="utf-8"), "existing")

    def test_undo(self):
        self._create_sample_files()
        organizer = FileOrganizer(source_dir=self.src_dir)
        organizer.organize()

        self.assertTrue((self.src_dir / "Documents" / "report.docx").exists())

        # Revert
        reverted, failed, errors = FileOrganizer.undo(self.src_dir)
        self.assertEqual(reverted, 10)
        self.assertEqual(failed, 0)

        # Files should be back in src_dir root
        self.assertTrue((self.src_dir / "report.docx").exists())
        self.assertTrue((self.src_dir / "resume.pdf").exists())
        # Empty category directories should be cleaned up
        self.assertFalse((self.src_dir / "Documents").exists())

    def test_recursive_organization(self):
        sub = self.src_dir / "nested" / "folder"
        sub.mkdir(parents=True)
        (sub / "nested_doc.docx").write_text("nested doc", encoding="utf-8")

        organizer = FileOrganizer(source_dir=self.src_dir, recursive=True)
        summary = organizer.organize()

        self.assertEqual(summary.total_moved, 1)
        self.assertTrue((self.src_dir / "Documents" / "nested_doc.docx").exists())

    def test_cli_execution(self):
        self._create_sample_files()
        exit_code = cli_main([str(self.src_dir), "--quiet"])
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.src_dir / "Documents" / "report.docx").exists())

        # Test CLI undo
        exit_code_undo = cli_main([str(self.src_dir), "--undo", "--quiet"])
        self.assertEqual(exit_code_undo, 0)
        self.assertTrue((self.src_dir / "report.docx").exists())


if __name__ == "__main__":
    unittest.main()
