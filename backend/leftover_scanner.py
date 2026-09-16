import os
import re
import winreg
import shutil
from typing import List, Dict, Any, Optional, Set, Tuple
from send2trash import send2trash

from backend.whitelist import WhitelistManager
from backend.everything_cli import EverythingCLI

class LeftoverItem:
    def __init__(
        self,
        item_type: str,  # 'FOLDER', 'FILE', 'REGISTRY_KEY'
        path: str,
        name: str,
        size: int = 0,
        details: str = "",
        hive_name: str = ""
    ):
        self.item_type = item_type
        self.path = path
        self.name = name
        self.size = size
        self.details = details
        self.hive_name = hive_name
        self.selected = True

class LeftoverScanner:
    """
    Performs targeted discovery of files, directories, and registry keys left behind
    after an application has been uninstalled.
    """

    def __init__(
        self,
        everything_cli: Optional[EverythingCLI] = None,
        whitelist_manager: Optional[WhitelistManager] = None
    ):
        self.everything_cli = everything_cli or EverythingCLI()
        self.whitelist = whitelist_manager or WhitelistManager()

    def scan_leftovers(
        self,
        app_name: str,
        publisher: str = "",
        install_location: str = "",
        registry_key: str = "",
        registry_hive: str = ""
    ) -> List[LeftoverItem]:
        """
        Executes a targeted scan specifically for the given application.
        Returns a list of LeftoverItem objects.
        """
        leftovers: List[LeftoverItem] = []
        seen_paths: Set[str] = set()

        tokens = self._generate_search_tokens(app_name, publisher)
        pub_tokens = self._clean_tokens(publisher)

        # 1. Check InstallLocation
        if install_location and os.path.exists(install_location):
            norm_loc = os.path.normpath(install_location)
            # Ensure install location is not root of Program Files or drive root
            if not self._is_root_or_system_dir(norm_loc):
                sz = self._get_path_size(norm_loc)
                leftovers.append(LeftoverItem(
                    item_type="FOLDER",
                    path=norm_loc,
                    name=os.path.basename(norm_loc) or app_name,
                    size=sz,
                    details="Leftover installation directory"
                ))
                seen_paths.add(norm_loc.lower())

        # 2. Filesystem standard locations: AppData (Roaming, Local, LocalLow), ProgramData, Start Menu
        standard_roots = [
            (os.environ.get("APPDATA", ""), "AppData\\Roaming"),
            (os.environ.get("LOCALAPPDATA", ""), "AppData\\Local"),
            (os.path.join(os.environ.get("APPDATA", ""), r"..\LocalLow"), "AppData\\LocalLow"),
            (os.environ.get("ProgramData", r"C:\ProgramData"), "ProgramData"),
            (os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"), "Start Menu (User)"),
            (os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"), "Start Menu (All Users)")
        ]

        for root_dir, category in standard_roots:
            if not root_dir or not os.path.isdir(root_dir):
                continue
            found_items = self._search_directory_for_tokens(root_dir, tokens, pub_tokens, category)
            for item in found_items:
                norm_p = os.path.normpath(item.path).lower()
                if norm_p not in seen_paths:
                    seen_paths.add(norm_p)
                    leftovers.append(item)

        # 3. Everything CLI targeted search (fast NTFS scan for remnants)
        if self.everything_cli and self.everything_cli.is_available:
            es_items = self._search_via_everything(tokens, seen_paths)
            for item in es_items:
                norm_p = os.path.normpath(item.path).lower()
                if norm_p not in seen_paths:
                    seen_paths.add(norm_p)
                    leftovers.append(item)

        # 4. Registry leftover scan (HKCU, HKLM, WOW6432Node)
        reg_items = self._scan_registry_leftovers(tokens, pub_tokens, registry_key, registry_hive)
        leftovers.extend(reg_items)

        # 5. Clean parent/child redundancy (e.g. don't list subfolders if parent folder is already marked)
        return self._deduplicate_subpaths(leftovers)

    def _deduplicate_subpaths(self, items: List[LeftoverItem]) -> List[LeftoverItem]:
        """Filters out items whose parent directory is already included in the list."""
        folders = [os.path.normpath(it.path).lower() for it in items if it.item_type == "FOLDER"]
        result = []
        for it in items:
            if it.item_type in ["FOLDER", "FILE"]:
                norm_p = os.path.normpath(it.path).lower()
                is_child = False
                for f in folders:
                    if f != norm_p and norm_p.startswith(f + os.sep):
                        is_child = True
                        break
                if is_child:
                    continue
            result.append(it)
        return result

    def _generate_search_tokens(self, app_name: str, publisher: str = "") -> List[str]:
        """Generates distinctive search keywords for the target application."""
        tokens = set()
        clean_name = app_name.strip()
        
        # Remove version numbers, architectures, release tags
        simplified = re.sub(r'(?i)\b(v?\d+(\.\d+)*|x64|x86|64-bit|32-bit|edition|release|build)\b', '', clean_name)
        simplified = re.sub(r'[\(\)\[\]\{\}\-_,.]', ' ', simplified).strip()
        
        tokens.add(clean_name.lower())
        if simplified:
            tokens.add(simplified.lower())

        # Clean alphanumeric
        alnum = re.sub(r'[^a-z0-9]', '', clean_name.lower())
        if len(alnum) >= 3:
            tokens.add(alnum)

        # Words with 3+ characters
        words = [w.lower() for w in simplified.split() if len(w) >= 3]
        if len(words) == 1:
            tokens.add(words[0])

        # Acronym (e.g. "Internet Download Manager" -> "idm")
        if len(words) >= 2:
            acro = ''.join(w[0] for w in words)
            if len(acro) >= 2:
                tokens.add(acro)

        return [t for t in tokens if len(t) >= 2 and not self.whitelist.is_protected(t)]

    def _clean_tokens(self, text: str) -> List[str]:
        if not text:
            return []
        cleaned = re.sub(r'(?i)\b(inc|corporation|corp|ltd|llc|gmbh|co|software)\b', '', text)
        cleaned = re.sub(r'[^a-z0-9]', ' ', cleaned.lower()).strip()
        words = [w for w in cleaned.split() if len(w) >= 3]
        return words

    def _search_directory_for_tokens(
        self,
        base_dir: str,
        tokens: List[str],
        pub_tokens: List[str],
        category: str
    ) -> List[LeftoverItem]:
        """Searches base_dir and 1st-level vendor subdirectories for target tokens."""
        items: List[LeftoverItem] = []
        try:
            entries = os.listdir(base_dir)
        except Exception:
            return items

        for entry in entries:
            entry_path = os.path.join(base_dir, entry)
            entry_lower = entry.lower()

            # Safety check: skip protected Windows and driver folders
            if self.whitelist.is_protected(entry):
                continue
            if self.whitelist.is_windows_related(entry, entry_path):
                continue

            # Case A: Entry matches app tokens directly
            if self._matches_any_token(entry_lower, tokens):
                is_dir = os.path.isdir(entry_path)
                items.append(LeftoverItem(
                    item_type="FOLDER" if is_dir else "FILE",
                    path=entry_path,
                    name=entry,
                    size=self._get_path_size(entry_path),
                    details=f"Leftover in {category}"
                ))
                continue

            # Case B: Entry matches publisher (e.g. "Adobe"), search its subfolders for app (e.g. "Illustrator")
            if os.path.isdir(entry_path) and self._matches_any_token(entry_lower, pub_tokens):
                try:
                    sub_entries = os.listdir(entry_path)
                    for sub in sub_entries:
                        sub_path = os.path.join(entry_path, sub)
                        sub_lower = sub.lower()
                        if self._matches_any_token(sub_lower, tokens):
                            is_sub_dir = os.path.isdir(sub_path)
                            items.append(LeftoverItem(
                                item_type="FOLDER" if is_sub_dir else "FILE",
                                path=sub_path,
                                name=f"{entry}\\{sub}",
                                size=self._get_path_size(sub_path),
                                details=f"Leftover under {entry} in {category}"
                            ))
                except Exception:
                    pass

        return items

    def _matches_any_token(self, candidate: str, tokens: List[str]) -> bool:
        """Returns True if candidate name matches or contains any token safely."""
        cand_clean = re.sub(r'[^a-z0-9]', '', candidate.lower())
        for tok in tokens:
            tok_clean = re.sub(r'[^a-z0-9]', '', tok)
            if not tok_clean:
                continue
            if cand_clean == tok_clean:
                return True
            if len(tok_clean) >= 4 and tok_clean in cand_clean:
                return True
        return False

    def _search_via_everything(self, tokens: List[str], seen_paths: Set[str]) -> List[LeftoverItem]:
        """Runs Everything query for AppData remnants."""
        items: List[LeftoverItem] = []
        # Use primary distinctive token with length >= 4
        query_token = None
        for t in sorted(tokens, key=len, reverse=True):
            if len(t) >= 4 and not self.whitelist.is_protected(t):
                query_token = t
                break
        if not query_token:
            return items

        results = self.everything_cli.run_query(["path:AppData", f'"{query_token}"', "-n", "15"])
        for res_path in results:
            if not os.path.exists(res_path):
                continue
            norm = os.path.normpath(res_path)
            if norm.lower() in seen_paths:
                continue
            base = os.path.basename(norm)
            if self.whitelist.is_protected(base) or self.whitelist.is_windows_related(base, norm):
                continue

            is_dir = os.path.isdir(norm)
            items.append(LeftoverItem(
                item_type="FOLDER" if is_dir else "FILE",
                path=norm,
                name=base,
                size=self._get_path_size(norm),
                details="Discovered via Everything indexer in AppData"
            ))
        return items

    def _scan_registry_leftovers(
        self,
        tokens: List[str],
        pub_tokens: List[str],
        uninstall_key: str = "",
        uninstall_hive: str = ""
    ) -> List[LeftoverItem]:
        """Scans HKCU and HKLM Software keys for leftover application data."""
        items: List[LeftoverItem] = []
        reg_roots = [
            (winreg.HKEY_CURRENT_USER, r"Software", "HKCU\\Software"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software", "HKLM\\Software"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node", "HKLM\\Software\\WOW6432Node")
        ]

        # 1. Check if the Uninstall key itself remains
        if uninstall_key:
            hive_map = {
                "HKCU": (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                "HKLM": (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                "HKLM_32": (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            }
            if uninstall_hive in hive_map:
                h_root, h_path = hive_map[uninstall_hive]
                target_key = f"{h_path}\\{uninstall_key}"
                try:
                    with winreg.OpenKey(h_root, target_key):
                        items.append(LeftoverItem(
                            item_type="REGISTRY_KEY",
                            path=target_key,
                            name=uninstall_key,
                            details="Leftover Windows Uninstall Registry entry",
                            hive_name=uninstall_hive
                        ))
                except EnvironmentError:
                    pass

        # 2. Check Software hive for App keys
        for root_h, base_path, display_hive in reg_roots:
            try:
                with winreg.OpenKey(root_h, base_path) as key:
                    num_sub = winreg.QueryInfoKey(key)[0]
                    for i in range(num_sub):
                        try:
                            s_name = winreg.EnumKey(key, i)
                            s_lower = s_name.lower()
                            if self.whitelist.is_protected(s_name) or self.whitelist.is_windows_related(s_name):
                                continue

                            # Direct app key match
                            if self._matches_any_token(s_lower, tokens):
                                full_reg_path = f"{base_path}\\{s_name}"
                                items.append(LeftoverItem(
                                    item_type="REGISTRY_KEY",
                                    path=full_reg_path,
                                    name=s_name,
                                    details=f"Leftover Registry settings in {display_hive}",
                                    hive_name="HKCU" if root_h == winreg.HKEY_CURRENT_USER else "HKLM"
                                ))
                                continue

                            # Publisher subkey match
                            if self._matches_any_token(s_lower, pub_tokens):
                                pub_path = f"{base_path}\\{s_name}"
                                try:
                                    with winreg.OpenKey(root_h, pub_path) as pub_key:
                                        for j in range(winreg.QueryInfoKey(pub_key)[0]):
                                            sub_app = winreg.EnumKey(pub_key, j)
                                            if self._matches_any_token(sub_app.lower(), tokens):
                                                full_sub_path = f"{pub_path}\\{sub_app}"
                                                items.append(LeftoverItem(
                                                    item_type="REGISTRY_KEY",
                                                    path=full_sub_path,
                                                    name=f"{s_name}\\{sub_app}",
                                                    details=f"Leftover Publisher settings in {display_hive}",
                                                    hive_name="HKCU" if root_h == winreg.HKEY_CURRENT_USER else "HKLM"
                                                ))
                                except EnvironmentError:
                                    pass
                        except EnvironmentError:
                            continue
            except EnvironmentError:
                continue

        return items

    def _get_path_size(self, path: str) -> int:
        """Calculates total size of a file or directory."""
        if os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except Exception:
                return 0
        total = 0
        try:
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        try:
                            total += os.path.getsize(fp)
                        except Exception:
                            pass
        except Exception:
            pass
        return total

    def _is_root_or_system_dir(self, path: str) -> bool:
        """Protects drive roots, Program Files root, Windows dir from accidental targeting."""
        clean = os.path.normpath(path).lower()
        if len(clean) <= 3 and clean.endswith(":\\"):
            return True
        system_dirs = [
            os.environ.get("SystemRoot", r"C:\Windows").lower(),
            r"c:\program files",
            r"c:\program files (x86)",
            r"c:\programdata",
            os.environ.get("APPDATA", "").lower(),
            os.environ.get("LOCALAPPDATA", "").lower(),
        ]
        return clean in system_dirs

    def delete_leftovers(self, items: List[LeftoverItem], permanent: bool = False) -> Tuple[int, int]:
        """
        Deletes the selected leftover items.
        Returns: (success_count, fail_count)
        """
        success = 0
        failed = 0

        for item in items:
            if not item.selected:
                continue

            if item.item_type in ["FOLDER", "FILE"]:
                if not os.path.exists(item.path):
                    success += 1
                    continue
                try:
                    if permanent:
                        if os.path.isdir(item.path):
                            shutil.rmtree(item.path)
                        else:
                            os.remove(item.path)
                    else:
                        send2trash(item.path)
                    success += 1
                except Exception:
                    failed += 1

            elif item.item_type == "REGISTRY_KEY":
                try:
                    root_hive = winreg.HKEY_CURRENT_USER if item.hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                    self._delete_registry_tree(root_hive, item.path)
                    success += 1
                except Exception:
                    failed += 1

        return success, failed

    def _delete_registry_tree(self, root_hive, subkey_path: str):
        """Recursively deletes a registry key and all of its subkeys."""
        try:
            with winreg.OpenKey(root_hive, subkey_path, 0, winreg.KEY_ALL_ACCESS) as key:
                info = winreg.QueryInfoKey(key)
                num_subkeys = info[0]
                while num_subkeys > 0:
                    child = winreg.EnumKey(key, 0)
                    self._delete_registry_tree(root_hive, f"{subkey_path}\\{child}")
                    num_subkeys = winreg.QueryInfoKey(key)[0]
            winreg.DeleteKey(root_hive, subkey_path)
        except FileNotFoundError:
            pass
