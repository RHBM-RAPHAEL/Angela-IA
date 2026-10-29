import unittest
from unittest.mock import Mock

from angela.windows_resources import resource_request, open_resource


class WindowsResourcesTests(unittest.TestCase):
    def test_settings(self):
        self.assertEqual(resource_request("Abra as configurações de som"), ("settings", "ms-settings:sound"))
        opener = Mock()
        result = open_resource(("settings", "ms-settings:sound"), opener=opener, platform="win32")
        opener.assert_called_once_with("ms-settings:sound")
        self.assertIn("Solicitei", result)

    def test_polite_natural_commands(self):
        examples = [
            'bom dia abre as configurações de som por favor',
            'Angela, abra as configurações de som por favor',
            'oi Angela abra as configurações de som',
            'pode abrir as configurações de som pra mim',
        ]
        for phrase in examples:
            with self.subTest(phrase=phrase):
                self.assertEqual(resource_request(phrase), ('settings', 'ms-settings:sound'))

    def test_explicit_file(self):
        self.assertEqual(resource_request(r"abra o arquivo D:\Temp\relatorio.pdf"),
                         ("file", r"D:\Temp\relatorio.pdf"))

    def test_does_not_intercept_project(self):
        self.assertIsNone(resource_request("abra o projeto Zynix no VS Code"))

    def test_rejects_scripts_and_executables(self):
        opener = Mock()
        for name in [r"C:\Temp\setup.exe", r"C:\Temp\build.ps1", r"C:\Temp\macro.bat"]:
            outcome = open_resource(("file", name), opener=opener, platform="win32")
            self.assertIn("segurança", outcome)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
