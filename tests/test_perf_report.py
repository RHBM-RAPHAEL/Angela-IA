"""Relatório de desempenho sem exibir conteúdo privado."""
import json
import tempfile
import unittest
from pathlib import Path

from angela.perf_report import summarize, percentile


class PerfReportTests(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([100, 150, 200, 300], .5), 150)
        self.assertEqual(percentile([100, 150, 200, 300], .95), 300)

    def test_filters_non_performance_and_sensitive_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "metrics.jsonl"
            items = [
                {"event": "command_received", "data": {"transcript": "Minha senha e secreta"}},
                {"event": "perf_metric", "data": {"phase": "tts_first_audio", "duration_ms": 100, "status": "ok"}},
                {"event": "perf_metric", "data": {"phase": "tts_first_audio", "duration_ms": 200, "status": "timeout"}},
                {"event": "perf_metric", "data": {"phase": "malicious", "duration_ms": 3, "status": "ok"}},
            ]
            path.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
            result = summarize(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 2)
        self.assertEqual(result[0]["p50_ms"], 150)
        self.assertEqual(result[0]["errors"], 1)
        self.assertNotIn("senha", str(result))


if __name__ == "__main__":
    unittest.main()
