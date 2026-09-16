import winreg
import os
import re
from typing import Dict, Any, List, Optional, Tuple

class RegistryScanner:
    def __init__(self):
        self.installed_apps: List[Dict[str, Any]] = []
        self._name_index: Dict[str, Dict[str, Any]] = {}
        self._acronym_index: Dict[str, Dict[str, Any]] = {}
        self.refresh()

    def refresh(self):
        """Scans Windows Registry uninstall keys and populates the cache."""
        self.installed_apps.clear()
        self._name_index.clear()
        self._acronym_index.clear()

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for root, subkey in roots:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                item = self._read_app_info(app_key)
                                if item and item.get("DisplayName"):
                                    self.installed_apps.append(item)
                                    self._index_item(item)
                        except EnvironmentError:
                            continue
            except EnvironmentError:
                continue

    def _read_app_info(self, key) -> Optional[Dict[str, Any]]:
        """Reads metadata for a single installed application key."""
        fields = ["DisplayName", "DisplayVersion", "Publisher", "InstallLocation", "UninstallString"]
        data = {}
        for field in fields:
            try:
                val, _ = winreg.QueryValueEx(key, field)
                if val and isinstance(val, str):
                    data[field] = val.strip()
            except EnvironmentError:
                pass

        if "DisplayName" in data:
            return data
        return None

    def _index_item(self, item: Dict[str, Any]):
        """Indexes application by normalized keywords and acronyms for fast lookup."""
        name = item["DisplayName"].lower()
        self._name_index[name] = item

        # Alphanumeric clean name
        clean_name = re.sub(r'[^a-z0-9]', '', name)
        if clean_name:
            self._name_index[clean_name] = item

        # Acronym indexing (e.g. "Internet Download Manager" -> "idm")
        words = [w for w in item["DisplayName"].split() if w and w[0].isalnum()]
        if len(words) >= 2:
            acro = ''.join(w[0].lower() for w in words)
            if len(acro) >= 2:
                self._acronym_index[acro] = item

        # Also index directory from UninstallString if present
        uninst = item.get("UninstallString", "")
        if uninst:
            clean_uninst = uninst.strip('"\'')
            uninst_dir = os.path.dirname(clean_uninst)
            if uninst_dir:
                dir_name = os.path.basename(uninst_dir).lower()
                clean_dir = re.sub(r'[^a-z0-9]', '', dir_name)
                if clean_dir and clean_dir not in self._name_index:
                    self._name_index[clean_dir] = item

    def check_app_in_registry(self, folder_name: str, subfolders: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Checks if folder name or subfolder corresponds to an installed app in Registry.
        Returns:
            (is_found, matching_app_name)
        """
        candidates = [folder_name] + subfolders
        for candidate in candidates:
            cand_lower = candidate.lower()
            cand_clean = re.sub(r'[^a-z0-9]', '', cand_lower)

            if len(cand_clean) < 2:
                continue

            # 1. Acronym match (e.g. "IDM" -> "Internet Download Manager")
            if cand_clean in self._acronym_index:
                return True, self._acronym_index[cand_clean].get("DisplayName")

            # 2. Exact match in name index
            if cand_lower in self._name_index:
                return True, self._name_index[cand_lower].get("DisplayName")
            if cand_clean in self._name_index:
                return True, self._name_index[cand_clean].get("DisplayName")

            # 3. Word token or substring match
            for app in self.installed_apps:
                disp_name = app["DisplayName"]
                disp_lower = disp_name.lower()
                disp_clean = re.sub(r'[^a-z0-9]', '', disp_lower)

                # Direct containment
                if cand_clean == disp_clean:
                    return True, disp_name
                if len(cand_clean) >= 4 and (cand_clean in disp_clean or disp_clean in cand_clean):
                    return True, disp_name

                # Check individual significant words
                app_words = [re.sub(r'[^a-z0-9]', '', w.lower()) for w in disp_name.split()]
                if cand_clean in app_words and len(cand_clean) >= 3:
                    return True, disp_name

                # Check if uninstaller or install location exists on disk
                loc = app.get("InstallLocation", "")
                uninst = app.get("UninstallString", "")
                if loc and candidate.lower() in loc.lower():
                    return True, disp_name
                if uninst and candidate.lower() in uninst.lower():
                    return True, disp_name

        return False, None
