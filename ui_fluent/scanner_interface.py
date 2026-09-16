import os
import subprocess
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QHeaderView,
    QTableWidgetItem, QAbstractItemView, QFrame, QSizePolicy
)
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton, ToolButton, CheckBox,
    SearchLineEdit, TableWidget, ProgressBar, SegmentedWidget,
    InfoBar, InfoBarPosition, BodyLabel, SubtitleLabel, CaptionLabel,
    StrongBodyLabel, TitleLabel, FluentIcon as FIF, MessageBox, ComboBox
)

from backend.everything_cli import EverythingCLI
from backend.scanner_engine import ScannerEngine, AppDataItem
from backend.cleaner_engine import CleanerEngine
from ui_fluent.formatters import format_size

class ScanWorker(QThread):
    progress = pyqtSignal(float, str, int)
    item_found = pyqtSignal(object)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, scanner: ScannerEngine, targets: dict, exclude_windows: bool = True):
        super().__init__()
        self.scanner = scanner
        self.targets = targets
        self.exclude_windows = exclude_windows

    def run(self):
        try:
            results = self.scanner.scan_roots(
                targets=self.targets,
                progress_callback=lambda pct, folder, count: self.progress.emit(pct, folder, count),
                item_callback=lambda it: self.item_found.emit(it),
                exclude_windows=self.exclude_windows
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class ScannerInterface(QWidget):
    def __init__(self, scanner: ScannerEngine, parent=None):
        super().__init__(parent)
        self.scanner = scanner
        self.setObjectName("scannerInterface")

        self.items: list[AppDataItem] = []
        self.item_paths: set[str] = set()
        self.filtered_items: list[AppDataItem] = []
        self.current_filter = "ORPHANED"  # "ORPHANED", "INSTALLED", "PROTECTED", "ALL"
        self.sort_column = 3              # Default: Size column
        self.sort_ascending = False       # Default: Largest first (Descending)
        self.worker: ScanWorker = None
        self.is_scanning: bool = False
        self.scanned_targets: set[str] = set()
        self.has_scanned: bool = False
        self.is_continuation_scan: bool = False
        self.current_scan_targets: list[str] = []

        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(36, 24, 36, 24)
        self.main_layout.setSpacing(14)

        # -----------------------------------------------------------------
        # 1. Header & Title Section
        # -----------------------------------------------------------------
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        self.lbl_title = TitleLabel("AppData Orphan Cleaner", self)
        self.lbl_subtitle = CaptionLabel("Find and safely remove abandoned application data using Voidtools Everything CLI", self)
        self.lbl_subtitle.setTextColor("#94A3B8", "#64748B")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch(1)

        # Everything CLI Status Pill
        self.btn_status = PushButton("Everything: Checking...", self)
        self.btn_status.setIcon(FIF.SYNC)
        self.btn_status.setEnabled(False)
        header_layout.addWidget(self.btn_status)

        self.main_layout.addLayout(header_layout)

        # -----------------------------------------------------------------
        # 2. Scan Configuration Card
        # -----------------------------------------------------------------
        self.config_card = CardWidget(self)
        config_layout = QVBoxLayout(self.config_card)
        config_layout.setContentsMargins(18, 14, 18, 14)
        config_layout.setSpacing(10)

        top_config = QHBoxLayout()
        lbl_scope = StrongBodyLabel("Scan Targets:", self.config_card)
        top_config.addWidget(lbl_scope)

        self.chk_roaming = CheckBox("Roaming", self.config_card)
        self.chk_roaming.setToolTip("%APPDATA% - Roaming profile application data")
        self.chk_roaming.setChecked(True)
        top_config.addWidget(self.chk_roaming)

        self.chk_local = CheckBox("Local", self.config_card)
        self.chk_local.setToolTip("%LOCALAPPDATA% - Machine-local application cache and data")
        self.chk_local.setChecked(True)
        top_config.addWidget(self.chk_local)

        self.chk_locallow = CheckBox("LocalLow", self.config_card)
        self.chk_locallow.setToolTip("%USERPROFILE%\\AppData\\LocalLow - Low-integrity application data")
        top_config.addWidget(self.chk_locallow)

        self.chk_programdata = CheckBox("ProgramData", self.config_card)
        self.chk_programdata.setToolTip("%PROGRAMDATA% - Shared all-users application data")
        top_config.addWidget(self.chk_programdata)

        # Condition: Exclude Windows system and Microsoft folders
        self.chk_exclude_windows = CheckBox("Exclude Windows Folders", self.config_card)
        self.chk_exclude_windows.setChecked(True)
        self.chk_exclude_windows.setToolTip("Do not include Windows OS, Microsoft system components, or framework caches in search")
        self.chk_exclude_windows.stateChanged.connect(self._on_exclude_windows_toggled)
        top_config.addWidget(self.chk_exclude_windows)

        # Connect target checkboxes for dynamic state and button updates
        self.chk_roaming.stateChanged.connect(lambda: self._on_target_checkbox_changed("roaming", self.chk_roaming.isChecked()))
        self.chk_local.stateChanged.connect(lambda: self._on_target_checkbox_changed("local", self.chk_local.isChecked()))
        self.chk_locallow.stateChanged.connect(lambda: self._on_target_checkbox_changed("locallow", self.chk_locallow.isChecked()))
        self.chk_programdata.stateChanged.connect(lambda: self._on_target_checkbox_changed("programdata", self.chk_programdata.isChecked()))

        top_config.addStretch(1)

        # Scan buttons
        self.btn_start_scan = PrimaryPushButton("Start Scan", self.config_card)
        self.btn_start_scan.setIcon(FIF.PLAY)
        self.btn_start_scan.clicked.connect(self._on_start_or_continue_scan)
        top_config.addWidget(self.btn_start_scan)

        self.btn_new_scan = PushButton("New Scan", self.config_card)
        self.btn_new_scan.setIcon(FIF.SYNC)
        self.btn_new_scan.setToolTip("Clear all results and re-scan all selected targets from scratch")
        self.btn_new_scan.setVisible(False)
        self.btn_new_scan.clicked.connect(self._start_new_scan)
        top_config.addWidget(self.btn_new_scan)

        self.btn_stop_scan = PushButton("Stop Scan", self.config_card)
        self.btn_stop_scan.setIcon(FIF.CANCEL)
        self.btn_stop_scan.setEnabled(False)
        self.btn_stop_scan.clicked.connect(self._stop_scan)
        top_config.addWidget(self.btn_stop_scan)

        config_layout.addLayout(top_config)

        # Progress bar & status label
        self.progress_bar = ProgressBar(self.config_card)
        self.progress_bar.setValue(0)
        config_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = CaptionLabel("Ready to scan your system.", self.config_card)
        self.lbl_progress_status.setTextColor("#94A3B8", "#64748B")
        config_layout.addWidget(self.lbl_progress_status)

        self.main_layout.addWidget(self.config_card)

        # -----------------------------------------------------------------
        # 3. Metrics Overview Cards
        # -----------------------------------------------------------------
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_total = self._create_metric_card("Total Scanned", "0", "folders")
        self.card_orphaned = self._create_metric_card("Orphaned Detected", "0", "safe to clean", accent="#F87171")
        self.card_reclaimable = self._create_metric_card("Reclaimable Space", "0 MB", "potential gain", accent="#38BDF8")
        self.card_selected = self._create_metric_card("Selected for Cleanup", "0 B", "0 folders selected", accent="#4ADE80")

        metrics_layout.addWidget(self.card_total)
        metrics_layout.addWidget(self.card_orphaned)
        metrics_layout.addWidget(self.card_reclaimable)
        metrics_layout.addWidget(self.card_selected)

        self.main_layout.addLayout(metrics_layout)

        # -----------------------------------------------------------------
        # 4. Filters, Search & Selection Toolbar (Responsive Balanced Design)
        # -----------------------------------------------------------------
        toolbar_container = QVBoxLayout()
        toolbar_container.setSpacing(10)

        # Row 1: Search (Expanding) & Filter Category Tabs (Anchor Right)
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(12)

        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("Search folders or applications...")
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_box.setMinimumWidth(200)
        self.search_box.textChanged.connect(self._apply_filter)
        row1_layout.addWidget(self.search_box, 1)

        self.pivot = SegmentedWidget(self)
        self.pivot.addItem("orphaned", "Orphaned", onClick=lambda: self._set_filter("ORPHANED"))
        self.pivot.addItem("installed", "Installed", onClick=lambda: self._set_filter("INSTALLED"))
        self.pivot.addItem("protected", "Protected", onClick=lambda: self._set_filter("PROTECTED"))
        self.pivot.addItem("all", "All Folders", onClick=lambda: self._set_filter("ALL"))
        self.pivot.setCurrentItem("orphaned")
        row1_layout.addWidget(self.pivot, 0)

        toolbar_container.addLayout(row1_layout)

        # Row 2: Sort Controls (Left) & Selection Actions (Right)
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)

        lbl_sort = CaptionLabel("Sort by:", self)
        lbl_sort.setTextColor("#94A3B8", "#64748B")
        row2_layout.addWidget(lbl_sort)

        self.combo_sort = ComboBox(self)
        self.combo_sort.addItems([
            "Size (Largest First)",
            "Size (Smallest First)",
            "Name (A → Z)",
            "Name (Z → A)",
            "Status (Orphaned First)",
            "Status (Installed First)",
            "Scope (Roaming First)",
            "Selected First"
        ])
        self.combo_sort.setCurrentText("Size (Largest First)")
        self.combo_sort.setFixedWidth(200)
        self.combo_sort.currentTextChanged.connect(self._on_sort_combo_changed)
        row2_layout.addWidget(self.combo_sort)

        self.btn_sort_direction = ToolButton(FIF.DOWN, self)
        self.btn_sort_direction.setToolTip("Toggle Sort Order (Ascending / Descending)")
        self.btn_sort_direction.clicked.connect(self._toggle_sort_direction)
        row2_layout.addWidget(self.btn_sort_direction)

        row2_layout.addStretch(1)

        self.btn_sel_orphaned = PushButton("Select Orphaned", self)
        self.btn_sel_orphaned.clicked.connect(self._select_orphaned)
        row2_layout.addWidget(self.btn_sel_orphaned)

        self.btn_sel_all = PushButton("Select All", self)
        self.btn_sel_all.clicked.connect(self._select_all)
        row2_layout.addWidget(self.btn_sel_all)

        self.btn_desel_all = PushButton("Deselect All", self)
        self.btn_desel_all.clicked.connect(self._deselect_all)
        row2_layout.addWidget(self.btn_desel_all)

        toolbar_container.addLayout(row2_layout)

        self.main_layout.addLayout(toolbar_container)

        # -----------------------------------------------------------------
        # 5. Results Table
        # -----------------------------------------------------------------
        self.table = TableWidget(self)
        self.table.setColumnCount(7)
        self.base_headers = [
            "Select", "Folder Name", "Scope", "Size", "Status", "Actions", "Detection Evidence"
        ]
        self.table.setHorizontalHeaderLabels(self.base_headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)            # Select
        self.table.setColumnWidth(0, 64)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Folder Name (Expands proportionally!)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Scope
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Size
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Status
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Actions
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)          # Detection Evidence (Expands proportionally!)

        # Enable interactive header clicks for Ascending/Descending sorting
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self._update_header_labels()

        self.main_layout.addWidget(self.table, 1)

        # -----------------------------------------------------------------
        # 6. Bottom Action Command Bar
        # -----------------------------------------------------------------
        self.bottom_card = CardWidget(self)
        bottom_layout = QHBoxLayout(self.bottom_card)
        bottom_layout.setContentsMargins(18, 10, 18, 10)

        self.lbl_bottom_stats = BodyLabel("Ready. Select orphaned items to clean.", self.bottom_card)
        bottom_layout.addWidget(self.lbl_bottom_stats)

        bottom_layout.addStretch(1)

        self.btn_recycle_clean = PrimaryPushButton("Move Selected to Recycle Bin (Safe)", self.bottom_card)
        self.btn_recycle_clean.setIcon(FIF.DELETE)
        self.btn_recycle_clean.clicked.connect(self._confirm_recycle_clean)
        bottom_layout.addWidget(self.btn_recycle_clean)

        self.btn_perm_clean = PushButton("Permanently Delete", self.bottom_card)
        self.btn_perm_clean.setIcon(FIF.CANCEL)
        self.btn_perm_clean.clicked.connect(self._confirm_perm_clean)
        bottom_layout.addWidget(self.btn_perm_clean)

        self.main_layout.addWidget(self.bottom_card)

        # Refresh Everything status badge
        self.update_everything_status()
        self._update_scan_buttons()

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
        lbl_s.setTextColor("#64748B", "#94A3B8")
        card.sub_label = lbl_s
        lay.addWidget(lbl_s)

        return card

    def update_everything_status(self):
        if self.scanner.everything_cli.is_available:
            self.btn_status.setText("Everything Connected")
            self.btn_status.setIcon(FIF.ACCEPT)
            self.btn_status.setStyleSheet("color: #4ADE80; font-weight: bold;")
        else:
            self.btn_status.setText("Everything Disconnected")
            self.btn_status.setIcon(FIF.CANCEL)
            self.btn_status.setStyleSheet("color: #F87171; font-weight: bold;")

    def _set_filter(self, filter_name: str):
        self.current_filter = filter_name
        self._apply_filter()

    def _get_current_targets(self) -> dict[str, bool]:
        return {
            "roaming": self.chk_roaming.isChecked(),
            "local": self.chk_local.isChecked(),
            "locallow": self.chk_locallow.isChecked(),
            "programdata": self.chk_programdata.isChecked()
        }

    def _set_checkboxes_enabled(self, enabled: bool):
        self.chk_roaming.setEnabled(enabled)
        self.chk_local.setEnabled(enabled)
        self.chk_locallow.setEnabled(enabled)
        self.chk_programdata.setEnabled(enabled)
        if hasattr(self, 'chk_exclude_windows'):
            self.chk_exclude_windows.setEnabled(enabled)

    def _on_exclude_windows_toggled(self):
        """Called when the 'Exclude Windows Folders' condition checkbox is toggled."""
        self._update_metrics()
        self._apply_filter()

    def _on_target_checkbox_changed(self, target_key: str, is_checked: bool):
        if not is_checked and target_key in self.scanned_targets:
            # If user unchecks an already scanned target, remove its items from results
            self.scanned_targets.discard(target_key)
            self.items = [i for i in self.items if i.root_type.lower() != target_key.lower()]
            self.item_paths = {i.path for i in self.items}
            self._update_metrics()
            self._apply_filter()

        self._update_scan_buttons()

    def _update_scan_buttons(self):
        targets = self._get_current_targets()
        checked = [k for k, v in targets.items() if v]
        unscanned_checked = [k for k in checked if k not in self.scanned_targets]

        if self.is_scanning:
            self.btn_start_scan.setEnabled(False)
            self.btn_new_scan.setEnabled(False)
            self.btn_stop_scan.setEnabled(True)
            self._set_checkboxes_enabled(False)
            return

        self._set_checkboxes_enabled(True)
        self.btn_stop_scan.setEnabled(False)

        if not self.has_scanned:
            self.btn_start_scan.setText("Start Scan")
            self.btn_start_scan.setIcon(FIF.PLAY)
            self.btn_start_scan.setEnabled(len(checked) > 0)
            self.btn_new_scan.setVisible(False)
        else:
            self.btn_new_scan.setVisible(True)
            self.btn_new_scan.setEnabled(len(checked) > 0)

            if unscanned_checked:
                names = [t.capitalize() for t in unscanned_checked]
                if len(names) == 1:
                    self.btn_start_scan.setText(f"Scan {names[0]}")
                else:
                    self.btn_start_scan.setText("Continue Scan")
                self.btn_start_scan.setIcon(FIF.PLAY)
                self.btn_start_scan.setEnabled(True)
            else:
                self.btn_start_scan.setText("All Scanned")
                self.btn_start_scan.setIcon(FIF.ACCEPT)
                self.btn_start_scan.setEnabled(False)

    def _on_start_or_continue_scan(self):
        targets = self._get_current_targets()
        checked = [k for k, v in targets.items() if v]
        if not checked:
            InfoBar.warning(
                title="No Target Selected",
                content="Please select at least one scan directory.",
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        if not self.has_scanned:
            self._execute_scan(targets=targets, is_continuation=False)
        else:
            unscanned_checked = [k for k in checked if k not in self.scanned_targets]
            if not unscanned_checked:
                return
            continuation_targets = {k: (k in unscanned_checked) for k in targets}
            self._execute_scan(targets=continuation_targets, is_continuation=True)

    def _start_new_scan(self):
        targets = self._get_current_targets()
        checked = [k for k, v in targets.items() if v]
        if not checked:
            InfoBar.warning(
                title="No Target Selected",
                content="Please select at least one scan directory.",
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Clear previous scan results and scanned targets
        self.items = []
        self.item_paths = set()
        self.filtered_items = []
        self.table.setRowCount(0)
        self.scanned_targets.clear()
        self._update_metrics()

        self._execute_scan(targets=targets, is_continuation=False)

    def _execute_scan(self, targets: dict, is_continuation: bool):
        self.is_scanning = True
        self.is_continuation_scan = is_continuation
        self.current_scan_targets = [k for k, v in targets.items() if v]

        self._update_scan_buttons()
        self.progress_bar.setValue(0)

        target_names = ", ".join(t.capitalize() for t in self.current_scan_targets)
        if is_continuation:
            self.lbl_progress_status.setText(f"Scanning additional target(s): {target_names}...")
        else:
            self.lbl_progress_status.setText(f"Scanning targets: {target_names}...")

        exclude_windows = self.chk_exclude_windows.isChecked() if hasattr(self, 'chk_exclude_windows') else True
        self.worker = ScanWorker(self.scanner, targets, exclude_windows=exclude_windows)
        self.worker.progress.connect(self._on_scan_progress)
        self.worker.item_found.connect(self._on_item_streamed)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.error.connect(self._on_scan_error)
        self.worker.start()

    def _stop_scan(self):
        if self.worker and self.worker.isRunning():
            self.scanner.cancel_scan()
            self.lbl_progress_status.setText("Stopping scan...")
            self.btn_stop_scan.setEnabled(False)

    def _on_scan_progress(self, pct: float, folder: str, count: int):
        self.progress_bar.setValue(int(pct * 100))
        disp = folder if len(folder) < 35 else folder[:32] + "..."
        self.lbl_progress_status.setText(f"Inspecting: {disp} ({count} folders analyzed)")

    def _on_item_streamed(self, item: AppDataItem):
        """Streams each scanned item into the table in real-time as it is evaluated."""
        if item.path in self.item_paths:
            return

        # Check if item passes the exclude windows condition
        if hasattr(self, 'chk_exclude_windows') and self.chk_exclude_windows.isChecked():
            if self.scanner.whitelist_manager.is_windows_related(item.name, item.path):
                return

        self.item_paths.add(item.path)
        self.items.append(item)
        self._update_metrics()

        # Check if item passes the active category filter
        cat = self.current_filter
        if cat != "ALL" and item.status != cat:
            return

        # Check if item passes the search query
        query = self.search_box.text().strip().lower()
        if query and (query not in item.name.lower() and query not in item.path.lower()):
            return

        # Append to filtered items and append row directly into the table
        self.filtered_items.append(item)
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self._render_row_cells(row_idx, item)
        self.table.scrollToBottom()

    def _on_scan_finished(self, results: list):
        self.is_scanning = False
        is_cancelled = getattr(self.scanner, "_is_cancelled", False)
        self.has_scanned = True

        if not is_cancelled:
            self.progress_bar.setValue(100)
            for t in self.current_scan_targets:
                self.scanned_targets.add(t)
        else:
            self.lbl_progress_status.setText(f"Scan stopped. {len(self.items)} folders retained.")
            InfoBar.info(
                title="Scan Stopped",
                content=f"Scan was stopped by user. {len(self.items)} folders analyzed so far.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

        if not self.is_continuation_scan and not is_cancelled:
            self.items = results
            self.item_paths = {i.path for i in results}

        self._update_metrics()
        self._apply_filter()
        self.table.scrollToTop()
        self._update_scan_buttons()

        if not is_cancelled:
            orphaned_in_batch = sum(1 for i in results if i.status == "ORPHANED")
            if self.is_continuation_scan:
                target_str = ", ".join(t.capitalize() for t in self.current_scan_targets)
                msg = f"Found {orphaned_in_batch} orphaned folder(s) in {target_str}. Total analyzed: {len(self.items)}."
            else:
                orphaned_total = sum(1 for i in self.items if i.status == "ORPHANED")
                msg = f"Scan complete. Found {orphaned_total} orphaned folders out of {len(self.items)} total items."

            self.lbl_progress_status.setText(msg)
            InfoBar.success(
                title="Scan Complete",
                content=msg,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )

    def _on_scan_error(self, err: str):
        self.is_scanning = False
        self._update_scan_buttons()
        self.lbl_progress_status.setText("Scan failed.")
        InfoBar.error(
            title="Scan Error",
            content=err,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )

    def _update_metrics(self):
        exclude_win = self.chk_exclude_windows.isChecked() if hasattr(self, 'chk_exclude_windows') else True
        active_items = [
            i for i in self.items
            if not (exclude_win and self.scanner.whitelist_manager.is_windows_related(i.name, i.path))
        ]

        total = len(active_items)
        orphaned = [i for i in active_items if i.status == "ORPHANED"]
        reclaimable_bytes = sum(i.size for i in orphaned)
        selected = [i for i in active_items if i.selected and i.status != "PROTECTED"]
        selected_bytes = sum(i.size for i in selected)

        self.card_total.value_label.setText(str(total))
        self.card_orphaned.value_label.setText(str(len(orphaned)))
        self.card_reclaimable.value_label.setText(format_size(reclaimable_bytes))
        self.card_selected.value_label.setText(format_size(selected_bytes))
        self.card_selected.sub_label.setText(f"{len(selected)} folders selected")

        self.lbl_bottom_stats.setText(
            f"Selected: {len(selected)} folders ({format_size(selected_bytes)}) ready for cleanup."
        )

    def _apply_filter(self):
        query = self.search_box.text().strip().lower()
        cat = self.current_filter
        exclude_win = self.chk_exclude_windows.isChecked() if hasattr(self, 'chk_exclude_windows') else True

        self.filtered_items = []
        for item in self.items:
            if exclude_win and self.scanner.whitelist_manager.is_windows_related(item.name, item.path):
                continue
            if cat != "ALL" and item.status != cat:
                continue
            if query and (query not in item.name.lower() and query not in item.path.lower()):
                continue
            self.filtered_items.append(item)

        self._sort_filtered_items()
        self._update_header_labels()
        self._populate_table()

    def _sort_filtered_items(self):
        """Sorts filtered_items according to self.sort_column and self.sort_ascending."""
        def get_key(item: AppDataItem):
            if self.sort_column == 0:
                return (item.selected, item.size)
            elif self.sort_column == 1:
                return item.name.lower()
            elif self.sort_column == 2:
                return item.root_type.lower()
            elif self.sort_column == 3:
                return item.size
            elif self.sort_column == 4:
                order_map = {"ORPHANED": 0, "INSTALLED": 1, "PROTECTED": 2}
                return (order_map.get(item.status, 9), item.size)
            elif self.sort_column == 6:
                return (item.evidence[0] if item.evidence else "").lower()
            return ""

        self.filtered_items.sort(key=get_key, reverse=not self.sort_ascending)

    def _update_header_labels(self):
        """Updates header text with ascending/descending arrows."""
        labels = []
        for idx, base in enumerate(self.base_headers):
            if idx == self.sort_column:
                arrow = "▲" if self.sort_ascending else "▼"
                labels.append(f"{base} {arrow}")
            else:
                labels.append(base)
        self.table.setHorizontalHeaderLabels(labels)
        order = Qt.SortOrder.AscendingOrder if self.sort_ascending else Qt.SortOrder.DescendingOrder
        self.table.horizontalHeader().setSortIndicator(self.sort_column, order)

    def _on_header_clicked(self, logical_index: int):
        """Called when the user clicks on any column header."""
        # Col 5 is Actions; no sorting on action buttons
        if logical_index == 5:
            return

        if self.sort_column == logical_index:
            # Toggle order
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = logical_index
            # When sorting by Size or Status or Select, default to Descending (Largest / Orphaned / Selected first)
            if logical_index in [0, 3, 4]:
                self.sort_ascending = False
            else:
                self.sort_ascending = True

        self._sync_combo_from_header()
        self._sort_filtered_items()
        self._update_header_labels()
        self._populate_table()

    def _toggle_sort_direction(self):
        """Toggles current sort between Ascending and Descending."""
        self.sort_ascending = not self.sort_ascending
        self._sync_combo_from_header()
        self._sort_filtered_items()
        self._update_header_labels()
        self._populate_table()

    def _sync_combo_from_header(self):
        """Syncs the ComboBox dropdown and sort button without triggering change events."""
        self.combo_sort.blockSignals(True)
        if self.sort_column == 3:
            self.combo_sort.setCurrentText("Size (Largest First)" if not self.sort_ascending else "Size (Smallest First)")
        elif self.sort_column == 1:
            self.combo_sort.setCurrentText("Name (A → Z)" if self.sort_ascending else "Name (Z → A)")
        elif self.sort_column == 4:
            self.combo_sort.setCurrentText("Status (Orphaned First)" if not self.sort_ascending else "Status (Installed First)")
        elif self.sort_column == 2:
            self.combo_sort.setCurrentText("Scope (Roaming First)")
        elif self.sort_column == 0:
            self.combo_sort.setCurrentText("Selected First")
        self.combo_sort.blockSignals(False)

        # Update sort direction icon
        if hasattr(self, 'btn_sort_direction'):
            self.btn_sort_direction.setIcon(FIF.UP if self.sort_ascending else FIF.DOWN)

    def _on_sort_combo_changed(self, text: str):
        """Called when the user chooses a sort preset from the ComboBox."""
        if "Size (Largest First)" in text:
            self.sort_column = 3
            self.sort_ascending = False
        elif "Size (Smallest First)" in text:
            self.sort_column = 3
            self.sort_ascending = True
        elif "Name (A → Z)" in text:
            self.sort_column = 1
            self.sort_ascending = True
        elif "Name (Z → A)" in text:
            self.sort_column = 1
            self.sort_ascending = False
        elif "Status (Orphaned First)" in text:
            self.sort_column = 4
            self.sort_ascending = False
        elif "Status (Installed First)" in text:
            self.sort_column = 4
            self.sort_ascending = True
        elif "Scope" in text:
            self.sort_column = 2
            self.sort_ascending = True
        elif "Selected First" in text:
            self.sort_column = 0
            self.sort_ascending = False

        if hasattr(self, 'btn_sort_direction'):
            self.btn_sort_direction.setIcon(FIF.UP if self.sort_ascending else FIF.DOWN)

        self._sort_filtered_items()
        self._update_header_labels()
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.filtered_items))

        for row_idx, item in enumerate(self.filtered_items):
            self._render_row_cells(row_idx, item)

    def _render_row_cells(self, row_idx: int, item: AppDataItem):
        """Builds and attaches widgets/items for all columns in a given row."""
        # Col 0: Checkbox
        chk = CheckBox(self.table)
        chk.setFixedSize(22, 22)
        chk.setChecked(item.selected)
        chk.setEnabled(item.status != "PROTECTED")
        chk.stateChanged.connect(lambda _, it=item, c=chk: self._on_item_check(it, c.isChecked()))
        chk_container = QWidget()
        chk_lay = QHBoxLayout(chk_container)
        chk_lay.addWidget(chk)
        chk_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        chk_lay.setContentsMargins(15, 0, 8, 0)
        self.table.setCellWidget(row_idx, 0, chk_container)

        # Col 1: Name
        name_item = QTableWidgetItem(item.name)
        name_item.setToolTip(item.path)
        self.table.setItem(row_idx, 1, name_item)

        # Col 2: Root (Scope)
        root_item = QTableWidgetItem(item.root_type)
        self.table.setItem(row_idx, 2, root_item)

        # Col 3: Size
        size_item = QTableWidgetItem(format_size(item.size))
        self.table.setItem(row_idx, 3, size_item)

        # Col 4: Status Badge
        status_widget = QWidget()
        status_lay = QHBoxLayout(status_widget)
        status_lay.setContentsMargins(4, 2, 4, 2)
        status_lbl = QLabel(f" {item.status} ")
        if item.status == "ORPHANED":
            status_lbl.setStyleSheet("background: #7A2E2E; color: #FFA5A5; border-radius: 4px; font-weight: bold; padding: 2px 6px;")
        elif item.status == "INSTALLED":
            status_lbl.setStyleSheet("background: #1E4D2B; color: #A3E635; border-radius: 4px; font-weight: bold; padding: 2px 6px;")
        else:
            status_lbl.setStyleSheet("background: #1E3A5F; color: #93C5FD; border-radius: 4px; font-weight: bold; padding: 2px 6px;")
        status_lay.addWidget(status_lbl)
        status_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row_idx, 4, status_widget)

        # Col 5: Actions
        actions_widget = QWidget()
        act_lay = QHBoxLayout(actions_widget)
        act_lay.setContentsMargins(2, 2, 2, 2)
        act_lay.setSpacing(4)

        btn_open = ToolButton(FIF.FOLDER, actions_widget)
        btn_open.setToolTip("Open in File Explorer")
        btn_open.clicked.connect(lambda _, p=item.path: self._open_explorer(p))
        act_lay.addWidget(btn_open)

        if item.status != "PROTECTED":
            btn_wl = ToolButton(FIF.ACCEPT, actions_widget)
            btn_wl.setToolTip("Add to Whitelist (Protect)")
            btn_wl.clicked.connect(lambda _, n=item.name: self._whitelist_folder(n))
            act_lay.addWidget(btn_wl)

        self.table.setCellWidget(row_idx, 5, actions_widget)

        # Col 6: Detection Evidence
        evidence_str = item.evidence[0] if item.evidence else "No data"
        ev_item = QTableWidgetItem(evidence_str)
        ev_item.setToolTip(item.path + "\n" + "\n".join(item.evidence))
        self.table.setItem(row_idx, 6, ev_item)

    def _on_item_check(self, item: AppDataItem, is_checked: bool):
        item.selected = bool(is_checked)
        self._update_metrics()

    def _select_orphaned(self):
        for item in self.items:
            item.selected = (item.status == "ORPHANED")
        self._update_metrics()
        self._populate_table()

    def _select_all(self):
        for item in self.filtered_items:
            if item.status != "PROTECTED":
                item.selected = True
        self._update_metrics()
        self._populate_table()

    def _deselect_all(self):
        for item in self.items:
            item.selected = False
        self._update_metrics()
        self._populate_table()

    def _open_explorer(self, path: str):
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                InfoBar.error(title="Error", content=str(e), parent=self)
        else:
            InfoBar.warning(title="Not Found", content="Directory does not exist.", parent=self)

    def _whitelist_folder(self, folder_name: str):
        w = MessageBox(
            "Confirm Whitelist",
            f"Add '{folder_name}' to user whitelist?\nIt will be permanently protected from scanning and deletion.",
            self.window()
        )
        if w.exec():
            self.scanner.whitelist_manager.add(folder_name)
            for item in self.items:
                if item.name.lower() == folder_name.lower():
                    item.status = "PROTECTED"
                    item.selected = False
            self._update_metrics()
            self._apply_filter()
            InfoBar.success(title="Whitelisted", content=f"'{folder_name}' is now protected.", parent=self)

    def _confirm_recycle_clean(self):
        selected = [i for i in self.items if i.selected and i.status != "PROTECTED"]
        if not selected:
            InfoBar.warning(title="No Selection", content="Please select at least one folder to delete.", parent=self)
            return

        size_str = format_size(sum(i.size for i in selected))
        w = MessageBox(
            "Recycle Bin Safe Cleanup",
            f"Are you sure you want to move {len(selected)} orphaned folder(s) ({size_str}) to the Windows Recycle Bin?\n\n"
            "You can restore them from the Recycle Bin if needed.",
            self.window()
        )
        if w.exec():
            self._execute_cleanup(selected, use_recycle_bin=True)

    def _confirm_perm_clean(self):
        selected = [i for i in self.items if i.selected and i.status != "PROTECTED"]
        if not selected:
            InfoBar.warning(title="No Selection", content="Please select at least one folder to delete.", parent=self)
            return

        size_str = format_size(sum(i.size for i in selected))
        w = MessageBox(
            "⚠️ Permanent Deletion Warning",
            f"This will PERMANENTLY DELETE {len(selected)} folder(s) ({size_str}) from disk.\n"
            "These files CANNOT be restored from the Recycle Bin.\n\nProceed?",
            self.window()
        )
        if w.exec():
            self._execute_cleanup(selected, use_recycle_bin=False)

    def _execute_cleanup(self, selected_items: list, use_recycle_bin: bool):
        items_dict = [{"name": i.name, "path": i.path, "size": i.size} for i in selected_items]
        res = CleanerEngine.delete_items(items_dict, use_recycle_bin=use_recycle_bin)

        deleted_paths = {i["path"] for i in items_dict}
        self.items = [i for i in self.items if i.path not in deleted_paths or os.path.exists(i.path)]
        self.item_paths = {i.path for i in self.items}

        self._update_metrics()
        self._apply_filter()

        action_word = "moved to the Recycle Bin" if use_recycle_bin else "permanently deleted"
        freed_str = format_size(res["freed_bytes"])
        InfoBar.success(
            title="Cleanup Finished",
            content=f"Successfully {action_word} {res['success_count']} folders! Freed {freed_str} of disk space.",
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
