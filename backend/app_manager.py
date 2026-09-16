import os
import re
import shlex
import subprocess
import winreg
from typing import Dict, Any, List, Optional

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
        registry_hive: str = ""
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

    @property
    def size_bytes(self) -> int:
        return self.size_kb * 1024

    def clean_icon_path(self) -> Optional[str]:
        """Returns clean path to .ico or .exe for icon extraction."""
        if not self.icon_path:
            return None
        clean = self.icon_path.strip().strip('"\'')
        # Strip index suffix like ,0 or ,-1
        if "," in clean:
            clean = clean.split(",")[0].strip()
        if os.path.isfile(clean):
            return clean
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
        self.refresh()

    def refresh(self) -> List[InstalledApp]:
        """Scans Windows Registry for all user-visible installed applications."""
        self.apps.clear()
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
