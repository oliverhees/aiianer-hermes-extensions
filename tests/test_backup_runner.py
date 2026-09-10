from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("backup_runner", ROOT / "extensions/aiianer-backup/backup_runner.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class BackupRunnerTest(unittest.TestCase):
    def test_rejects_home_and_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"; home.mkdir()
            with self.assertRaisesRegex(ValueError, "TARGET_INSIDE_HERMES_HOME"):
                MOD.validate_target(str(home / "backups"), home)
            with self.assertRaisesRegex(ValueError, "TARGET_TRAVERSAL"):
                MOD.validate_target(str(Path(d) / ".." / "outside"), home, create=False)

    def test_retention_only_removes_own_archives_and_keeps_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            for i in range(3):
                p = target / f"aiianer-backup-2024010{i}T000000Z.zip"; p.write_bytes(b"x"); p.touch()
            foreign = target / "other.zip"; foreign.write_bytes(b"x")
            removed = MOD.apply_retention(target, 2)
            self.assertEqual(len(removed), 1)
            self.assertTrue(foreign.exists())
            self.assertEqual(len(list(target.glob("aiianer-backup-*.zip"))), 2)

    def test_archive_verification_rejects_invalid_zip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.zip"; p.write_bytes(b"not zip")
            with self.assertRaisesRegex(ValueError, "ARCHIVE_MISSING_OR_INVALID"):
                MOD.verify_archive(p)

if __name__ == "__main__": unittest.main()
