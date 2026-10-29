import unittest
from unittest.mock import patch
from angela.windows_controller import WindowsController, command_kind
from angela.windows_windows import WindowInfo


class NaturalCloseTests(unittest.TestCase):
    def test_polite_close_interpretation(self):
        self.assertEqual(command_kind("bom dia Angela feche as configurações de som por favor"),
                         ("close_window", "configuracoes de som"))
        self.assertEqual(command_kind("feche as configurações"), ("close_window", "configuracoes"))

    def test_settings_window_close_requires_confirmation(self):
        item = WindowInfo(77, "Configurações")
        closed = []
        control = WindowsController(windows=lambda: [item], close=lambda x: closed.append(x) or True)
        with patch("angela.windows_controller.sys.platform", "win32"):
            response = control.process("bom dia feche as configurações de som por favor")
            self.assertIn("Confirmar fechamento?", response)
            self.assertEqual(closed, [])
            followup = control.process("sim")
            self.assertIn("Solicitei ao Windows", followup)
            self.assertEqual(closed, [item])


if __name__ == "__main__":
    unittest.main()
