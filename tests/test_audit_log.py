"""Persistence, correlation, masking and bounded files."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from angela import audit_log


class AuditLogTests(unittest.TestCase):
    def test_records_utf8_and_correlates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"ANGELA_AUDIT_PATH": str(path)}):
                trace = audit_log.begin_interaction()
                audit_log.record("heard", transcript="Abra o Zynix")
                row = json.loads(path.read_text(encoding="utf-8").strip())
                self.assertEqual(row["event"], "heard")
                self.assertEqual(row["trace_id"], trace)
                self.assertEqual(row["data"]["transcript"], "Abra o Zynix")

    def test_masks_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"ANGELA_AUDIT_PATH": str(path)}):
                audit_log.record("test", value="token=abc123", api_key="private")
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("abc123", content)
                self.assertNotIn("private", content)

    def test_rotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            with patch.dict(os.environ, {"ANGELA_AUDIT_PATH": str(path)}), patch.object(audit_log, "MAX_BYTES", 90):
                for i in range(12):
                    audit_log.record("test", value=str(i) * 20)
                self.assertTrue(path.exists())
                self.assertTrue(path.with_name(path.name + ".1").exists())
                self.assertFalse(path.with_name(path.name + ".5").exists())


if __name__ == "__main__":
    unittest.main()
