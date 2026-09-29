"""Behavioural tests use isolated databases and synthetic records only."""
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from pipeline.core import COLUMNS, DEFAULT_CONTRACT, connect, digest, generate, ingest, report, trace

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "product.db"
        self.source = self.root / "input.csv"
        self.row = ["SYN-PAY-00001", "SYN-POL-001", "2026-01-15", "100.25", "EUR"]

    def write(self, rows, header=COLUMNS, name="input.csv"):
        p = self.root / name
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        return p

    def test_demo_publishes_ten_and_quarantines_two(self):
        generate(self.source)
        result = ingest(self.source, self.db)
        self.assertEqual((result["status"], result["inserted_rows"], result["invalid_rows"]), ("PUBLISHED", 10, 2))
        evidence = report(self.db)
        self.assertEqual(evidence["metrics"], [{"paid_date": "2026-01-15", "currency": "EUR", "payment_count": 10, "total_amount_cents": 550000}])
        self.assertEqual(len(evidence["quarantine"]), 2)

    def test_exact_replay_does_not_duplicate(self):
        p = self.write([self.row])
        a, b = ingest(p, self.db), ingest(p, self.db)
        self.assertEqual(a["batch_id"], b["batch_id"])
        self.assertTrue(b["replayed"])
        self.assertEqual(len(report(self.db)["batches"]), 1)

    def test_duplicate_across_different_files_is_counted_once(self):
        ingest(self.write([self.row]), self.db)
        second = ["SYN-PAY-00002", *self.row[1:]]
        r = ingest(self.write([self.row, second], name="next.csv"), self.db)
        self.assertEqual((r["inserted_rows"], r["duplicate_rows"]), (1, 1))
        self.assertEqual(report(self.db)["metrics"][0]["total_amount_cents"], 20050)

    def test_exact_duplicate_in_batch_is_not_double_counted(self):
        r = ingest(self.write([self.row, self.row]), self.db)
        self.assertEqual((r["inserted_rows"], r["duplicate_rows"]), (1, 1))

    def test_conflicting_id_does_not_replace_published_value(self):
        ingest(self.write([self.row]), self.db)
        conflict = [*self.row[:3], "999.00", "EUR"]
        r = ingest(self.write([conflict]), self.db)
        self.assertEqual(r["status"], "BLOCKED_QUALITY")
        self.assertEqual(report(self.db)["metrics"][0]["total_amount_cents"], 10025)
        self.assertIn("CONFLICTING_PUBLISHED_ID", report(self.db)["quarantine"][0]["reasons"])

    def test_conflicting_id_within_batch_quarantines_both(self):
        conflict = [*self.row[:3], "101.25", "EUR"]
        r = ingest(self.write([self.row, conflict]), self.db)
        self.assertEqual(r["invalid_rows"], 2)
        self.assertEqual(report(self.db)["metrics"], [])

    def test_schema_break_blocks_whole_batch(self):
        ingest(self.write([self.row]), self.db)
        r = ingest(self.write([self.row], header=[*COLUMNS[:-1], "currency_code"]), self.db)
        self.assertEqual(r["status"], "BLOCKED_SCHEMA")
        self.assertEqual(report(self.db)["metrics"][0]["payment_count"], 1)

    def test_quality_gate_blocks_otherwise_valid_rows_and_recovery_works(self):
        bad = ["SYN-PAY-00002", "UNKNOWN", *self.row[2:]]
        r = ingest(self.write([self.row, bad]), self.db)
        self.assertEqual(r["status"], "BLOCKED_QUALITY")
        self.assertEqual(len(report(self.db)["quarantine"]), 2)
        self.assertEqual(report(self.db)["metrics"], [])
        fixed = ["SYN-PAY-00002", *self.row[1:]]
        r = ingest(self.write([self.row, fixed]), self.db)
        self.assertEqual(r["status"], "PUBLISHED")
        self.assertEqual(len(report(self.db)["batches"]), 2)

    def test_invalid_dates_nonfinite_amounts_and_precision_are_rejected(self):
        for field, value in [(2, "2026-02-30"), (2, "20260115"), (3, "NaN"), (3, "1.001"), (3, "0"), (3, "1e4"), (4, "USD")]:
            with self.subTest(value=value):
                row = self.row.copy()
                row[field] = value
                self.assertEqual(ingest(self.write([row]), self.db)["status"], "BLOCKED_QUALITY")
        self.assertEqual(report(self.db)["metrics"], [])

    def test_contract_version_and_unknown_fields_fail_closed(self):
        c = json.loads(DEFAULT_CONTRACT.read_text())
        for change in [{"contract_version": "2.0.0"}, {"unexpected": True}, {"max_invalid_fraction": 1}]:
            with self.subTest(change=change):
                p = self.root / "contract.json"
                p.write_text(json.dumps({**c, **change}))
                with self.assertRaises(ValueError):
                    ingest(self.write([self.row]), self.db, p)

    def test_lineage_has_original_source_contract_and_transform(self):
        p = self.write([self.row])
        run = ingest(p, self.db)
        result = trace(self.db, "2026-01-15", "EUR")
        contributor = result["contributors"][0]
        self.assertEqual(contributor["source_sha"], digest(p.read_bytes()))
        self.assertEqual(contributor["contract_sha"], run["contract_sha"])
        self.assertEqual(contributor["transform_sha"], run["transform_sha"])
        self.assertEqual(contributor["source_row"], 2)
        self.assertEqual(result["total_amount_cents"], 10025)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT source_bytes FROM batches").fetchone()[0], p.read_bytes())

    def test_failure_mid_transaction_rolls_back(self):
        db = connect(self.db)
        db.execute("""CREATE TRIGGER simulate_failure BEFORE INSERT ON observations
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
        db.close()
        with self.assertRaises(sqlite3.IntegrityError):
            ingest(self.write([self.row]), self.db)
        self.assertEqual(report(self.db)["batches"], [])
        self.assertEqual(report(self.db)["metrics"], [])

    def test_concurrent_replay_is_serialized(self):
        p = self.write([self.row])
        db = connect(self.db)
        db.close()
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: ingest(p, self.db), range(2)))
        self.assertEqual(sorted(r["replayed"] for r in results), [False, True])
        self.assertEqual(report(self.db)["metrics"][0]["payment_count"], 1)

    def test_empty_and_malformed_batches_are_blocked(self):
        self.assertEqual(ingest(self.write([]), self.db)["status"], "BLOCKED_SCHEMA")
        self.assertEqual(ingest(self.write([self.row[:-1]]), self.db)["status"], "BLOCKED_SCHEMA")

    def test_cli_blocked_exit_code_and_persisted_decision(self):
        p = self.write([self.row], header=["unexpected", *COLUMNS[1:]])
        completed = subprocess.run([sys.executable, "-m", "pipeline", "run", str(p), "--database", str(self.db)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "BLOCKED_SCHEMA")
        self.assertEqual(len(report(self.db)["batches"]), 1)

if __name__ == "__main__":
    unittest.main()
