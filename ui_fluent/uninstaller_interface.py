import os
import sys
from typing import List, Optional, Dict

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QFileInfo
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem,
    QAbstractItemView, QLabel, QSizePolicy, QDialog, QFileIconProvider
)
from qfluentwidgets import (
    TableWidget, PrimaryPushButton, PushButton, SearchLineEdit,
    ComboBox, CardWidget, TitleLabel, SubtitleLabel, CaptionLabel,
    BodyLabel, StrongBodyLabel, InfoBar, InfoBarPosition,
    ProgressBar, IndeterminateProgressBar, CheckBox, LineEdit,
    FluentIcon as FIF, MessageBoxBase
)

from backend.app_manager import AppManager, InstalledApp
from backend.leftover_scanner import LeftoverScanner, LeftoverItem
from backend.everything_cli import EverythingCLI
from ui_fluent.formatters import format_size

_icon_provider: Optional[QFileIconProvider] = None
_icon_cache: Dict[str, QIcon] = {}

def get_app_icon(app: Optional[InstalledApp], fallback: FIF = FIF.APPLICATION) -> QIcon:
    """
    Extracts high-resolution native Windows icons from .exe, .lnk, .ico, or fallback.
    Caches QIcon instances in-memory for instant sorting and filtering.
    """
    global _icon_provider, _icon_cache
    if not app:
        return fallback.icon()

    path = getattr(app, "resolved_icon_path", "") or (app.clean_icon_path() if hasattr(app, "clean_icon_path") else "")
    if not path:
        return fallback.icon()

    if path in _icon_cache:
        return _icon_cache[path]

    # For standard image/ico files
    if path.lower().endswith((".ico", ".png", ".jpg", ".jpeg", ".svg")):
        ic = QIcon(path)
        if not ic.isNull():
            _icon_cache[path] = ic
            return ic

    # For Windows executables (.exe, .dll) and shortcuts (.lnk), use QFileIconProvider
    if _icon_provider is None:
        _icon_provider = QFileIconProvider()

    try:
        fi = QFileInfo(path)
        ic = _icon_provider.icon(fi)
        if not ic.isNull():
            _icon_cache[path] = ic
            return ic
    except Exception:
        pass

    return fallback.icon()

# -------------------------------------------------------------------------
# Background Worker Threads
# -------------------------------------------------------------------------

class UninstallWorker(QThread):
    """Executes the native uninstaller process and waits for it to complete."""
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, app_manager: AppManager, app: InstalledApp, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.app = app

    def run(self):
        try:
            proc = self.app_manager.run_uninstaller(self.app)
            ret = proc.wait()
            self.finished.emit(ret)
        except Exception as e:
            self.error.emit(str(e))

class LeftoverScanWorker(QThread):
    """Executes the deep targeted leftover scan."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, scanner: LeftoverScanner, app_name: str, publisher: str = "",
                 install_loc: str = "", reg_key: str = "", reg_hive: str = "", parent=None):
        super().__init__(parent)
        self.scanner = scanner
        self.app_name = app_name
        self.publisher = publisher
        self.install_loc = install_loc
        self.reg_key = reg_key
        self.reg_hive = reg_hive

    def run(self):
        try:
            items = self.scanner.scan_leftovers(
                app_name=self.app_name,
                publisher=self.publisher,
                install_location=self.install_loc,
                registry_key=self.reg_key,
                registry_hive=self.reg_hive
            )
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))


# -------------------------------------------------------------------------
# Leftover Review & Cleanup Dialog (IObit / Revo Style)
# -------------------------------------------------------------------------

class LeftoverReviewDialog(QDialog):
    """
    Step-by-step uninstallation and leftover review wizard:
    Stage 1: Launch native uninstaller & wait
    Stage 2: Deep scan for files, folders, AppData, and Registry remnants
    Stage 3: Review and safe cleanup
    """

    def __init__(
        self,
        app: Optional[InstalledApp],
        app_manager: AppManager,
        leftover_scanner: LeftoverScanner,
        target_name: str = "",
        auto_uninstall: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.app = app
        self.app_manager = app_manager
        self.leftover_scanner = leftover_scanner
        self.target_name = app.name if app else target_name
        self.auto_uninstall = auto_uninstall
        self.leftover_items: List[LeftoverItem] = []

        self.setWindowTitle(f"Leftover Cleaner — {self.target_name}")
        self.resize(840, 560)
        self.setMinimumSize(720, 480)

        self._init_ui()

        # Start workflow
        if self.app and self.auto_uninstall and self.app.get_effective_uninstall_command():
            self._start_uninstall_stage()
        else:
            self._start_scan_stage()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 20, 28, 20)
        self.layout.setSpacing(14)

        # Header Title
        title_row = QHBoxLayout()
        icon_lbl = QLabel(self)
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setPixmap(get_app_icon(self.app).pixmap(36, 36))
        title_row.addWidget(icon_lbl)

        v_box = QVBoxLayout()
        v_box.setSpacing(2)
        self.lbl_title = TitleLabel(self.target_name, self)
        v_box.addWidget(self.lbl_title)

        sub_text = f"Publisher: {self.app.publisher or 'Unknown'} | Version: {self.app.version or 'N/A'}" if self.app else "Targeted Leftover Search"
        self.lbl_sub = CaptionLabel(sub_text, self)
        self.lbl_sub.setTextColor("#94A3B8", "#64748B")
        v_box.addWidget(self.lbl_sub)
        title_row.addLayout(v_box, 1)
        self.layout.addLayout(title_row)

        # Status & Progress Area
        self.status_card = CardWidget(self)
        s_lay = QVBoxLayout(self.status_card)
        s_lay.setContentsMargins(16, 12, 16, 12)
        s_lay.setSpacing(8)

        self.lbl_status = BodyLabel("Preparing...", self.status_card)
        s_lay.addWidget(self.lbl_status)

        self.progress_bar = IndeterminateProgressBar(self.status_card)
        s_lay.addWidget(self.progress_bar)
        self.layout.addWidget(self.status_card)

        # Results Table Area
        self.table = TableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Type", "Item Name", "Details", "Path"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.setVisible(False)
        self.layout.addWidget(self.table, 1)

        # Bulk selection toolbar (visible on Stage 3)
        self.bulk_bar = QHBoxLayout()
        self.btn_select_all = PushButton("Select All", self)
        self.btn_select_all.clicked.connect(self._select_all)
        self.bulk_bar.addWidget(self.btn_select_all)

        self.btn_deselect_all = PushButton("Deselect All", self)
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        self.bulk_bar.addWidget(self.btn_deselect_all)

        self.bulk_bar.addStretch(1)

        self.lbl_selection_summary = CaptionLabel("", self)
        self.bulk_bar.addWidget(self.lbl_selection_summary)

        self.bulk_container = QWidget()
        self.bulk_container.setLayout(self.bulk_bar)
        self.bulk_container.setVisible(False)
        self.layout.addWidget(self.bulk_container)

        # Bottom Command Bar
        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.addStretch(1)

        self.btn_cancel = PushButton("Close", self)
        self.btn_cancel.clicked.connect(self.close)
        self.bottom_bar.addWidget(self.btn_cancel)

        self.btn_clean = PrimaryPushButton("Delete Selected Leftovers (Safe)", self)
        self.btn_clean.setIcon(FIF.DELETE)
        self.btn_clean.clicked.connect(self._on_clean_clicked)
        self.btn_clean.setVisible(False)
        self.bottom_bar.addWidget(self.btn_clean)

        self.layout.addLayout(self.bottom_bar)

    # -------------------------------------------------------------
    # Stage 1: Run Native Uninstaller
    # -------------------------------------------------------------
    def _start_uninstall_stage(self):
        self.lbl_status.setText("Running official uninstaller... Please complete the uninstaller dialog on your screen if prompted.")
        self.progress_bar.setVisible(True)

        self.uninstall_worker = UninstallWorker(self.app_manager, self.app, self)
        self.uninstall_worker.finished.connect(self._on_uninstaller_finished)
        self.uninstall_worker.error.connect(self._on_uninstaller_error)
        self.uninstall_worker.start()

    def _on_uninstaller_finished(self, exit_code: int):
        self._start_scan_stage()

    def _on_uninstaller_error(self, error_msg: str):
        InfoBar.warning(
            title="Uninstaller Warning",
            content=f"Could not launch standard uninstaller: {error_msg}. Proceeding directly to leftover scan.",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
        self._start_scan_stage()

    # -------------------------------------------------------------
    # Stage 2: Deep Leftover Scan
    # -------------------------------------------------------------
    def _start_scan_stage(self):
        self.lbl_status.setText("Scanning for leftover files, folders, AppData, and registry entries...")
        self.progress_bar.setVisible(True)

        pub = self.app.publisher if self.app else ""
        loc = self.app.install_location if self.app else ""
        reg_k = self.app.registry_key if self.app else ""
        reg_h = self.app.registry_hive if self.app else ""

        self.scan_worker = LeftoverScanWorker(
            self.leftover_scanner, self.target_name, pub, loc, reg_k, reg_h, self
        )
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _on_scan_finished(self, items: List[LeftoverItem]):
        self.progress_bar.setVisible(False)
        self.leftover_items = items

        if not items:
            self.lbl_status.setText("✓ No leftover files or registry keys detected! Clean uninstallation.")
            self.lbl_status.setStyleSheet("color: #4ADE80; font-weight: bold;")
            self.btn_cancel.setText("Done")
            return

        # Stage 3: Present leftovers
        folders_count = sum(1 for it in items if it.item_type == "FOLDER")
        files_count = sum(1 for it in items if it.item_type == "FILE")
        reg_count = sum(1 for it in items if it.item_type == "REGISTRY_KEY")
        total_size = sum(it.size for it in items)

        summary_msg = f"Detected {len(items)} leftover items ({folders_count} folders, {files_count} files, {reg_count} registry keys, {format_size(total_size)})."
        self.lbl_status.setText(summary_msg)
        self.lbl_status.setStyleSheet("color: #F59E0B; font-weight: bold;")

        self.table.setVisible(True)
        self.bulk_container.setVisible(True)
        self.btn_clean.setVisible(True)
        self.btn_cancel.setText("Skip / Cancel")

        self._populate_table()
        self._update_summary()

    def _on_scan_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"Scan error: {err}")
        self.lbl_status.setStyleSheet("color: #F87171;")

    # -------------------------------------------------------------
    # Stage 3: Populate and Manage Leftovers Table
    # -------------------------------------------------------------
    def _populate_table(self):
        self.table.setRowCount(len(self.leftover_items))
        for row, item in enumerate(self.leftover_items):
            # Checkbox
            chk = CheckBox(self.table)
            chk.setFixedSize(22, 22)
            chk.setChecked(item.selected)
            chk.stateChanged.connect(lambda _, it=item, c=chk: self._on_item_check(it, c.isChecked()))
            chk_container = QWidget()
            c_lay = QHBoxLayout(chk_container)
            c_lay.addWidget(chk)
            c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, chk_container)

            # Type badge
            type_item = QTableWidgetItem(item.item_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, type_item)

            # Name
            name_item = QTableWidgetItem(item.name)
            self.table.setItem(row, 2, name_item)

            # Details
            detail_item = QTableWidgetItem(f"{item.details} ({format_size(item.size)})" if item.size else item.details)
            self.table.setItem(row, 3, detail_item)

            # Path
            path_item = QTableWidgetItem(item.path)
            path_item.setToolTip(item.path)
            self.table.setItem(row, 4, path_item)

    def _on_item_check(self, item: LeftoverItem, checked: bool):
        item.selected = checked
        self._update_summary()

    def _select_all(self):
        for it in self.leftover_items:
            it.selected = True
        self._populate_table()
        self._update_summary()

    def _deselect_all(self):
        for it in self.leftover_items:
            it.selected = False
        self._populate_table()
        self._update_summary()

    def _update_summary(self):
        selected = [it for it in self.leftover_items if it.selected]
        sz = sum(it.size for it in selected)
        self.lbl_selection_summary.setText(f"Selected: {len(selected)} items ({format_size(sz)})")
        self.btn_clean.setEnabled(len(selected) > 0)

    def _on_clean_clicked(self):
        selected = [it for it in self.leftover_items if it.selected]
        if not selected:
            return

        success, failed = self.leftover_scanner.delete_leftovers(selected, permanent=False)
        if failed == 0:
            InfoBar.success(
                title="Cleanup Complete",
                content=f"Successfully cleaned {success} leftover items. Files were moved to the Recycle Bin.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self.parent() or self
            )
            self.accept()
        else:
            InfoBar.warning(
                title="Cleanup Result",
                content=f"Cleaned {success} items. {failed} items could not be removed (in use or locked).",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self.parent() or self
            )
            self.accept()


# -------------------------------------------------------------------------
# Targeted Leftover Search Modal (for previously uninstalled apps)
# -------------------------------------------------------------------------

class TargetedSearchDialog(QDialog):
    """Simple dialog to input an application name and launch leftover discovery."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Targeted Leftover Search")
        self.resize(460, 200)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        t_lbl = TitleLabel("Search Leftovers", self)
        lay.addWidget(t_lbl)

        desc = CaptionLabel("Enter the name of a previously uninstalled software to search for remaining AppData and Registry keys:", self)
        desc.setTextColor("#94A3B8", "#64748B")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.input_name = LineEdit(self)
        self.input_name.setPlaceholderText("e.g. Zoom, Discord, IDM, Brother, Skype...")
        lay.addWidget(self.input_name)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_cancel = PushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self.btn_search = PrimaryPushButton("Find Leftovers", self)
        self.btn_search.setIcon(FIF.SEARCH)
        self.btn_search.clicked.connect(self._submit)
        btn_row.addWidget(self.btn_search)

        lay.addLayout(btn_row)

    def _submit(self):
        text = self.input_name.text().strip()
        if text:
            self.accept()

    def get_query(self) -> str:
        return self.input_name.text().strip()


# -------------------------------------------------------------------------
# Main Uninstaller Interface (Revo / IObit Style Dashboard)
# -------------------------------------------------------------------------

class UninstallerInterface(QWidget):
    """
    Primary dashboard for listing installed applications, launching built-in
    uninstallers, and initiating deep post-uninstall leftover cleanup.
    """

    def __init__(self, everything_cli: Optional[EverythingCLI] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("uninstallerInterface")

        self.app_manager = AppManager()
        self.leftover_scanner = LeftoverScanner(everything_cli=everything_cli)
        self.all_apps: List[InstalledApp] = []
        self.filtered_apps: List[InstalledApp] = []

        self.sort_column = 0  # 0: Name
        self.sort_ascending = True

        self._init_ui()
        self.refresh_apps()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(36, 24, 36, 24)
        self.main_layout.setSpacing(14)

        # 1. Header Title
        lbl_title = TitleLabel("Application Uninstaller & Leftover Cleaner", self)
        lbl_sub = CaptionLabel("Uninstall installed software and thoroughly purge leftover AppData and Registry keys with zero false positives.", self)
        lbl_sub.setTextColor("#94A3B8", "#64748B")
        self.main_layout.addWidget(lbl_title)
        self.main_layout.addWidget(lbl_sub)

        # 2. Top Summary Stat Cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.card_total = self._create_metric_card("Installed Applications", "0 Apps", "Detected in Windows Registry")
        self.card_size = self._create_metric_card("Estimated Total Space", "0 MB", "Total calculated disk usage", accent="#38BDF8")
        self.card_target = self._create_metric_card("Targeted Leftovers Mode", "Zero False Positives", "Runs uninstaller then purges leftovers", accent="#4ADE80")

        cards_row.addWidget(self.card_total)
        cards_row.addWidget(self.card_size)
        cards_row.addWidget(self.card_target)
        self.main_layout.addLayout(cards_row)

        # 3. Search, Sort, and Action Toolbar
        toolbar_card = CardWidget(self)
        tb_lay = QHBoxLayout(toolbar_card)
        tb_lay.setContentsMargins(16, 10, 16, 10)
        tb_lay.setSpacing(12)

        self.search_box = SearchLineEdit(toolbar_card)
        self.search_box.setPlaceholderText("Search installed applications by name or publisher...")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tb_lay.addWidget(self.search_box, 1)

        # Sort combo
        tb_lay.addWidget(CaptionLabel("Sort by:", toolbar_card))
        self.combo_sort = ComboBox(toolbar_card)
        self.combo_sort.addItems([
            "Name (A → Z)",
            "Name (Z → A)",
            "Size (Largest First)",
            "Size (Smallest First)",
            "Install Date (Newest)"
        ])
        self.combo_sort.currentIndexChanged.connect(self._on_sort_changed)
        tb_lay.addWidget(self.combo_sort)

        # Targeted Leftovers Search Button
        self.btn_targeted_search = PushButton("Search Past Leftovers", toolbar_card)
        self.btn_targeted_search.setIcon(FIF.SEARCH)
        self.btn_targeted_search.setToolTip("Scan leftovers for an application you uninstalled in the past")
        self.btn_targeted_search.clicked.connect(self._open_targeted_search)
        tb_lay.addWidget(self.btn_targeted_search)

        # Refresh button
        self.btn_refresh = PushButton("Refresh", toolbar_card)
        self.btn_refresh.setIcon(FIF.SYNC)
        self.btn_refresh.clicked.connect(self.refresh_apps)
        tb_lay.addWidget(self.btn_refresh)

        self.main_layout.addWidget(toolbar_card)

        # 4. Applications Table
        self.table = TableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Program Name", "Publisher", "Version", "Size", "Install Date", "Action"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Publisher
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Version
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Size
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Install Date
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)            # Action
        self.table.setColumnWidth(5, 120)

        self.main_layout.addWidget(self.table, 1)

    def _create_metric_card(self, title: str, value: str, sub: str, accent: str = None) -> CardWidget:
        card = CardWidget(self)
        card.setFixedHeight(84)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)

        lbl_t = CaptionLabel(title, card)
        lbl_t.setTextColor("#94A3B8", "#64748B")
        lay.addWidget(lbl_t)

        lbl_v = StrongBodyLabel(value, card)
        font = lbl_v.font()
        font.setPointSize(16)
        font.setBold(True)
        lbl_v.setFont(font)
        if accent:
            lbl_v.setStyleSheet(f"color: {accent}; font-weight: bold; font-size: 16px;")
        card.value_label = lbl_v
        lay.addWidget(lbl_v)

        lbl_s = CaptionLabel(sub, card)
        lbl_s.setTextColor("#CBD5E1", "#475569")
        card.sub_label = lbl_s
        lay.addWidget(lbl_s)
        return card

    def refresh_apps(self):
        """Scans registry for installed apps and refreshes UI."""
        self.all_apps = self.app_manager.refresh()
        total_kb = sum(a.size_kb for a in self.all_apps)

        self.card_total.value_label.setText(f"{len(self.all_apps)} Apps")
        self.card_size.value_label.setText(format_size(total_kb * 1024))

        self._filter_and_sort()

    def _on_search_changed(self):
        self._filter_and_sort()

    def _on_sort_changed(self):
        self._filter_and_sort()

    def _filter_and_sort(self):
        query = self.search_box.text().strip().lower()
        if query:
            self.filtered_apps = [
                a for a in self.all_apps
                if query in a.name.lower() or query in a.publisher.lower()
            ]
        else:
            self.filtered_apps = list(self.all_apps)

        sort_idx = self.combo_sort.currentIndex()
        if sort_idx == 0:  # Name A-Z
            self.filtered_apps.sort(key=lambda x: x.name.lower())
        elif sort_idx == 1:  # Name Z-A
            self.filtered_apps.sort(key=lambda x: x.name.lower(), reverse=True)
        elif sort_idx == 2:  # Size Largest
            self.filtered_apps.sort(key=lambda x: x.size_bytes, reverse=True)
        elif sort_idx == 3:  # Size Smallest
            self.filtered_apps.sort(key=lambda x: x.size_bytes)
        elif sort_idx == 4:  # Date Newest
            self.filtered_apps.sort(key=lambda x: x.install_date or "0000", reverse=True)

        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self.filtered_apps))

        for row, app in enumerate(self.filtered_apps):
            # Col 0: Program Name with Icon
            name_item = QTableWidgetItem(app.name)
            name_item.setIcon(get_app_icon(app))
            name_item.setToolTip(f"Install Location: {app.install_location or 'Registry standard'}")
            self.table.setItem(row, 0, name_item)

            # Col 1: Publisher
            pub_item = QTableWidgetItem(app.publisher or "—")
            self.table.setItem(row, 1, pub_item)

            # Col 2: Version
            ver_item = QTableWidgetItem(app.version or "—")
            self.table.setItem(row, 2, ver_item)

            # Col 3: Size
            sz_str = format_size(app.size_bytes) if app.size_bytes > 0 else "—"
            sz_item = QTableWidgetItem(sz_str)
            self.table.setItem(row, 3, sz_item)

            # Col 4: Install Date
            date_item = QTableWidgetItem(app.install_date or "—")
            self.table.setItem(row, 4, date_item)

            # Col 5: Uninstall Action Button
            btn_uninstall = PrimaryPushButton("Uninstall", self.table)
            btn_uninstall.setIcon(FIF.DELETE)
            btn_uninstall.setFixedSize(100, 30)
            btn_uninstall.clicked.connect(lambda _, a=app: self._on_uninstall_clicked(a))

            cell_widget = QWidget()
            c_lay = QHBoxLayout(cell_widget)
            c_lay.addWidget(btn_uninstall)
            c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 5, cell_widget)

    def _on_uninstall_clicked(self, app: InstalledApp):
        """Launches the uninstallation wizard and post-uninstall leftover cleaner."""
        dlg = LeftoverReviewDialog(
            app=app,
            app_manager=self.app_manager,
            leftover_scanner=self.leftover_scanner,
            parent=self.window() or self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh app list upon successful uninstall / cleanup
            self.refresh_apps()

    def _open_targeted_search(self):
        """Allows users to search and purge leftovers for software uninstalled in the past."""
        search_dlg = TargetedSearchDialog(parent=self.window() or self)
        if search_dlg.exec() == QDialog.DialogCode.Accepted:
            query = search_dlg.get_query()
            if query:
                # Open Leftover review dialog directly in scan mode
                dlg = LeftoverReviewDialog(
                    app=None,
                    app_manager=self.app_manager,
                    leftover_scanner=self.leftover_scanner,
                    target_name=query,
                    auto_uninstall=False,
                    parent=self.window() or self
                )
                dlg.exec()
