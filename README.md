<div align="center">

<img src="assets/app_icon.png" alt="AppData Orphan Cleaner Logo" width="128" height="128" />

# AppData Orphan Cleaner

**A high-performance Windows 11 desktop utility powered by Voidtools Everything CLI to detect, review, and safely remove abandoned AppData left behind by uninstalled applications.**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D4.svg?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![UI Framework](https://img.shields.io/badge/GUI-PyQt6%20Fluent%20Widgets-00B4D8.svg?logo=qt&logoColor=white)](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
[![Everything CLI](https://img.shields.io/badge/Backend-Voidtools%20Everything-FF9800.svg)](https://www.voidtools.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Features](#-key-features) •
[Architecture](#-how-it-works) •
[Installation & Usage](#-installation--quick-start) •
[Building from Source](#-building-the-native-executable--installer) •
[⚠️ Safety Warning](#️-safety-guidelines--deletion-warning) •
[License](#-license)

</div>

---

## 💡 The Problem

When applications are uninstalled from Windows, their uninstaller scripts almost always leave behind remnants inside:
- `AppData\Roaming`
- `AppData\Local`
- `AppData\LocalLow`
- `ProgramData`

Over time, hundreds of orphaned folders accumulate, silently consuming tens of gigabytes of disk space, fragmenting SSD file allocation tables, and cluttering system backups.

Traditional cleaner utilities either rely on slow recursive file crawling or blindly delete folders by name, risking system corruption. **AppData Orphan Cleaner** solves this by pairing the speed of the **Voidtools Everything NTFS USN Journal** with deep **Windows Registry verification** and a **multi-signal safety shield**, providing instant, zero-false-positive orphan detection.

---

## ✨ Key Features

- **🎨 Modern Windows 11 Fluent UI**:
  - Implements native Fluent Design specifications via `PyQt6-Fluent-Widgets`.
  - Acrylic/Mica surfaces, smooth animations, and Segoe Fluent iconography.
  - Seamless live theme switching (**Dark Mode**, **Light Mode**, or **System Synchronized**).
  - Responsive multi-tier control bar with adaptive search and segmented category filters.

- **⚡ Instant Voidtools Everything CLI (`es.exe`) Integration**:
  - Queries the NTFS Master File Table (MFT) and USN Journal in single-digit milliseconds.
  - Searches for executables, vendor directories, and Start Menu shortcuts across all physical and logical drives.

- **🛡️ Triple-Signal Safety Shield**:
  - **OS Component Whitelist**: Automatically filters and protects Windows system directories, Microsoft subsystems, PowerShell, Store packages, driver stores (NVIDIA, AMD, Intel), and runtime environments (`.dotnet`, `.gemini`, `pip`, `npm`).
  - **Registry Uninstall Database Verification**: Scans 32-bit and 64-bit Windows Uninstall registry hives to cross-reference registered applications.
  - **Acronym & Vendor Resolution**: Intelligently resolves abbreviations (e.g. `IDM` $\leftrightarrow$ *Internet Download Manager*) and vendor subdirectories (e.g. `Daum\PotPlayer`).

- **🔄 Real-Time Live Streaming & Continuation Scanning**:
  - Folders stream into the results table one by one in real-time as they are analyzed.
  - **Continuation Scanning ("Scan from where it left")**: Check additional targets (e.g., `LocalLow` or `ProgramData`) and only the newly checked targets are scanned without losing existing findings or selections.
  - Dedicated **"New Scan"** button to start fresh at any time.

- **↕️ Interactive Multi-Column Sorting**:
  - Click any table header (`Folder Name`, `Size`, `Status`, `Scope`, `Select`) to toggle Ascending ($\uparrow$) and Descending ($\downarrow$) order.
  - **Numerical Size Sorting**: Sorts by true byte size, placing the largest disk hogs at the top.

- **♻️ Windows Recycle Bin Safe Deletion**:
  - Deletions route to the **Windows Recycle Bin** (`Send2Trash`) by default, enabling instant one-click restoration if needed.
  - Permanent deletion is available as an explicit option with confirmation prompts.

---

## 🧭 How It Works

```
┌────────────────────────────────────────────────────────┐
│               Scan Targets Selected                    │
│      (Roaming, Local, LocalLow, ProgramData)           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │  Windows OS & Whitelist Filter   │
          │  (Microsoft, System, Drivers...) │
          └────────────────┬─────────────────┘
                           │ Passed
                           ▼
          ┌──────────────────────────────────┐
          │     Windows Registry Check       │
          │ (DisplayName, Acronyms, Paths)   │
          └────────────────┬─────────────────┘
                           │ Not explicitly found
                           ▼
          ┌──────────────────────────────────┐
          │     Voidtools Everything CLI     │
          │   (Executables, Shortcuts, MFT)  │
          └────────────────┬─────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
 ┌───────────┐                           ┌───────────┐
 │ INSTALLED │                           │ ORPHANED  │
 └───────────┘                           └─────┬─────┘
                                               │
                                               ▼
                                 ┌───────────────────────────┐
                                 │ Move to Recycle Bin (Safe)│
                                 └───────────────────────────┘
```

---

## 🚀 Installation & Quick Start

### Option 1: Windows Installer (Recommended)
Download and run `AppDataOrphanCleaner_Setup_v1.0.0.exe` from the latest release:
- Includes Start Menu & Desktop shortcuts.
- Fully registered in Windows Settings > **Installed Apps**.
- Embedded Voidtools Everything CLI (`es.exe`).

### Option 2: Standalone Portable Executable
Download `AppDataOrphanCleaner.exe` and run directly without any installation.

### Option 3: Run from Python Source

#### Prerequisites
- **Windows 10 / 11** (64-bit)
- **Python 3.10+** (Python 3.10 – 3.14 fully tested)
- Optional: [Voidtools Everything](https://www.voidtools.com/) installed and running (for live NTFS indexing)

```powershell
# 1. Clone the repository
git clone https://github.com/sabbirdj/APPDATA-Cleaner-For-Uninstalled-APP.git
cd APPDATA-Cleaner-For-Uninstalled-APP

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the modern Fluent UI
python main.py

# (Optional) Launch classic CustomTkinter UI
python main.py --classic
```

Or simply double-click **`run_app.bat`** on Windows.

---

## 🛠️ Building the Native Executable & Installer

This repository includes a complete automated build pipeline powered by **PyInstaller** and **Inno Setup 6**.

### One-Click Build
Run the provided batch launcher:
```powershell
.\build.bat
```

### Or run via Python build pipeline:
```powershell
python scripts\build.py
```

The build pipeline will:
1. Generate multi-resolution Windows 11 application icons (`assets/app_icon.ico` and `assets/app_icon.png`).
2. Bundle Voidtools Everything CLI (`bin/es.exe`).
3. Compile the standalone native executable into `dist/AppDataOrphanCleaner/AppDataOrphanCleaner.exe`.
4. Compile the Windows installer into `installer_output/AppDataOrphanCleaner_Setup_v1.0.0.exe`.

---

## 🧪 Testing

Run the automated test suite covering backend logic, whitelist filtering, Windows exclusion rules, and registry scanners:

```powershell
python -m unittest discover tests
```

---

## 📁 Repository Structure

```
├── assets/                  # High-resolution application icons (PNG & multi-size ICO)
├── backend/
│   ├── cleaner_engine.py    # Safe Send2Trash and permanent deletion logic
│   ├── everything_cli.py    # Voidtools Everything CLI subprocess bridge
│   ├── registry_scanner.py  # 32/64-bit Windows registry uninstall analyzer
│   ├── scanner_engine.py    # Core orphan detection & correlation engine
│   └── whitelist.py         # System protections & user whitelist manager
├── scripts/
│   ├── build.py             # Master build automation pipeline
│   └── generate_assets.py   # Icon and asset generator
├── tests/                   # Automated unittest suite
├── ui/                      # Classic CustomTkinter UI implementation
├── ui_fluent/               # Modern Windows 11 Fluent UI (PyQt6-Fluent-Widgets)
│   ├── main_window.py       # Main shell with navigation & taskbar setup
│   ├── scanner_interface.py # Live streaming scanner interface & table
│   ├── settings_interface.py# Settings & diagnostics dashboard
│   └── whitelist_interface.py# Custom whitelist manager interface
├── app.spec                 # PyInstaller specification file
├── build.bat                # One-click Windows release builder
├── installer.iss            # Inno Setup 6 installer definition
├── main.py                  # Application entry point
├── requirements.txt         # Python package dependencies
└── run_app.bat              # Quick launch script
```

---

## ⚠️ Safety Guidelines & Deletion Warning

> [!WARNING]
> ### 🛑 PLEASE READ CAREFULLY BEFORE DELETING ANY FILES OR FOLDERS
> 
> While **AppData Orphan Cleaner** employs a rigorous triple-signal verification engine (NTFS journal indexing, Windows Registry uninstaller cross-referencing, and system keyword filtering), **AppData folders often contain user settings, local databases, game save files, login sessions, and application cache.**
> 
> 1. **Always Review the Selection List**:
>    - Before clicking any cleanup button, inspect the folders checked in the results table.
>    - If you recognize a software title you still use—or might reinstall in the future—**uncheck it** or click the **Whitelist** button to permanently exclude it from future scans.
> 
> 2. **Prefer "Move Selected to Recycle Bin (Safe)"**:
>    - Always default to **Move Selected to Recycle Bin (Safe)**.
>    - Items sent to the Windows Recycle Bin can be immediately restored with right-click > **Restore** if you later discover a program required that folder.
> 
> 3. **Use "Permanently Delete" with Extreme Caution**:
>    - Permanent deletion bypasses the Windows Recycle Bin and purges files directly from your storage device.
>    - **Permanently deleted data cannot be undone or recovered via the Recycle Bin.** Only use this option when you are 100% confident that the data is abandoned and you must reclaim drive space immediately.
> 
> 4. **Backup Critical Data First**:
>    - We strongly advise creating a backup of your important `AppData\Roaming` and `AppData\Local` folders (especially web browser profiles, cryptocurrency wallets, developer SSH keys, and game saves) before performing any bulk cleanup operations.
> 
> 5. **Disclaimer of Liability**:
>    - This software is provided *"as is"*, without warranty of any kind, express or implied. Under no circumstances shall the authors or copyright holders be held liable for any data loss, system corruption, or other damages arising from the use of this software. You are solely responsible for reviewing and verifying the files you choose to delete.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<div align="center">
Made with ❤️ for a cleaner, faster Windows experience.
</div>
