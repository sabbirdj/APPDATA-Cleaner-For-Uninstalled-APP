from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton, LineEdit,
    TitleLabel, SubtitleLabel, CaptionLabel, BodyLabel,
    StrongBodyLabel, InfoBar, InfoBarPosition, ComboBox,
    FluentIcon as FIF, setTheme, Theme
)
from backend.everything_cli import EverythingCLI

class SettingsInterface(QWidget):
    def __init__(self, everything_cli: EverythingCLI, on_status_changed=None, parent=None):
        super().__init__(parent)
        self.everything_cli = everything_cli
        self.on_status_changed = on_status_changed
        self.setObjectName("settingsInterface")

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)

        lbl_title = TitleLabel("Settings & Diagnostics", self)
        lbl_sub = CaptionLabel("Configure backend integration and desktop preferences", self)
        lbl_sub.setTextColor("#94A3B8", "#64748B")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # ---------------------------------------------------------
        # Everything CLI Card
        # ---------------------------------------------------------
        es_card = CardWidget(self)
        es_lay = QVBoxLayout(es_card)
        es_lay.setContentsMargins(20, 16, 20, 16)
        es_lay.setSpacing(10)

        es_title = StrongBodyLabel("Voidtools Everything CLI (es.exe)", es_card)
        es_lay.addWidget(es_title)

        status_text = "● CONNECTED (Service Active)" if self.everything_cli.is_available else "▲ DISCONNECTED / NOT FOUND"
        status_color = "#4ADE80" if self.everything_cli.is_available else "#F87171"
        self.lbl_status = BodyLabel(status_text, es_card)
        self.lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        es_lay.addWidget(self.lbl_status)

        path_text = f"Binary: {self.everything_cli.cli_path or 'Not detected'}"
        self.lbl_path = CaptionLabel(path_text, es_card)
        self.lbl_path.setTextColor("#CBD5E1", "#475569")
        es_lay.addWidget(self.lbl_path)

        # Path browse row
        browse_row = QHBoxLayout()
        self.input_es_path = LineEdit(es_card)
        self.input_es_path.setPlaceholderText("Custom path to es.exe...")
        if self.everything_cli.cli_path:
            self.input_es_path.setText(self.everything_cli.cli_path)
        browse_row.addWidget(self.input_es_path, 1)

        btn_browse = PushButton("Browse...", es_card)
        btn_browse.setIcon(FIF.FOLDER)
        btn_browse.clicked.connect(self._browse_es)
        browse_row.addWidget(btn_browse)

        btn_test = PrimaryPushButton("Test Connection", es_card)
        btn_test.setIcon(FIF.SYNC)
        btn_test.clicked.connect(self._test_connection)
        browse_row.addWidget(btn_test)

        es_lay.addLayout(browse_row)
        layout.addWidget(es_card)

        # ---------------------------------------------------------
        # Appearance Card
        # ---------------------------------------------------------
        theme_card = CardWidget(self)
        theme_lay = QVBoxLayout(theme_card)
        theme_lay.setContentsMargins(20, 16, 20, 16)
        theme_lay.setSpacing(10)

        theme_title = StrongBodyLabel("Appearance & Theme", theme_card)
        theme_lay.addWidget(theme_title)

        theme_row = QHBoxLayout()
        theme_lbl = BodyLabel("Theme Mode:", theme_card)
        theme_row.addWidget(theme_lbl)

        self.theme_combo = ComboBox(theme_card)
        self.theme_combo.addItems(["Dark", "Light", "System Auto"])
        self.theme_combo.setCurrentText("Dark")
        self.theme_combo.currentTextChanged.connect(self._change_theme)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)

        theme_lay.addLayout(theme_row)
        layout.addWidget(theme_card)

        # ---------------------------------------------------------
        # About & Info Card
        # ---------------------------------------------------------
        about_card = CardWidget(self)
        about_lay = QVBoxLayout(about_card)
        about_lay.setContentsMargins(20, 16, 20, 16)
        about_lay.setSpacing(6)

        about_title = StrongBodyLabel("About AppData Orphan Cleaner", about_card)
        about_lay.addWidget(about_title)

        about_desc = CaptionLabel(
            "Version 2.0 (Fluent Design Edition)\n\n"
            "This application scans AppData directories for abandoned files left behind when software is uninstalled. "
            "It queries the Voidtools Everything NTFS USN Journal and Windows Registry to verify application status in milliseconds.\n"
            "By default, all deletions are sent to the Windows Recycle Bin to ensure total safety.",
            about_card
        )
        about_desc.setTextColor("#94A3B8", "#64748B")
        about_lay.addWidget(about_desc)

        layout.addWidget(about_card)
        layout.addStretch(1)

    def _browse_es(self):
        fp, _ = QFileDialog.getOpenFileName(
            self,
            "Select Everything CLI executable",
            "",
            "Executable (*.exe);;All Files (*.*)"
        )
        if fp:
            self.input_es_path.setText(fp)
            self.everything_cli.cli_path = fp
            self._test_connection()

    def _test_connection(self):
        cand = self.input_es_path.text().strip()
        if cand:
            self.everything_cli.cli_path = cand
        self.everything_cli.is_available = self.everything_cli._test_connection()

        if self.everything_cli.is_available:
            self.lbl_status.setText("● CONNECTED (Service Active)")
            self.lbl_status.setStyleSheet("color: #4ADE80; font-weight: bold;")
            self.lbl_path.setText(f"Binary: {self.everything_cli.cli_path}")
            InfoBar.success(
                title="Connection Successful",
                content="Everything CLI connected and operational.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
        else:
            self.lbl_status.setText("▲ DISCONNECTED / NOT FOUND")
            self.lbl_status.setStyleSheet("color: #F87171; font-weight: bold;")
            InfoBar.error(
                title="Connection Failed",
                content="Unable to communicate with Everything. Ensure Everything desktop app is running.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )

        if self.on_status_changed:
            self.on_status_changed()

    def _change_theme(self, mode: str):
        if mode == "Dark":
            setTheme(Theme.DARK)
        elif mode == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.AUTO)
