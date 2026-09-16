import os
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from backend.everything_cli import EverythingCLI
from backend.registry_scanner import RegistryScanner
from backend.whitelist import WhitelistManager

GENERIC_SUBFOLDER_NAMES = {
    'cache', 'caches', 'logs', 'log', 'temp', 'tmp', 'data', 'userdata', 'capture', 'captures',
    'model', 'models', 'playlist', 'playlists', 'config', 'configuration', 'settings', 'setting',
    'bin', 'lib', 'libs', 'default', 'profile', 'profiles', 'local', 'storage', 'backup', 'backups',
    'updates', 'update', 'plugins', 'plugin', 'addons', 'addon', 'extensions', 'extension',
    'resources', 'resource', 'assets', 'asset', 'download', 'downloads', 'shared', 'common', 'components',
    'python', 'node', 'java', 'ruby', 'go', 'env', 'venv', 'tools'
}

class AppDataItem:
    def __init__(self, name: str, path: str, root_type: str):
        self.name = name
        self.path = path
        self.root_type = root_type  # "Roaming", "Local", "LocalLow", "ProgramData"
        self.size = 0
        self.file_count = 0
        self.last_modified = ""
        self.status = "UNKNOWN"  # "ORPHANED", "INSTALLED", "PROTECTED"
        self.evidence: List[str] = []
        self.selected = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "root_type": self.root_type,
            "size": self.size,
            "file_count": self.file_count,
            "last_modified": self.last_modified,
            "status": self.status,
            "evidence": self.evidence,
            "selected": self.selected
        }

class ScannerEngine:
    def __init__(self, everything_cli: Optional[EverythingCLI] = None):
        self.everything_cli = everything_cli or EverythingCLI()
        self.registry_scanner = RegistryScanner()
        self.whitelist_manager = WhitelistManager()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel_scan(self):
        """Cancels an ongoing scan."""
        with self._lock:
            self._is_cancelled = True

    def calculate_dir_stats(self, folder_path: str) -> tuple[int, int, str]:
        """Calculates total size (bytes), file count, and latest modified date."""
        total_size = 0
        file_count = 0
        latest_mtime = 0.0

        try:
            latest_mtime = os.path.getmtime(folder_path)
        except Exception:
            pass

        try:
            for root, dirs, files in os.walk(folder_path):
                if self._is_cancelled:
                    break
                for f in files:
                    file_count += 1
                    fp = os.path.join(root, f)
                    try:
                        stat = os.stat(fp)
                        total_size += stat.st_size
                        if stat.st_mtime > latest_mtime:
                            latest_mtime = stat.st_mtime
                    except Exception:
                        continue
        except Exception:
            pass

        mod_str = ""
        if latest_mtime > 0:
            try:
                mod_str = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        return total_size, file_count, mod_str

    def inspect_subfolders(self, folder_path: str) -> List[str]:
        """Returns the first level of subfolder names inside a directory."""
        subs = []
        try:
            with os.scandir(folder_path) as it:
                for entry in it:
                    if entry.is_dir():
                        subs.append(entry.name)
        except Exception:
            pass
        return subs

    def scan_roots(
        self,
        targets: Dict[str, bool],
        progress_callback: Optional[Callable[[float, str, int], None]] = None,
        item_callback: Optional[Callable[[AppDataItem], None]] = None,
        exclude_windows: bool = True
    ) -> List[AppDataItem]:
        """
        Scans selected AppData root directories.
        targets dict keys: 'roaming', 'local', 'locallow', 'programdata'
        exclude_windows: When True, completely skips Windows and Microsoft OS folders.
        """
        self._is_cancelled = False
        # Refresh registry app index at the start of each scan
        self.registry_scanner.refresh()

        root_dirs = []
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        userprofile = os.environ.get("USERPROFILE")
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")

        if targets.get("roaming") and appdata and os.path.isdir(appdata):
            root_dirs.append(("Roaming", appdata))
        if targets.get("local") and localappdata and os.path.isdir(localappdata):
            root_dirs.append(("Local", localappdata))
        if targets.get("locallow") and userprofile:
            ll_path = os.path.join(userprofile, "AppData", "LocalLow")
            if os.path.isdir(ll_path):
                root_dirs.append(("LocalLow", ll_path))
        if targets.get("programdata") and programdata and os.path.isdir(programdata):
            root_dirs.append(("ProgramData", programdata))

        # First discover all top-level folders to scan
        folder_tasks = []
        for root_type, root_path in root_dirs:
            try:
                with os.scandir(root_path) as it:
                    for entry in it:
                        if entry.is_dir():
                            folder_tasks.append((root_type, entry.name, entry.path))
            except Exception:
                continue

        total_folders = len(folder_tasks)
        results = []

        for idx, (root_type, folder_name, folder_path) in enumerate(folder_tasks):
            if self._is_cancelled:
                break

            # If exclude_windows condition is enabled, completely skip Windows-related folders
            if exclude_windows and self.whitelist_manager.is_windows_related(folder_name, folder_path):
                continue

            progress_pct = (idx / total_folders) if total_folders > 0 else 1.0
            if progress_callback:
                progress_callback(progress_pct, folder_name, len(results))

            item = AppDataItem(name=folder_name, path=folder_path, root_type=root_type)

            # Step 1: Check Whitelist / System Protection
            if self.whitelist_manager.is_protected(folder_name, folder_path):
                item.status = "PROTECTED"
                item.evidence.append("Protected system component or whitelisted folder.")
                # We can still get quick size if accessible
                size, count, mod_date = self.calculate_dir_stats(folder_path)
                item.size = size
                item.file_count = count
                item.last_modified = mod_date
                results.append(item)
                if item_callback:
                    item_callback(item)
                continue

            # Get subfolders (useful for vendor folders like Daum/PotPlayer or Adobe/Illustrator)
            raw_subfolders = self.inspect_subfolders(folder_path)
            subfolders = [
                s for s in raw_subfolders 
                if s.lower() not in GENERIC_SUBFOLDER_NAMES and len(s) > 2
            ]

            # Step 2: Check Windows Registry Uninstall DB
            reg_found, reg_app_name = self.registry_scanner.check_app_in_registry(folder_name, subfolders)
            if reg_found:
                item.status = "INSTALLED"
                item.evidence.append(f"Verified via Windows Registry: '{reg_app_name}'")
                size, count, mod_date = self.calculate_dir_stats(folder_path)
                item.size = size
                item.file_count = count
                item.last_modified = mod_date
                results.append(item)
                if item_callback:
                    item_callback(item)
                continue

            # Step 3: Check Everything CLI
            es_installed, es_evidence = self.everything_cli.check_app_installed(folder_name, subfolders)
            if es_installed:
                item.status = "INSTALLED"
                item.evidence.extend(es_evidence)
            else:
                item.status = "ORPHANED"
                item.evidence.extend(es_evidence)
                # By default, orphaned items are selected for convenience
                item.selected = True

            size, count, mod_date = self.calculate_dir_stats(folder_path)
            item.size = size
            item.file_count = count
            item.last_modified = mod_date

            results.append(item)
            if item_callback:
                item_callback(item)

        if progress_callback:
            progress_callback(1.0, "Scan Complete", len(results))

        return results
