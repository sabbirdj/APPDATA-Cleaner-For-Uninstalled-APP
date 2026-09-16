import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Callable, Optional
from backend.everything_cli import EverythingCLI
from backend.whitelist import WhitelistManager

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, everything_cli: EverythingCLI, whitelist_manager: WhitelistManager, on_updated: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.everything_cli = everything_cli
        self.whitelist_manager = whitelist_manager
        self.on_updated = on_updated

        self.title("Settings & Whitelist Management")
        self.geometry("640x560")
        self.minsize(580, 500)
        self.transient(master)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=16)

        tab_wl = self.tabview.add("Custom Whitelist")
        tab_es = self.tabview.add("Everything CLI Config")

        # --- Tab 1: Whitelist ---
        lbl_wl_info = ctk.CTkLabel(
            tab_wl,
            text="Folders in this list are completely ignored during scans and cannot be deleted.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        lbl_wl_info.pack(anchor="w", padx=10, pady=(10, 8))

        # Input to add
        add_frame = ctk.CTkFrame(tab_wl, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=6)

        self.entry_add = ctk.CTkEntry(add_frame, placeholder_text="Enter folder name (e.g. MyCustomTool)...", height=36)
        self.entry_add.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_add.bind("<Return>", lambda e: self._add_item())

        btn_add = ctk.CTkButton(add_frame, text="+ Add to Whitelist", width=130, height=36, command=self._add_item)
        btn_add.pack(side="right")

        # Scrollable list of custom whitelisted items
        self.scroll_list = ctk.CTkScrollableFrame(tab_wl, fg_color="#1E293B", corner_radius=8)
        self.scroll_list.pack(fill="both", expand=True, padx=10, pady=(10, 10))

        self._refresh_whitelist_ui()

        # --- Tab 2: Everything CLI ---
        lbl_es_title = ctk.CTkLabel(
            tab_es,
            text="Voidtools Everything Command-Line Interface (es.exe)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_es_title.pack(anchor="w", padx=10, pady=(14, 4))

        status_str = "CONNECTED" if self.everything_cli.is_available else "DISCONNECTED / NOT FOUND"
        status_color = "#4ADE80" if self.everything_cli.is_available else "#F87171"

        self.lbl_status = ctk.CTkLabel(
            tab_es,
            text=f"Status: {status_str}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=status_color
        )
        self.lbl_status.pack(anchor="w", padx=10, pady=4)

        self.lbl_path = ctk.CTkLabel(
            tab_es,
            text=f"Binary Path: {self.everything_cli.cli_path or 'Not found'}",
            font=ctk.CTkFont(size=12),
            text_color="#CBD5E1",
            wraplength=540,
            justify="left"
        )
        self.lbl_path.pack(anchor="w", padx=10, pady=(2, 16))

        # Browse custom path
        browse_frame = ctk.CTkFrame(tab_es, fg_color="transparent")
        browse_frame.pack(fill="x", padx=10, pady=8)

        self.entry_path = ctk.CTkEntry(browse_frame, placeholder_text="Custom path to es.exe...", height=36)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if self.everything_cli.cli_path:
            self.entry_path.insert(0, self.everything_cli.cli_path)

        btn_browse = ctk.CTkButton(browse_frame, text="Browse...", width=90, height=36, command=self._browse_es)
        btn_browse.pack(side="right")

        btn_test = ctk.CTkButton(tab_es, text="Test Connection", height=36, command=self._test_es)
        btn_test.pack(anchor="w", padx=10, pady=12)

    def _refresh_whitelist_ui(self):
        for widget in self.scroll_list.winfo_children():
            widget.destroy()

        items = self.whitelist_manager.get_custom_items()
        if not items:
            lbl_empty = ctk.CTkLabel(
                self.scroll_list,
                text="No custom items in whitelist yet.\nUse '+ Add to Whitelist' or click Whitelist on any row.",
                text_color="#64748B",
                font=ctk.CTkFont(size=12)
            )
            lbl_empty.pack(pady=30)
            return

        for item in items:
            row = ctk.CTkFrame(self.scroll_list, fg_color="#0F172A", corner_radius=6, height=36)
            row.pack(fill="x", pady=3, padx=2)
            row.pack_propagate(False)

            lbl = ctk.CTkLabel(row, text=f"  🛡  {item}", font=ctk.CTkFont(size=13))
            lbl.pack(side="left", padx=8)

            btn_del = ctk.CTkButton(
                row,
                text="Remove",
                width=65,
                height=24,
                fg_color="#7F1D1D",
                hover_color="#991B1B",
                command=lambda val=item: self._remove_item(val)
            )
            btn_del.pack(side="right", padx=8)

    def _add_item(self):
        val = self.entry_add.get().strip()
        if val:
            if self.whitelist_manager.add(val):
                self.entry_add.delete(0, "end")
                self._refresh_whitelist_ui()
                if self.on_updated:
                    self.on_updated()
            else:
                messagebox.showinfo("Already exists", f"'{val}' is already in the whitelist.")

    def _remove_item(self, val: str):
        if self.whitelist_manager.remove(val):
            self._refresh_whitelist_ui()
            if self.on_updated:
                self.on_updated()

    def _browse_es(self):
        fp = filedialog.askopenfilename(
            title="Select es.exe executable",
            filetypes=[("Executables", "*.exe"), ("All Files", "*.*")]
        )
        if fp:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, fp)
            self.everything_cli.cli_path = fp
            self._test_es()

    def _test_es(self):
        cand = self.entry_path.get().strip()
        if cand:
            self.everything_cli.cli_path = cand
        self.everything_cli.is_available = self.everything_cli._test_connection()
        if self.everything_cli.is_available:
            self.lbl_status.configure(text="Status: CONNECTED", text_color="#4ADE80")
            self.lbl_path.configure(text=f"Binary Path: {self.everything_cli.cli_path}")
            messagebox.showinfo("Success", "Successfully connected to Voidtools Everything service!")
        else:
            self.lbl_status.configure(text="Status: DISCONNECTED / NOT FOUND", text_color="#F87171")
            messagebox.showwarning("Connection Failed", "Could not communicate with Everything.\nEnsure Everything is running and es.exe path is correct.")
        if self.on_updated:
            self.on_updated()
