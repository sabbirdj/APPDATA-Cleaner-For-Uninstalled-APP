import os
import shutil
import subprocess
from typing import List, Tuple, Optional

class EverythingCLI:
    def __init__(self, custom_path: Optional[str] = None):
        self.cli_path = self._find_es_executable(custom_path)
        self.is_available = self._test_connection()

    def _find_es_executable(self, custom_path: Optional[str] = None) -> Optional[str]:
        """Finds the path to es.exe on the system."""
        if custom_path and os.path.isfile(custom_path):
            return custom_path

        # Check next to executable or inside PyInstaller bundle
        import sys
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        app_dirs = [
            exe_dir,
            os.path.join(exe_dir, "_internal"),
            getattr(sys, "_MEIPASS", ""),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ]
        for app_dir in app_dirs:
            if app_dir:
                bundled = os.path.join(app_dir, "es.exe")
                if os.path.isfile(bundled):
                    return bundled

        # Check PATH
        which_path = shutil.which("es.exe") or shutil.which("es")
        if which_path:
            return which_path

        # Common known installation paths
        localappdata = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(localappdata, r"Microsoft\WinGet\Links\es.exe"),
            r"C:\Program Files\Everything\es.exe",
            r"C:\Program Files (x86)\Everything\es.exe",
            os.path.join(localappdata, r"Programs\Everything\es.exe"),
        ]
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate

        return None

    def _test_connection(self) -> bool:
        """Tests if es.exe can communicate with the running Everything service."""
        if not self.cli_path:
            return False
        try:
            res = subprocess.run(
                [self.cli_path, "-get-result-count", "Everything.exe"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_query(self, args: List[str], timeout: int = 4) -> List[str]:
        """
        Runs a query with es.exe with properly separated arguments.
        IMPORTANT: Do not bundle switches into one string.
        """
        if not self.cli_path or not self.is_available:
            return []
        try:
            cmd = [self.cli_path] + args
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                return lines
            return []
        except Exception:
            return []

    def get_result_count(self, search_term: str) -> int:
        """Gets total count of items matching a search query."""
        if not self.cli_path or not self.is_available:
            return 0
        try:
            cmd = [self.cli_path, "-get-result-count", search_term]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            out = res.stdout.strip()
            return int(out) if out.isdigit() else 0
        except Exception:
            return 0

    def query_executables(self, app_name: str, max_results: int = 5) -> List[str]:
        """Searches for main executables matching the app name."""
        if not self.cli_path or not self.is_available:
            return []
        
        # Check exact and wildcard patterns: e.g. wfn:uv.exe or wfn:*IDM*.exe
        queries = [f"wfn:{app_name}.exe", f"wfn:*{app_name}*.exe"]
        valid_exes = []
        for q in queries:
            args = ["-n", str(max_results), "ext:exe", q]
            results = self.run_query(args)
            for exe in results:
                exe_lower = exe.lower()
                # Exclude installers, caches, downloads, temp, recycle bin
                if any(p in exe_lower for p in ["$recycle.bin", "temp", "cache", "installer", "setup", "download"]):
                    continue
                if any(p in exe_lower for p in ["program files", "programs", "windowsapps"]):
                    valid_exes.append(exe)
            if valid_exes:
                break

        return list(dict.fromkeys(valid_exes))

    def query_install_locations(self, app_name: str) -> List[str]:
        """Searches for installation folders in Program Files or AppData Local Programs."""
        if not self.cli_path or not self.is_available:
            return []
        
        folders_found = []
        # Use folder:wfn: to match the exact folder name rather than arbitrary substrings
        for pf_path in [r"C:\Program Files", r"C:\Program Files (x86)"]:
            res = self.run_query(["-path", pf_path, "-n", "3", f"folder:wfn:{app_name}"])
            if not res:
                # Also try matching folder prefix
                res = self.run_query(["-path", pf_path, "-n", "3", f"folder:wfn:*{app_name}*"])
            folders_found.extend(res)
        
        local_programs = os.path.expandvars(r"%LOCALAPPDATA%\Programs")
        if os.path.isdir(local_programs):
            res = self.run_query(["-path", local_programs, "-n", "3", f"folder:wfn:{app_name}"])
            folders_found.extend(res)

        return list(dict.fromkeys(folders_found))

    def query_shortcuts(self, app_name: str) -> List[str]:
        """Searches for Start Menu or Desktop shortcuts for the app."""
        if not self.cli_path or not self.is_available:
            return []
        # Separated arguments for ext:lnk and path:Programs
        args = ["-n", "3", "ext:lnk", "path:Programs", app_name]
        return self.run_query(args)

    def check_app_installed(self, folder_name: str, subfolder_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Uses Everything CLI to determine if an application exists on the system.
        Returns:
            (is_installed, list_of_evidence_strings)
        """
        if not self.is_available:
            return False, ["Everything CLI is not connected or service not running."]

        evidence = []
        candidates = [folder_name] + [sub for sub in subfolder_names if len(sub) > 2]

        # Generate search variations
        search_terms = []
        for term in candidates:
            search_terms.append(term)
            # Remove symbols/dashes
            simplified = term.replace("-", " ").replace("_", " ").split()[0]
            if len(simplified) >= 3 and simplified.lower() != term.lower():
                search_terms.append(simplified)

        search_terms = list(dict.fromkeys(search_terms))

        for term in search_terms:
            # 1. Check Start Menu shortcuts (very strong signal of installed app)
            shortcuts = self.query_shortcuts(term)
            if shortcuts:
                evidence.append(f"Start Menu shortcut found: {shortcuts[0]}")
                return True, evidence

            # 2. Check direct install folders in Program Files / Local Programs
            install_dirs = self.query_install_locations(term)
            if install_dirs:
                evidence.append(f"Install folder found: {install_dirs[0]}")
                return True, evidence

            # 3. Check for main executable in Program Files, WindowsApps, or Local Programs
            exes = self.query_executables(term, max_results=5)
            if exes:
                evidence.append(f"Installed executable found: {exes[0]}")
                return True, evidence

        return False, ["No installed executable, install folder, or Start Menu shortcut found via Everything."]
