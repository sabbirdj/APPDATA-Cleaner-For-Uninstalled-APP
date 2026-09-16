import os
import sys
import ctypes
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import (
    MSFluentWindow, NavigationItemPosition, FluentIcon as FIF,
    setTheme, Theme
)

from backend.everything_cli import EverythingCLI
from backend.scanner_engine import ScannerEngine
from ui_fluent.scanner_interface import ScannerInterface
from ui_fluent.whitelist_interface import WhitelistInterface
from ui_fluent.settings_interface import SettingsInterface

# Set Windows AppUserModelID so taskbar displays the custom app icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.appdataorphancleaner.desktop")
except Exception:
    pass

def _get_icon_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "app_icon.png"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "app_icon.ico"),
        os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "assets", "app_icon.png"),
        os.path.join(base_dir, "assets", "app_icon.png"),
        os.path.join(base_dir, "assets", "app_icon.ico"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ""

class MainWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AppData Orphan Cleaner — Powered by Everything CLI")
        self.resize(1120, 760)
        self.setMinimumSize(940, 600)

        icon_path = _get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # Initialize backend engines
        self.everything_cli = EverythingCLI()
        self.scanner = ScannerEngine(self.everything_cli)

        # Sub-interfaces
        self.scanner_interface = ScannerInterface(self.scanner, self)
        self.whitelist_interface = WhitelistInterface(self.scanner.whitelist_manager, self)
        self.settings_interface = SettingsInterface(
            self.everything_cli,
            on_status_changed=self.scanner_interface.update_everything_status,
            parent=self
        )

        self._init_navigation()

    def _init_navigation(self):
        # Add navigation items
        self.addSubInterface(
            self.scanner_interface,
            FIF.SEARCH,
            "Scanner"
        )
        self.addSubInterface(
            self.whitelist_interface,
            FIF.ACCEPT,
            "Whitelist"
        )
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM
        )

        # Default to dark theme
        setTheme(Theme.DARK)
