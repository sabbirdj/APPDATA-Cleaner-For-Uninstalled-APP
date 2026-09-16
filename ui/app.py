import os
import sys
import threading
import subprocess
from tkinter import messagebox
import customtkinter as ctk

from backend.everything_cli import EverythingCLI
from backend.scanner_engine import ScannerEngine, AppDataItem
from backend.cleaner_engine import CleanerEngine
from ui.components import ItemRow, format_size
from ui.settings_dialog import SettingsDialog

class AppDataCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AppData Orphan Cleaner — Powered by Everything CLI")
        self.geometry("1100x740")
        self.minsize(920, 600)

        # Initialize Engines
        self.everything_cli = EverythingCLI()
        self.scanner = ScannerEngine(self.everything_cli)

        # State
        self.items: list[AppDataItem] = []
        self.filtered_items: list[AppDataItem] = []
        self.row_widgets: list[ItemRow] = []
        self.is_scanning = False
        self.current_filter = "ORPHANED"  # "ALL", "ORPHANED", "INSTALLED", "PROTECTED"

        self._setup_ui()
        self._update_everything_badge()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Main results area expands

        # ==========================================
        # 1. HEADER BAR
        # ==========================================
        header = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=0, height=70)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=12)

        lbl_title = ctk.CTkLabel(
            title_frame,
            text="🧹 AppData Orphan Cleaner",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#F8FAFC"
        )
        lbl_title.pack(anchor="w")

        lbl_subtitle = ctk.CTkLabel(
            title_frame,
            text="Detect & Clean Abandoned Application Data with Voidtools Everything CLI",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        lbl_subtitle.pack(anchor="w")

        # Top Right Badges & Settings
        top_right = ctk.CTkFrame(header, fg_color="transparent")
        top_right.pack(side="right", padx=20, pady=12)

        self.btn_es_badge = ctk.CTkButton(
            top_right,
            text="● Everything CLI",
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_settings
        )
        self.btn_es_badge.pack(side="left", padx=(0, 10))

        btn_settings = ctk.CTkButton(
            top_right,
            text="⚙ Settings & Whitelist",
            width=150,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self._open_settings
        )
        btn_settings.pack(side="left")

        # ==========================================
        # 2. SCAN CONTROLS & SCOPE
        # ==========================================
        controls_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        controls_frame.grid(row=1, column=0, padx=20, pady=(15, 10), sticky="ew")
        controls_frame.grid_columnconfigure(1, weight=1)

        # Scopes
        scope_box = ctk.CTkFrame(controls_frame, fg_color="transparent")
        scope_box.pack(side="left", padx=15, pady=12)

        lbl_scope = ctk.CTkLabel(scope_box, text="Scan Scope:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_scope.pack(side="left", padx=(0, 10))

        self.chk_roaming = ctk.CTkCheckBox(scope_box, text="Roaming", width=20)
        self.chk_roaming.select()
        self.chk_roaming.pack(side="left", padx=6)

        self.chk_local = ctk.CTkCheckBox(scope_box, text="Local", width=20)
        self.chk_local.select()
        self.chk_local.pack(side="left", padx=6)

        self.chk_locallow = ctk.CTkCheckBox(scope_box, text="LocalLow", width=20)
        self.chk_locallow.pack(side="left", padx=6)

        self.chk_programdata = ctk.CTkCheckBox(scope_box, text="ProgramData", width=20)
        self.chk_programdata.pack(side="left", padx=6)

        # Scan Button & Progress
        scan_action_box = ctk.CTkFrame(controls_frame, fg_color="transparent")
        scan_action_box.pack(side="right", padx=15, pady=12)

        self.lbl_progress = ctk.CTkLabel(
            scan_action_box,
            text="Ready to scan",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        self.lbl_progress.pack(side="left", padx=(0, 12))

        self.btn_scan = ctk.CTkButton(
            scan_action_box,
            text="▶ Start Scan",
            width=120,
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._toggle_scan
        )
        self.btn_scan.pack(side="left")

        # Progress bar (full width strip below controls)
        self.progress_bar = ctk.CTkProgressBar(self, height=4, corner_radius=0)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="sew", padx=20)

        # ==========================================
        # 3. RESULTS & FILTER BAR
        # ==========================================
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_rowconfigure(1, weight=1)

        # Filter bar
        filter_bar = ctk.CTkFrame(main_content, fg_color="transparent")
        filter_bar.grid(row=0, column=0, sticky="ew", pady=(5, 8))
        filter_bar.grid_columnconfigure(0, weight=1)

        # Search box
        self.entry_search = ctk.CTkEntry(
            filter_bar,
            placeholder_text="🔍 Filter by folder or app name...",
            width=280,
            height=34
        )
        self.entry_search.pack(side="left", padx=(0, 12))
        self.entry_search.bind("<KeyRelease>", lambda e: self._apply_filter())

        # Category segmented buttons
        self.seg_filter = ctk.CTkSegmentedButton(
            filter_bar,
            values=["Orphaned", "Installed", "Protected", "All"],
            height=34,
            command=self._on_segment_changed
        )
        self.seg_filter.set("Orphaned")
        self.seg_filter.pack(side="left", padx=4)

        # Selection shortcuts
        btn_sel_orphaned = ctk.CTkButton(
            filter_bar,
            text="Select Orphaned",
            width=115,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self._select_orphaned
        )
        btn_sel_orphaned.pack(side="right", padx=(6, 0))

        btn_desel_all = ctk.CTkButton(
            filter_bar,
            text="Deselect All",
            width=90,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self._deselect_all
        )
        btn_desel_all.pack(side="right", padx=6)

        btn_sel_all = ctk.CTkButton(
            filter_bar,
            text="Select All",
            width=80,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self._select_all
        )
        btn_sel_all.pack(side="right")

        # Scrollable List Frame
        self.scroll_results = ctk.CTkScrollableFrame(
            main_content,
            fg_color="#0F172A",
            corner_radius=10,
            label_text="Scanned Folders"
        )
        self.scroll_results.grid(row=1, column=0, sticky="nsew")

        # Empty state label
        self.lbl_empty_results = ctk.CTkLabel(
            self.scroll_results,
            text="No scan results yet.\nClick 'Start Scan' above to search for orphaned AppData folders.",
            font=ctk.CTkFont(size=14),
            text_color="#64748B"
        )
        self.lbl_empty_results.pack(pady=100)

        # ==========================================
        # 4. BOTTOM ACTION & STATS BAR
        # ==========================================
        bottom_bar = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10, height=60)
        bottom_bar.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Stats Labels
        self.lbl_summary_stats = ctk.CTkLabel(
            bottom_bar,
            text="Items: 0  |  Orphaned: 0  |  Selected: 0 B",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E2E8F0"
        )
        self.lbl_summary_stats.pack(side="left", padx=16, pady=12)

        # Action Buttons
        btn_perm_delete = ctk.CTkButton(
            bottom_bar,
            text="🗑 Permanently Delete",
            height=36,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._confirm_permanent_delete
        )
        btn_perm_delete.pack(side="right", padx=16, pady=12)

        btn_recycle_delete = ctk.CTkButton(
            bottom_bar,
            text="🛡 Move Selected to Recycle Bin",
            height=36,
            fg_color="#15803D",
            hover_color="#166534",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._confirm_recycle_delete
        )
        btn_recycle_delete.pack(side="right", padx=(0, 8), pady=12)

    def _update_everything_badge(self):
        if self.everything_cli.is_available:
            self.btn_es_badge.configure(
                text="● Everything Connected",
                fg_color="#166534",
                hover_color="#14532D"
            )
        else:
            self.btn_es_badge.configure(
                text="▲ Everything Disconnected",
                fg_color="#854D0E",
                hover_color="#713F12"
            )

    def _open_settings(self):
        SettingsDialog(
            self,
            everything_cli=self.everything_cli,
            whitelist_manager=self.scanner.whitelist_manager,
            on_updated=self._on_settings_updated
        )

    def _on_settings_updated(self):
        self._update_everything_badge()
        # Re-evaluate items if items already exist
        if self.items:
            for item in self.items:
                if self.scanner.whitelist_manager.is_protected(item.name, item.path):
                    item.status = "PROTECTED"
                    item.selected = False
            self._apply_filter()

    def _toggle_scan(self):
        if self.is_scanning:
            # Cancel scan
            self.scanner.cancel_scan()
            self.lbl_progress.configure(text="Cancelling scan...")
            self.btn_scan.configure(state="disabled")
        else:
            # Start scan
            targets = {
                "roaming": bool(self.chk_roaming.get()),
                "local": bool(self.chk_local.get()),
                "locallow": bool(self.chk_locallow.get()),
                "programdata": bool(self.chk_programdata.get())
            }
            if not any(targets.values()):
                messagebox.showwarning("No Target Selected", "Please select at least one scan directory.")
                return

            self.is_scanning = True
            self.btn_scan.configure(text="⏹ Stop Scan", fg_color="#DC2626", hover_color="#B91C1C")
            self.progress_bar.set(0)
            self.lbl_progress.configure(text="Starting scan...")

            # Clear old rows
            for w in self.scroll_results.winfo_children():
                w.destroy()
            self.items.clear()
            self.filtered_items.clear()
            self.row_widgets.clear()

            # Start thread
            threading.Thread(target=self._run_scan_thread, args=(targets,), daemon=True).start()

    def _run_scan_thread(self, targets):
        def progress_cb(pct, current_folder, count):
            self.after(0, lambda: self._on_scan_progress(pct, current_folder, count))

        try:
            results = self.scanner.scan_roots(
                targets=targets,
                progress_callback=progress_cb
            )
            self.after(0, lambda: self._on_scan_finished(results))
        except Exception as e:
            self.after(0, lambda: self._on_scan_error(str(e)))

    def _on_scan_progress(self, pct: float, current_folder: str, count: int):
        self.progress_bar.set(pct)
        display_name = current_folder if len(current_folder) < 30 else current_folder[:27] + "..."
        self.lbl_progress.configure(text=f"Scanning: {display_name} ({count} found)")

    def _on_scan_finished(self, results: list[AppDataItem]):
        self.is_scanning = False
        self.btn_scan.configure(text="▶ Start Scan", fg_color="#2563EB", hover_color="#1D4ED8", state="normal")
        self.progress_bar.set(1.0)
        self.lbl_progress.configure(text=f"Scan completed: {len(results)} items found.")
        self.items = results
        self._apply_filter()

    def _on_scan_error(self, err_msg: str):
        self.is_scanning = False
        self.btn_scan.configure(text="▶ Start Scan", fg_color="#2563EB", hover_color="#1D4ED8", state="normal")
        self.lbl_progress.configure(text="Scan failed.")
        messagebox.showerror("Scan Error", f"An error occurred during scan:\n{err_msg}")

    def _on_segment_changed(self, value: str):
        self.current_filter = value.upper()
        self._apply_filter()

    def _apply_filter(self):
        query = self.entry_search.get().strip().lower()
        cat = self.current_filter  # "ORPHANED", "INSTALLED", "PROTECTED", "ALL"

        self.filtered_items = []
        for item in self.items:
            # Check status filter
            if cat != "ALL" and item.status != cat:
                continue
            # Check search query
            if query and (query not in item.name.lower() and query not in item.path.lower()):
                continue
            self.filtered_items.append(item)

        self._render_filtered_items()
        self._update_summary_stats()

    def _render_filtered_items(self):
        # Clear existing items
        for w in self.scroll_results.winfo_children():
            w.destroy()
        self.row_widgets.clear()

        if not self.filtered_items:
            empty_text = "No matching folders found for this filter." if self.items else "Click 'Start Scan' to begin."
            lbl_empty = ctk.CTkLabel(
                self.scroll_results,
                text=empty_text,
                font=ctk.CTkFont(size=14),
                text_color="#64748B"
            )
            lbl_empty.pack(pady=80)
            return

        for item in self.filtered_items:
            row = ItemRow(
                self.scroll_results,
                item=item,
                on_toggle=lambda checked, it=item: self._on_item_toggled(it, checked),
                on_open=self._open_folder_in_explorer,
                on_whitelist=self._whitelist_folder
            )
            row.pack(fill="x", padx=4, pady=3)
            self.row_widgets.append(row)

    def _on_item_toggled(self, item: AppDataItem, checked: bool):
        item.selected = checked
        self._update_summary_stats()

    def _update_summary_stats(self):
        total_count = len(self.items)
        orphaned_count = sum(1 for i in self.items if i.status == "ORPHANED")
        selected_items = [i for i in self.items if i.selected and i.status != "PROTECTED"]
        selected_count = len(selected_items)
        selected_bytes = sum(i.size for i in selected_items)

        self.lbl_summary_stats.configure(
            text=f"Total: {total_count}  |  Orphaned: {orphaned_count}  |  Selected: {selected_count} ({format_size(selected_bytes)} reclaimable)"
        )

    def _select_all(self):
        for item in self.filtered_items:
            if item.status != "PROTECTED":
                item.selected = True
        for row in self.row_widgets:
            row.set_checked(True)
        self._update_summary_stats()

    def _deselect_all(self):
        for item in self.items:
            item.selected = False
        for row in self.row_widgets:
            row.set_checked(False)
        self._update_summary_stats()

    def _select_orphaned(self):
        for item in self.items:
            item.selected = (item.status == "ORPHANED")
        for row in self.row_widgets:
            row.set_checked(row.item.status == "ORPHANED")
        self._update_summary_stats()

    def _open_folder_in_explorer(self, path: str):
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder:\n{str(e)}")
        else:
            messagebox.showwarning("Not Found", "Folder does not exist on disk.")

    def _whitelist_folder(self, folder_name: str):
        if messagebox.askyesno("Confirm Whitelist", f"Add '{folder_name}' to user whitelist?\nIt will be permanently protected from deletion."):
            self.scanner.whitelist_manager.add(folder_name)
            # Update item status
            for item in self.items:
                if item.name.lower() == folder_name.lower():
                    item.status = "PROTECTED"
                    item.selected = False
            self._apply_filter()

    def _confirm_recycle_delete(self):
        selected = [i for i in self.items if i.selected and i.status != "PROTECTED"]
        if not selected:
            messagebox.showinfo("No Selection", "Please select at least one item to delete.")
            return

        total_size_str = format_size(sum(i.size for i in selected))
        msg = (
            f"Are you sure you want to move {len(selected)} folder(s) ({total_size_str}) to the Windows Recycle Bin?\n\n"
            "You can restore them from the Recycle Bin if needed."
        )
        if messagebox.askyesno("Confirm Recycle Bin Clean", msg, icon="question"):
            self._execute_deletion(selected, use_recycle_bin=True)

    def _confirm_permanent_delete(self):
        selected = [i for i in self.items if i.selected and i.status != "PROTECTED"]
        if not selected:
            messagebox.showinfo("No Selection", "Please select at least one item to delete.")
            return

        total_size_str = format_size(sum(i.size for i in selected))
        msg = (
            f"⚠️ WARNING: PERMANENT DELETION\n\n"
            f"This will PERMANENTLY delete {len(selected)} folder(s) ({total_size_str}) from disk.\n"
            "These files CANNOT be restored from the Recycle Bin.\n\n"
            "Do you want to proceed?"
        )
        if messagebox.askyesno("Confirm Permanent Deletion", msg, icon="warning"):
            self._execute_deletion(selected, use_recycle_bin=False)

    def _execute_deletion(self, items_to_delete: list[AppDataItem], use_recycle_bin: bool):
        items_dict = [{"name": i.name, "path": i.path, "size": i.size} for i in items_to_delete]
        res = CleanerEngine.delete_items(items_dict, use_recycle_bin=use_recycle_bin)

        # Remove deleted items from our list
        deleted_paths = {i["path"] for i in items_dict}
        self.items = [i for i in self.items if i.path not in deleted_paths or os.path.exists(i.path)]

        self._apply_filter()

        mode_str = "moved to the Recycle Bin" if use_recycle_bin else "permanently deleted"
        summary_msg = (
            f"Cleanup Complete!\n\n"
            f"Successfully {mode_str}: {res['success_count']} folder(s)\n"
            f"Freed space: {format_size(res['freed_bytes'])}\n"
        )
        if res["failed_count"] > 0:
            summary_msg += f"\nFailed items: {res['failed_count']}\n" + "\n".join(res["errors"][:3])

        messagebox.showinfo("Cleanup Summary", summary_msg)
