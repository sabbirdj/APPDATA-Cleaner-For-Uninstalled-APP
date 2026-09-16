import os
import re
import shlex
import subprocess
import winreg
from typing import Dict, Any, List, Optional, Tuple

class InstalledApp:
    def __init__(
        self,
        name: str,
        version: str = "",
        publisher: str = "",
        install_location: str = "",
        uninstall_string: str = "",
        quiet_uninstall_string: str = "",
        icon_path: str = "",
        size_kb: int = 0,
        install_date: str = "",
        registry_key: str = "",
        registry_hive: str = "",
        resolved_icon_path: str = ""
    ):
        self.name = name
        self.version = version
        self.publisher = publisher
        self.install_location = install_location
        self.uninstall_string = uninstall_string
        self.quiet_uninstall_string = quiet_uninstall_string
        self.icon_path = icon_path
        self.size_kb = size_kb
        self.install_date = install_date
        self.registry_key = registry_key
        self.registry_hive = registry_hive
        self.resolved_icon_path = resolved_icon_path

    @property
    def size_bytes(self) -> int:
        return self.size_kb * 1024

    def clean_icon_path(self) -> Optional[str]:
        """Returns clean path to .ico or .exe for icon extraction."""
        if not self.icon_path:
            return None
        clean = self.icon_path.strip()
        # Strip index suffix like ,0 or ,-1 before removing quotes
        if "," in clean:
            clean = clean.split(",")[0].strip()
        clean = clean.strip('"\'')
        if os.path.isfile(clean):
            return clean
        # Check for 64-bit executable sibling (e.g. studio.exe -> studio64.exe)
        if clean.lower().endswith(".exe"):
            c64 = clean[:-4] + "64.exe"
            if os.path.isfile(c64):
                return c64
        return None

    def get_effective_uninstall_command(self, silent: bool = False) -> str:
        """Determines best uninstaller command string to execute."""
        if silent and self.quiet_uninstall_string:
            return self.quiet_uninstall_string

        cmd = self.uninstall_string or self.quiet_uninstall_string
        if not cmd:
            return ""

        # Normalize MsiExec commands: convert /I or /i (install) to /X (uninstall)
        if "msiexec" in cmd.lower():
            # Replace /I{ or /i{ or /I { with /X
            cmd = re.sub(r'(?i)msiexec(\.exe)?\s*/i', r'msiexec.exe /x', cmd)
            if silent and "/qn" not in cmd.lower():
                cmd += " /qn"

        return cmd.strip()

class AppManager:
    """Manages discovery and uninstallation of installed Windows applications."""

    def __init__(self):
        self.apps: List[InstalledApp] = []
        self.shortcuts: List[Tuple[str, str]] = []
        self.refresh()

    def _build_shortcut_index(self):
        """Indexes Start Menu shortcuts (.lnk) for icon discovery."""
        self.shortcuts = []
        start_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        ]
        for sdir in start_dirs:
            if os.path.isdir(sdir):
                for root, _, files in os.walk(sdir):
                    for f in files:
                        if f.lower().endswith(".lnk"):
                            base = os.path.splitext(f)[0]
                            self.shortcuts.append((base, os.path.join(root, f)))

    def _resolve_app_icon(self, app: InstalledApp) -> Optional[str]:
        """
        5-tier resolution hierarchy to locate application icon:
        1. Registry DisplayIcon (via clean_icon_path)
        2. InstallLocation search for .ico or main .exe
        3. UninstallString parent dir search for .ico or main .exe
        4. Start Menu shortcuts matching app name (exact normalized)
        5. Start Menu shortcuts matching app name (fuzzy / substring)
        """
        # Tier 1: Direct clean DisplayIcon
        cand = app.clean_icon_path()
        if cand:
            return cand

        # Tier 2: Check InstallLocation
        if app.install_location and os.path.isdir(app.install_location):
            try:
                for item in os.listdir(app.install_location):
                    ilow = item.lower()
                    if ilow.endswith(".ico"):
                        return os.path.join(app.install_location, item)
                    elif ilow.endswith(".exe") and not any(x in ilow for x in ["unins", "update", "setup", "helper", "crash"]):
                        return os.path.join(app.install_location, item)
            except Exception:
                pass

        # Tier 3: Check UninstallString directory
        if app.uninstall_string:
            m = re.match(r'^\s*"([^"]+)"', app.uninstall_string) or re.match(r'^\s*([^\s,]+)', app.uninstall_string)
            if m:
                u_path = m.group(1)
                if os.path.isfile(u_path):
                    u_dir = os.path.dirname(u_path)
                    try:
                        for item in os.listdir(u_dir):
                            ilow = item.lower()
                            if ilow.endswith(".ico"):
                                return os.path.join(u_dir, item)
                            elif ilow.endswith(".exe") and not any(x in ilow for x in ["unins", "update", "setup", "helper"]):
                                return os.path.join(u_dir, item)
                    except Exception:
                        pass

        # Tier 4 & 5: Start Menu shortcuts
        norm_app = re.sub(r'[^a-z0-9]', '', app.name.lower())
        if norm_app:
            # Pass 1: exact normalized match
            for s_base, s_path in self.shortcuts:
                norm_base = re.sub(r'[^a-z0-9]', '', s_base.lower())
                if "uninstall" in norm_base:
                    continue
                if norm_app == norm_base:
                    return s_path

            # Pass 2: substring match (longer name starts with or contains)
            if len(norm_app) >= 4:
                for s_base, s_path in self.shortcuts:
                    norm_base = re.sub(r'[^a-z0-9]', '', s_base.lower())
                    if any(x in norm_base for x in ["uninstall", "documentation", "website", "prompt", "help"]):
                        continue
                    if norm_app in norm_base or norm_base in norm_app:
                        return s_path

        return None

    def refresh(self) -> List[InstalledApp]:
        """Scans Windows Registry for all user-visible installed applications."""
        self.apps.clear()
        self._build_shortcut_index()
        seen_keys = set()

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM_32"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU")
        ]

        for root_hive, subkey, hive_name in roots:
            try:
                with winreg.OpenKey(root_hive, subkey) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            dedup_key = f"{hive_name}\\{subkey_name}".lower()
                            if dedup_key in seen_keys:
                                continue
                            seen_keys.add(dedup_key)

                            with winreg.OpenKey(key, subkey_name) as app_key:
                                app = self._parse_app_key(app_key, subkey_name, hive_name)
                                if app:
                                    self.apps.append(app)
                        except EnvironmentError:
                            continue
            except EnvironmentError:
                continue

        # Resolve icons for all discovered applications
        for app in self.apps:
            app.resolved_icon_path = self._resolve_app_icon(app) or ""

        # Sort alphabetically by app name
        self.apps.sort(key=lambda x: x.name.lower())
        return self.apps

    def _parse_app_key(self, app_key, subkey_name: str, hive_name: str) -> Optional[InstalledApp]:
        """Parses an individual registry uninstall key into an InstalledApp object."""
        def get_val(field_name: str) -> Any:
            try:
                val, _ = winreg.QueryValueEx(app_key, field_name)
                return val
            except EnvironmentError:
                return None

        disp_name = get_val("DisplayName")
        if not disp_name or not str(disp_name).strip():
            return None

        name_str = str(disp_name).strip()

        # Filter out system components, hidden items, and Windows update KBs
        if get_val("SystemComponent") == 1:
            return None
        if get_val("ParentKeyName"):
            return None
        if name_str.startswith("KB") and len(name_str) <= 10 and name_str[2:].isdigit():
            return None
        if re.search(r'\bKB\d{6,}\b', name_str) and any(x in name_str.lower() for x in ["update for", "security update", "hotfix"]):
            return None

        # Uninstall strings
        uninstall_str = str(get_val("UninstallString") or "").strip()
        quiet_uninstall_str = str(get_val("QuietUninstallString") or "").strip()

        # If there is no way to uninstall, ignore unless install location exists
        if not uninstall_str and not quiet_uninstall_str:
            return None

        version = str(get_val("DisplayVersion") or "").strip()
        publisher = str(get_val("Publisher") or "").strip()
        install_loc = str(get_val("InstallLocation") or "").strip()
        icon = str(get_val("DisplayIcon") or "").strip()
        size_kb = get_val("EstimatedSize") or 0
        if not isinstance(size_kb, int):
            try:
                size_kb = int(size_kb)
            except Exception:
                size_kb = 0

        # If size_kb is 0 but install location exists, calculate folder size
        if size_kb == 0 and install_loc and os.path.isdir(install_loc):
            size_kb = self._estimate_folder_size_kb(install_loc)

        install_date = str(get_val("InstallDate") or "").strip()
        if install_date and len(install_date) == 8 and install_date.isdigit():
            # Format YYYYMMDD -> YYYY-MM-DD
            install_date = f"{install_date[:4]}-{install_date[4:6]}-{install_date[6:]}"

        return InstalledApp(
            name=name_str,
            version=version,
            publisher=publisher,
            install_location=install_loc,
            uninstall_string=uninstall_str,
            quiet_uninstall_string=quiet_uninstall_str,
            icon_path=icon,
            size_kb=size_kb,
            install_date=install_date,
            registry_key=subkey_name,
            registry_hive=hive_name
        )

    def _estimate_folder_size_kb(self, path: str) -> int:
        """Fast calculation of install directory size in KB (up to 500 files limit for speed)."""
        try:
            total_bytes = 0
            count = 0
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        total_bytes += os.path.getsize(fp)
                    count += 1
                    if count > 500:
                        break
                if count > 500:
                    break
            return total_bytes // 1024
        except Exception:
            return 0

    def run_uninstaller(self, app: InstalledApp, silent: bool = False) -> subprocess.Popen:
        """
        Executes the application's built-in uninstaller process.
        Returns the spawned subprocess.Popen object so callers can monitor progress.
        """
        cmd = app.get_effective_uninstall_command(silent=silent)
        if not cmd:
            raise ValueError(f"No uninstall command available for {app.name}")

        # Execute using standard Windows process creation
        return subprocess.Popen(cmd, shell=True)
