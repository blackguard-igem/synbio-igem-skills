#!/usr/bin/env python3
"""Self-contained behavioral checks; fixtures are teaching simulations only."""

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

SCRIPT = Path(__file__).with_name("kb.py")
WORK_DIR = None


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kb-check-", dir=WORK_DIR)
        self.root = Path(self.temp.name)
        self.db = self.root / "demo.sqlite"
        self.note = self.root / "note.md"
        self.note.write_text("# 教学模拟\n课堂 证据\nAlpha signal\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, project="team-a", expected=0, db=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(db or self.db),
             "--project", project, *map(str, args)],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return json.loads(result.stdout) if expected == 0 else result

    def add(self, **kwargs):
        return self.run_cli("add", self.note, "--source", "teaching:note",
                            "--locator", "教学模拟第一节", **kwargs)

    def test_add_list_get_and_source_lines(self):
        added = self.add()
        self.assertEqual(added["action"], "added")
        doc = added["document"]
        self.assertEqual(doc["state"], "READY")
        listing = self.run_cli("list")
        self.assertEqual(listing["total"], 1)
        full = self.run_cli("get", doc["id"])["document"]
        self.assertEqual(full["source"], "teaching:note")
        self.assertEqual(full["locator"], "教学模拟第一节")
        self.assertEqual(full["lines"][1], {"line": 2, "text": "课堂 证据"})

    def test_duplicate_and_update_replace_searchable_content(self):
        first = self.add()["document"]
        unchanged = self.add()
        self.assertEqual(unchanged["action"], "unchanged")
        self.assertEqual(unchanged["document"]["version"], 1)
        self.note.write_text("# 教学模拟\n替代材料 Beta\n", encoding="utf-8")
        updated = self.add()
        self.assertEqual(updated["action"], "updated")
        self.assertEqual(updated["document"]["version"], 2)
        self.assertEqual(updated["document"]["id"], first["id"])
        self.assertEqual(self.run_cli("list")["total"], 1)
        self.assertEqual(self.run_cli("search", "Alpha")["total"], 0)
        self.assertEqual(self.run_cli("search", "Beta")["total"], 1)

    def test_project_isolation_for_list_search_get_and_update(self):
        first = self.add()["document"]
        self.note.write_text("# 教学模拟\nTEAM_B_ONLY\n", encoding="utf-8")
        second = self.add(project="team-b")["document"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.run_cli("list")["total"], 1)
        self.assertEqual(self.run_cli("search", "TEAM_B_ONLY")["total"], 0)
        self.assertEqual(self.run_cli("search", "Alpha", project="team-b")["total"], 0)
        self.assertEqual(self.run_cli("list", project="unknown")["total"], 0)
        self.run_cli("get", second["id"], expected=2)
        original = self.run_cli("get", first["id"])["document"]
        self.assertEqual(original["version"], 1)
        self.assertEqual(original["lines"][2]["text"], "Alpha signal")

    def test_keyword_and_casefold_and_no_semantic_claim(self):
        self.add()
        hit = self.run_cli("search", "课堂 ALPHA")
        self.assertEqual(hit["total"], 1)
        self.assertEqual([line["line"] for line in hit["documents"][0]["hits"]], [2, 3])
        self.assertEqual(self.run_cli("search", "课堂 absent")["total"], 0)
        self.assertEqual(self.run_cli("search", "teacher")["total"], 0)
        self.assertEqual(self.run_cli("search", "teaching:note")["total"], 0)

    def test_same_content_different_sources_preserves_provenance(self):
        self.add()
        second = self.run_cli("add", self.note, "--source", "teaching:second")
        self.assertEqual(second["action"], "added")
        self.assertEqual(self.run_cli("list")["total"], 2)

    def test_missing_read_database_does_not_create_it(self):
        self.run_cli("list", expected=2)
        self.assertFalse(self.db.exists())

    def test_input_rejection_does_not_create_database(self):
        for filename, data in [
            ("empty.md", b" \n"), ("binary.txt", b"a\x00b"),
            ("invalid.txt", b"\xff\xfe"), ("raw.pdf", b"%PDF-demo"),
        ]:
            bad = self.root / filename
            bad.write_bytes(data)
            self.run_cli("add", bad, expected=2)
            self.assertFalse(self.db.exists())

    def test_size_limit(self):
        oversized = self.root / "large.txt"
        oversized.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
        self.run_cli("add", oversized, expected=2)
        self.assertFalse(self.db.exists())

    def test_bom_and_newline_normalization(self):
        self.note.write_bytes(b"\xef\xbb\xbfline1\r\nline2\r")
        first = self.add()["document"]
        full = self.run_cli("get", first["id"])["document"]
        self.assertEqual(full["lines"], [{"line": 1, "text": "line1"},
                                          {"line": 2, "text": "line2"}])
        self.note.write_bytes(b"line1\nline2\n")
        self.assertEqual(self.add()["action"], "unchanged")

    def test_project_parameter_required_and_not_sql(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(self.db), "list"],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.add()
        self.assertEqual(self.run_cli("list", project="' OR 1=1 --")["total"], 0)

    def test_wrong_schema_database_not_modified(self):
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute("CREATE TABLE unrelated (value TEXT)")
                conn.execute("INSERT INTO unrelated VALUES ('teaching simulation')")
        self.run_cli("add", self.note, expected=2)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT value FROM unrelated").fetchone()[0],
                             "teaching simulation")
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            self.assertEqual(tables, [("unrelated",)])

    def test_limits_and_pagination(self):
        self.add()
        self.run_cli("add", self.note, "--source", "teaching:second")
        self.assertEqual(len(self.run_cli("list", "--limit", 1)["documents"]), 1)
        self.assertEqual(len(self.run_cli("list", "--offset", 1)["documents"]), 1)
        self.assertEqual(len(self.run_cli("search", "Alpha", "--limit", 1)["documents"]), 1)
        self.run_cli("list", "--offset", -1, expected=2)
        self.run_cli("search", "Alpha", "--limit", 0, expected=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True,
                        help="Temporary test subdirectories are created only here")
    args = parser.parse_args()
    WORK_DIR = Path(args.work_dir).expanduser().resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(KnowledgeBaseTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
