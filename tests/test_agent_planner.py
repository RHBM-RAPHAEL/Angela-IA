import unittest
from unittest.mock import Mock, patch
from angela.agent_planner import parse_plan, execute_plan, local_fallback_plan
from angela.windows_apps import InstalledApp


class PlannerTests(unittest.TestCase):
    def test_utterance_opera_without_gx(self):
        self.assertEqual(local_fallback_plan('abra o youtube pelo opera'), [{'tool': 'open_website', 'target': 'youtube', 'browser': 'Opera GX'}])

    def test_real_transcript_fallback(self):
        plan = local_fallback_plan('eu quero ver vídeo no youtube abra pelo golpe')
        self.assertEqual(plan, [{'tool': 'open_website', 'target': 'youtube', 'browser': 'Opera GX'}])
        self.assertIsNone(local_fallback_plan('como funciona o youtube?'))

    def test_plan_validated(self):
        self.assertEqual(parse_plan({"steps": [{"tool": "open_website", "target": "youtube", "browser": "Opera GX"}]})[0]["target"], "youtube")
        self.assertIsNone(parse_plan({"steps": [{"tool": "run_shell", "target": "whatever"}]}))
        self.assertIsNone(parse_plan({"steps": [{"tool": "open_app", "target": "x"}] * 4}))
        self.assertEqual(parse_plan({"steps": []}), [])

    def test_unknown_site_not_opened(self):
        catalog = Mock()
        windows = Mock(catalog=catalog)
        opener = Mock()
        response = execute_plan([{"tool": "open_website", "target": "unknown", "browser": ""}], windows, startfile=opener)
        self.assertIn("não está identificado", response)
        opener.assert_not_called()

    def test_youtube_default(self):
        windows = Mock()
        opener = Mock()
        response = execute_plan([{"tool": "open_website", "target": "youtube", "browser": ""}], windows, startfile=opener)
        self.assertIn("Solicitei", response)
        opener.assert_called_once_with("https://www.youtube.com")

    def test_youtube_opera_executable(self):
        windows = Mock()
        windows.catalog.list_apps.return_value = [InstalledApp("Opera GX", "exe", r"C:\Browser\opera.exe")]
        with patch("subprocess.Popen") as launcher:
            response = execute_plan([{"tool": "open_website", "target": "youtube", "browser": "Opera GX"}], windows)
        self.assertIn("Opera GX", response)
        launcher.assert_called_once_with([r"C:\Browser\opera.exe", "https://www.youtube.com"], shell=False)


if __name__ == "__main__":
    unittest.main()
