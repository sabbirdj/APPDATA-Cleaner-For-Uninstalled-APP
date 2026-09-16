from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem
)
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton, ToolButton, LineEdit,
    TableWidget, TitleLabel, SubtitleLabel, CaptionLabel, BodyLabel,
    StrongBodyLabel, InfoBar, InfoBarPosition, FluentIcon as FIF, MessageBox
)
from backend.whitelist import WhitelistManager

class WhitelistInterface(QWidget):
    def __init__(self, whitelist_manager: WhitelistManager, parent=None):
        super().__init__(parent)
        self.whitelist_manager = whitelist_manager
        self.setObjectName("whitelistInterface")

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = TitleLabel("Safety Whitelist Management", self)
        lbl_sub = CaptionLabel("Protected folders are excluded from scans and cannot be deleted by the cleaner.", self)
        lbl_sub.setTextColor("#94A3B8", "#64748B")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Add Rule Card
        add_card = CardWidget(self)
        add_lay = QHBoxLayout(add_card)
        add_lay.setContentsMargins(18, 14, 18, 14)

        self.input_folder = LineEdit(add_card)
        self.input_folder.setPlaceholderText("Enter folder name to protect (e.g., 'MyCustomGame' or 'AndroidStudio')...")
        self.input_folder.returnPressed.connect(self._add_rule)
        add_lay.addWidget(self.input_folder, 1)

        btn_add = PrimaryPushButton("Protect Folder", add_card)
        btn_add.setIcon(FIF.ACCEPT)
        btn_add.clicked.connect(self._add_rule)
        add_lay.addWidget(btn_add)

        layout.addWidget(add_card)

        # User Custom Rules Table
        self.user_card = CardWidget(self)
        user_lay = QVBoxLayout(self.user_card)
        user_lay.setContentsMargins(18, 14, 18, 14)

        user_header = QHBoxLayout()
        user_title = StrongBodyLabel("Custom Protected Folders", self.user_card)
        user_header.addWidget(user_title)
        user_header.addStretch(1)
        self.lbl_user_count = CaptionLabel("0 custom rules", self.user_card)
        self.lbl_user_count.setTextColor("#94A3B8", "#64748B")
        user_header.addWidget(self.lbl_user_count)
        user_lay.addLayout(user_header)

        self.user_table = TableWidget(self.user_card)
        self.user_table.setColumnCount(3)
        self.user_table.setHorizontalHeaderLabels(["Folder Name", "Status", "Action"])
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        user_lay.addWidget(self.user_table)

        layout.addWidget(self.user_card, 1)

        # Built-in Protected Notice
        built_card = CardWidget(self)
        built_lay = QVBoxLayout(built_card)
        built_lay.setContentsMargins(18, 14, 18, 14)

        built_title = StrongBodyLabel("Built-in System Safety List", built_card)
        built_lay.addWidget(built_title)

        builtin_items = self.whitelist_manager.get_builtin_items()
        summary_text = f"Includes {len(builtin_items)} core system, GPU driver, package manager, and Windows store components: " + ", ".join(builtin_items[:18]) + "..."
        built_desc = CaptionLabel(summary_text, built_card)
        built_desc.setTextColor("#64748B", "#94A3B8")
        built_lay.addWidget(built_desc)

        layout.addWidget(built_card)

        self.refresh_rules()

    def refresh_rules(self):
        custom_items = self.whitelist_manager.get_custom_items()
        self.lbl_user_count.setText(f"{len(custom_items)} custom rules active")

        self.user_table.setRowCount(len(custom_items))
        for idx, item in enumerate(custom_items):
            # Name
            name_item = QTableWidgetItem(f"🛡  {item}")
            self.user_table.setItem(idx, 0, name_item)

            # Status
            status_item = QTableWidgetItem("User Protected")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.user_table.setItem(idx, 1, status_item)

            # Action
            btn_del = PushButton("Remove", self.user_table)
            btn_del.setIcon(FIF.DELETE)
            btn_del.clicked.connect(lambda _, name=item: self._remove_rule(name))
            self.user_table.setCellWidget(idx, 2, btn_del)

    def _add_rule(self):
        val = self.input_folder.text().strip()
        if not val:
            return

        if self.whitelist_manager.add(val):
            self.input_folder.clear()
            self.refresh_rules()
            InfoBar.success(
                title="Rule Added",
                content=f"'{val}' is now protected from cleaning.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.warning(
                title="Already Exists",
                content=f"'{val}' is already in the whitelist.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def _remove_rule(self, name: str):
        if self.whitelist_manager.remove(name):
            self.refresh_rules()
            InfoBar.info(
                title="Rule Removed",
                content=f"'{name}' removed from whitelist.",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
