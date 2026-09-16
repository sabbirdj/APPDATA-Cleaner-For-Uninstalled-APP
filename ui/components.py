import os
import subprocess
import customtkinter as ctk
from typing import Callable, Optional

def format_size(bytes_val: int) -> str:
    """Formats bytes into human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"

class StatusBadge(ctk.CTkFrame):
    """Pill badge showing status with appropriate color."""
    COLORS = {
        "ORPHANED": {"fg": "#7A2E2E", "text": "#FFA5A5", "label": "ORPHANED"},
        "INSTALLED": {"fg": "#1E4D2B", "text": "#A3E635", "label": "INSTALLED"},
        "PROTECTED": {"fg": "#1E3A5F", "text": "#93C5FD", "label": "PROTECTED"},
        "UNKNOWN": {"fg": "#374151", "text": "#9CA3AF", "label": "UNKNOWN"},
    }

    def __init__(self, master, status: str, **kwargs):
        config = self.COLORS.get(status, self.COLORS["UNKNOWN"])
        super().__init__(master, fg_color=config["fg"], corner_radius=12, height=24, **kwargs)
        self.label = ctk.CTkLabel(
            self,
            text=f"  {config['label']}  ",
            text_color=config["text"],
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.label.pack(padx=6, pady=2)

class ItemRow(ctk.CTkFrame):
    """Row widget representing one AppData folder item."""
    def __init__(
        self,
        master,
        item,
        on_toggle: Callable[[bool], None],
        on_open: Callable[[str], None],
        on_whitelist: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, fg_color="#1E293B", corner_radius=8, **kwargs)
        self.item = item
        self.on_toggle = on_toggle

        self.grid_columnconfigure(1, weight=1)

        # 1. Selection Checkbox
        self.checkbox_var = ctk.BooleanVar(value=item.selected)
        self.checkbox = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.checkbox_var,
            width=24,
            command=self._on_check_changed,
            state="disabled" if item.status == "PROTECTED" else "normal"
        )
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8, sticky="w")

        # 2. Folder Info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=4, pady=(8, 2), sticky="w")

        # Name & Root tag
        name_label = ctk.CTkLabel(
            info_frame,
            text=item.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F8FAFC"
        )
        name_label.pack(side="left", padx=(0, 8))

        root_label = ctk.CTkLabel(
            info_frame,
            text=f"({item.root_type})",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        root_label.pack(side="left")

        # Path & Evidence
        evidence_text = item.evidence[0] if item.evidence else ""
        if len(evidence_text) > 75:
            evidence_text = evidence_text[:72] + "..."

        sub_label = ctk.CTkLabel(
            self,
            text=f"{item.path}  •  {evidence_text}",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
            anchor="w"
        )
        sub_label.grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")

        # 3. Stats (Size & Date)
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=0, column=2, rowspan=2, padx=12, pady=8, sticky="e")

        size_label = ctk.CTkLabel(
            stats_frame,
            text=format_size(item.size),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8" if item.size > 10 * 1024 * 1024 else "#CBD5E1"
        )
        size_label.pack(anchor="e")

        date_label = ctk.CTkLabel(
            stats_frame,
            text=item.last_modified or "Unknown date",
            font=ctk.CTkFont(size=10),
            text_color="#64748B"
        )
        date_label.pack(anchor="e")

        # 4. Status Badge
        badge = StatusBadge(self, status=item.status)
        badge.grid(row=0, column=3, rowspan=2, padx=10, pady=8)

        # 5. Quick Action Buttons
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=0, column=4, rowspan=2, padx=(4, 12), pady=8, sticky="e")

        btn_open = ctk.CTkButton(
            actions_frame,
            text="📁",
            width=32,
            height=28,
            fg_color="#334155",
            hover_color="#475569",
            command=lambda: on_open(item.path)
        )
        btn_open.pack(side="left", padx=2)

        if item.status != "PROTECTED":
            btn_wl = ctk.CTkButton(
                actions_frame,
                text="🛡 Whitelist",
                width=80,
                height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#334155",
                hover_color="#475569",
                command=lambda: on_whitelist(item.name)
            )
            btn_wl.pack(side="left", padx=2)

    def _on_check_changed(self):
        val = self.checkbox_var.get()
        self.item.selected = val
        self.on_toggle(val)

    def set_checked(self, checked: bool):
        if self.item.status != "PROTECTED":
            self.checkbox_var.set(checked)
            self.item.selected = checked
