import os
import json
from typing import Set, List

BUILTIN_PROTECTED_FOLDERS = {
    # Core Windows and Microsoft System Folders
    "microsoft",
    "windows",
    "packages",
    "temp",
    "virtualstore",
    "comms",
    "d3dscache",
    "crashdumps",
    "system",
    "identitycrl",
    "connecteddevicesplatform",
    "publishers",
    "peerdistrep",
    "elevateddiagnostics",
    "crypto",
    "driverstore",
    "windowsapps",
    "microsoft shared",
    "system certificates",
    "usoprivate",
    "usoshared",
    "windows defender",
    "windows security",
    "windows media player",
    "speech",
    "credentials",
    "history",
    "inetcache",
    "cookies",
    "caches",
    "localappdata",
    "programs",  # AppData\Local\Programs contains active applications

    # Hardware & Driver Platforms
    "nvidia",
    "nvidia corporation",
    "amd",
    "intel",
    "realtek",

    # Package managers, language runtimes, developer cache
    "pip",
    "npm",
    "yarn",
    "git",
    "docker",
    "nuget",
    "packagemanagement",
    "winget",
    ".dotnet",
    ".gemini",
    ".git",
}

def _get_default_whitelist_path() -> str:
    """Returns persistent path in %APPDATA% or fallback to local directory."""
    local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_whitelist.json")
    if os.path.isfile(local_path):
        return local_path

    appdata = os.environ.get("APPDATA")
    if appdata:
        app_dir = os.path.join(appdata, "AppDataOrphanCleaner")
        try:
            os.makedirs(app_dir, exist_ok=True)
            return os.path.join(app_dir, "user_whitelist.json")
        except Exception:
            pass
    return local_path

WHITELIST_FILE = _get_default_whitelist_path()

class WhitelistManager:
    def __init__(self, config_path: str = WHITELIST_FILE):
        self.config_path = config_path
        self.user_whitelist: Set[str] = set()
        self.load()

    def load(self):
        """Loads user-defined whitelist from JSON."""
        self.user_whitelist.clear()
        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.user_whitelist = {item.strip().lower() for item in data if item.strip()}
            except Exception:
                pass

    def save(self):
        """Saves user-defined whitelist to JSON."""
        try:
            parent_dir = os.path.dirname(self.config_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.user_whitelist)), f, indent=2)
        except Exception:
            pass

    def is_windows_related(self, folder_name: str, folder_path: str = "") -> bool:
        """Determines whether a folder is an OS component, Windows, or Microsoft-related folder."""
        clean = folder_name.strip().lower()
        path = folder_path.strip().lower()

        # 1. Any folder containing 'microsoft' (e.g. Microsoft, Microsoft DevDiv, regid.1991-06.com.microsoft)
        if "microsoft" in clean:
            return True

        # 2. Any folder starting with 'windows' or named 'windows' (e.g. Windows, WindowsHolographicDevices, Windows NT)
        if clean.startswith("windows") or clean == "windows":
            return True

        # 3. Known Windows and Microsoft OS keywords
        WINDOWS_KEYWORDS = {
            "windowspowershell", "windowsapps", "windows defender",
            "windows security", "windows media player", "windows mail",
            "windows nt", "windowsholographicdevices", "windows collaboration",
            "windows setup", "windows journal", "windows photo viewer",
            "windows feedback hub", "packages", "package cache", "usoprivate",
            "usoshared", "system certificates", "system volume information",
            "softwaredistribution", "virtualstore", "identitycrl",
            "connecteddevicesplatform", "elevateddiagnostics", "d3dscache",
            "crashdumps", "comms", "crypto", "driverstore", "internet explorer",
            "wer", "diagtrack", "oobe", "programs", "localappdata"
        }
        if clean in WINDOWS_KEYWORDS:
            return True

        # 4. Built-in protected system components
        if clean in BUILTIN_PROTECTED_FOLDERS:
            return True

        # 5. Check known Windows OS directory paths
        if any(p in path for p in [
            "\\appdata\\local\\packages",
            "\\appdata\\local\\microsoft",
            "\\programdata\\microsoft",
            "\\appdata\\local\\programs"
        ]):
            return True

        return False

    def is_protected(self, folder_name: str, folder_path: str = "") -> bool:
        """Returns True if the folder is in the built-in protected list, Windows-related, or user whitelist."""
        clean_name = folder_name.strip().lower()

        # Check Windows-related components
        if self.is_windows_related(clean_name, folder_path):
            return True

        # Check built-in protected
        if clean_name in BUILTIN_PROTECTED_FOLDERS:
            return True

        # Check user whitelist
        if clean_name in self.user_whitelist:
            return True

        return False

    def add(self, folder_name: str) -> bool:
        """Adds a folder to user whitelist."""
        clean = folder_name.strip().lower()
        if clean and clean not in self.user_whitelist and clean not in BUILTIN_PROTECTED_FOLDERS:
            self.user_whitelist.add(clean)
            self.save()
            return True
        return False

    def remove(self, folder_name: str) -> bool:
        """Removes a folder from user whitelist."""
        clean = folder_name.strip().lower()
        if clean in self.user_whitelist:
            self.user_whitelist.remove(clean)
            self.save()
            return True
        return False

    def get_custom_items(self) -> List[str]:
        """Returns list of user-added items."""
        return sorted(list(self.user_whitelist))

    def get_builtin_items(self) -> List[str]:
        """Returns list of built-in protected names."""
        return sorted(list(BUILTIN_PROTECTED_FOLDERS))
