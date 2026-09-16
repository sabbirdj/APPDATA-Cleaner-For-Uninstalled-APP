import os
import unittest
import tempfile
import shutil
from backend.everything_cli import EverythingCLI
from backend.registry_scanner import RegistryScanner
from backend.whitelist import WhitelistManager, BUILTIN_PROTECTED_FOLDERS
from backend.cleaner_engine import CleanerEngine
from backend.scanner_engine import ScannerEngine

class TestEverythingCLI(unittest.TestCase):
    def setUp(self):
        self.es = EverythingCLI()

    def test_detection(self):
        # We verified earlier es is installed via winget
        self.assertTrue(self.es.is_available)
        self.assertIsNotNone(self.es.cli_path)

    def test_query_installed_app(self):
        # Chrome is installed on the machine
        res = self.es.get_result_count("chrome.exe")
        self.assertGreater(res, 0)

    def test_query_non_existent(self):
        res = self.es.get_result_count("DefinitelyNonExistentApp99999XYZ.exe")
        self.assertEqual(res, 0)

class TestRegistryScanner(unittest.TestCase):
    def setUp(self):
        self.reg = RegistryScanner()

    def test_registry_loaded(self):
        self.assertGreater(len(self.reg.installed_apps), 0)

    def test_known_registry_match(self):
        # Test against something that is likely in registry
        found, name = self.reg.check_app_in_registry("NVIDIA", [])
        # If NVIDIA is installed, should find it
        self.assertTrue(found)
        self.assertIsNotNone(name)

    def test_idm_acronym_match(self):
        # IDM is installed on the user's system as Internet Download Manager
        found, name = self.reg.check_app_in_registry("IDM", [])
        self.assertTrue(found)
        self.assertEqual(name, "Internet Download Manager")

class TestWhitelistManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.mktemp(suffix=".json")
        self.wm = WhitelistManager(self.temp_file)

    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def test_builtin_protection(self):
        self.assertTrue(self.wm.is_protected("Microsoft"))
        self.assertTrue(self.wm.is_protected("Windows"))
        self.assertTrue(self.wm.is_protected("Packages"))
        self.assertFalse(self.wm.is_protected("SomeRandomOrphanedApp"))

    def test_custom_whitelist(self):
        self.assertFalse(self.wm.is_protected("MyCustomApp"))
        self.wm.add("MyCustomApp")
        self.assertTrue(self.wm.is_protected("MyCustomApp"))
        self.assertTrue(self.wm.is_protected("mycustomapp"))

        # Re-load from saved file
        wm2 = WhitelistManager(self.temp_file)
        self.assertTrue(wm2.is_protected("MyCustomApp"))

        self.wm.remove("MyCustomApp")
        self.assertFalse(self.wm.is_protected("MyCustomApp"))

class TestCleanerEngine(unittest.TestCase):
    def test_recycle_bin_deletion(self):
        temp_dir = tempfile.mkdtemp(prefix="orphan_cleaner_test_")
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello world")

        items = [{"name": "test_folder", "path": temp_dir, "size": 11}]
        res = CleanerEngine.delete_items(items, use_recycle_bin=True)
        self.assertEqual(res["success_count"], 1)
        self.assertEqual(res["failed_count"], 0)
        self.assertFalse(os.path.exists(temp_dir))

class TestScannerEngineStreaming(unittest.TestCase):
    def test_streaming_callback(self):
        temp_root = tempfile.mkdtemp(prefix="test_appdata_")
        dummy_folder = os.path.join(temp_root, "TestSampleApp")
        os.makedirs(dummy_folder, exist_ok=True)
        with open(os.path.join(dummy_folder, "data.txt"), "w") as f:
            f.write("abc")

        scanner = ScannerEngine()
        received_items = []

        orig_env = os.environ.get("APPDATA")
        try:
            os.environ["APPDATA"] = temp_root
            results = scanner.scan_roots(
                targets={"roaming": True, "local": False, "locallow": False, "programdata": False},
                item_callback=lambda it: received_items.append(it)
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(len(received_items), 1)
            self.assertEqual(received_items[0].name, "TestSampleApp")
        finally:
            if orig_env:
                os.environ["APPDATA"] = orig_env
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_windows_exclusion(self):
        temp_root = tempfile.mkdtemp(prefix="test_appdata_win_")
        for win_name in ["Microsoft", "WindowsHolographicDevices", "regid.1991-06.com.microsoft", "Package Cache"]:
            f = os.path.join(temp_root, win_name)
            os.makedirs(f, exist_ok=True)
            with open(os.path.join(f, "test.txt"), "w") as fp:
                fp.write("x")

        scanner = ScannerEngine()
        orig_env = os.environ.get("APPDATA")
        try:
            os.environ["APPDATA"] = temp_root
            # When exclude_windows=True (default), none of these should be in results
            results_excluded = scanner.scan_roots(
                targets={"roaming": True, "local": False, "locallow": False, "programdata": False},
                exclude_windows=True
            )
            self.assertEqual(len(results_excluded), 0)

            # When exclude_windows=False, they should be included and protected
            results_included = scanner.scan_roots(
                targets={"roaming": True, "local": False, "locallow": False, "programdata": False},
                exclude_windows=False
            )
            self.assertEqual(len(results_included), 4)
            for item in results_included:
                self.assertEqual(item.status, "PROTECTED")
        finally:
            if orig_env:
                os.environ["APPDATA"] = orig_env
            shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
