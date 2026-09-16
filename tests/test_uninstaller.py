import unittest
from backend.app_manager import AppManager, InstalledApp
from backend.leftover_scanner import LeftoverScanner, LeftoverItem

class TestAppManager(unittest.TestCase):
    def setUp(self):
        self.manager = AppManager()

    def test_discovery_returns_apps(self):
        apps = self.manager.refresh()
        self.assertIsInstance(apps, list)
        self.assertGreater(len(apps), 0, "Should discover installed applications from Windows Registry")

    def test_installed_app_attributes(self):
        apps = self.manager.refresh()
        sample = apps[0]
        self.assertIsInstance(sample.name, str)
        self.assertTrue(len(sample.name) > 0)
        self.assertIsInstance(sample.size_kb, int)

    def test_msiexec_command_normalization(self):
        # MsiExec install /I should be converted to /X for uninstallation
        app = InstalledApp(
            name="Test MSI App",
            uninstall_string="MsiExec.exe /I{12345678-ABCD-1234-ABCD-1234567890AB}"
        )
        cmd = app.get_effective_uninstall_command(silent=False)
        self.assertIn("/x", cmd.lower())
        self.assertNotIn("/i{", cmd.lower())

        # Test silent flag adds /qn
        silent_cmd = app.get_effective_uninstall_command(silent=True)
        self.assertIn("/qn", silent_cmd.lower())

    def test_clean_icon_path_with_quotes_and_index(self):
        # Even with quotes and comma index, should clean and resolve existing file
        explorer_path = r"C:\Windows\explorer.exe"
        app = InstalledApp(
            name="Explorer Test",
            icon_path=f'"{explorer_path}",0'
        )
        cleaned = app.clean_icon_path()
        self.assertEqual(cleaned, explorer_path)

    def test_shortcut_index_loaded(self):
        # AppManager should index Start Menu shortcuts
        self.assertIsInstance(self.manager.shortcuts, list)
        self.assertGreater(len(self.manager.shortcuts), 0)

    def test_resolved_icon_discovery(self):
        # Check that high percentage of installed apps have resolved icons
        apps = self.manager.refresh()
        resolved = [a for a in apps if a.resolved_icon_path]
        # At least 85% of real installed apps on system should resolve an icon
        self.assertGreater(len(resolved) / len(apps), 0.85)

class TestLeftoverScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = LeftoverScanner()

    def test_token_generation(self):
        tokens = self.scanner._generate_search_tokens("Internet Download Manager", "Tonec Inc.")
        self.assertIn("idm", tokens)
        self.assertIn("internet download manager", tokens)

    def test_token_generation_clean_version(self):
        tokens = self.scanner._generate_search_tokens("Adobe Photoshop 2025 v26.9 x64", "Adobe Inc.")
        self.assertTrue(any("photoshop" in t for t in tokens))

    def test_subpath_deduplication(self):
        # If parent folder is included, child subfolder should be excluded to avoid redundant delete attempts
        items = [
            LeftoverItem(item_type="FOLDER", path=r"C:\AppData\Roaming\TestApp", name="TestApp"),
            LeftoverItem(item_type="FOLDER", path=r"C:\AppData\Roaming\TestApp\Cache", name="Cache"),
            LeftoverItem(item_type="FILE", path=r"C:\AppData\Roaming\TestApp\config.json", name="config.json"),
            LeftoverItem(item_type="REGISTRY_KEY", path=r"Software\TestApp", name="TestApp")
        ]
        deduped = self.scanner._deduplicate_subpaths(items)
        paths = [it.path for it in deduped]
        self.assertIn(r"C:\AppData\Roaming\TestApp", paths)
        self.assertNotIn(r"C:\AppData\Roaming\TestApp\Cache", paths)
        self.assertNotIn(r"C:\AppData\Roaming\TestApp\config.json", paths)
        self.assertIn(r"Software\TestApp", paths)

if __name__ == "__main__":
    unittest.main()
