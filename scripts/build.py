"""
Automated Build Pipeline for AppData Orphan Cleaner
1. Generates icons and brand assets
2. Packages standalone Windows executable via PyInstaller
3. Compiles professional Windows installer via Inno Setup (ISCC)
"""

import os
import sys
import shutil
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

def find_iscc() -> str:
    """Finds Inno Setup Compiler executable."""
    which_iscc = shutil.which("iscc.exe") or shutil.which("iscc")
    if which_iscc:
        return which_iscc

    candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # Search LocalAppData Programs dynamically
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        for root, dirs, files in os.walk(os.path.join(localappdata, "Programs")):
            if "ISCC.exe" in files:
                return os.path.join(root, "ISCC.exe")

    return ""

def step_generate_assets():
    print("\n[1/4] Generating Application Icons...")
    assets_dir = os.path.join(PROJECT_ROOT, "assets")
    from generate_assets import create_app_icon
    create_app_icon(assets_dir)

def step_prepare_binaries():
    print("\n[2/4] Preparing External Binaries (es.exe)...")
    bin_dir = os.path.join(PROJECT_ROOT, "bin")
    target_es = os.path.join(bin_dir, "es.exe")
    if not os.path.isfile(target_es):
        # Look for WinGet package es.exe
        localappdata = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(localappdata, r"Microsoft\WinGet\Packages\voidtools.Everything.Cli_Microsoft.Winget.Source_8wekyb3d8bbwe\es.exe"),
            r"C:\Program Files\Everything\es.exe",
            r"C:\Program Files (x86)\Everything\es.exe",
        ]
        for src in candidates:
            if os.path.isfile(src):
                os.makedirs(bin_dir, exist_ok=True)
                shutil.copy2(src, target_es)
                print(f"  -> Bundled es.exe from {src}")
                break
    if os.path.isfile(target_es):
        print(f"  -> es.exe ready in bin/ ({os.path.getsize(target_es):,} bytes)")
    else:
        print("  -> Notice: es.exe not found for bundling (app will use system Everything if available)")

def step_pyinstaller():
    print("\n[3/4] Building Standalone Native Executable with PyInstaller...")
    spec_path = os.path.join(PROJECT_ROOT, "app.spec")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", spec_path]
    print(f"  Running: {' '.join(cmd)}")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("  [ERROR] PyInstaller build failed!")
        sys.exit(1)
    
    exe_path = os.path.join(PROJECT_ROOT, "dist", "AppDataOrphanCleaner", "AppDataOrphanCleaner.exe")
    if os.path.isfile(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        # Ensure es.exe is also at dist root alongside the executable
        src_es = os.path.join(PROJECT_ROOT, "bin", "es.exe")
        dst_es = os.path.join(PROJECT_ROOT, "dist", "AppDataOrphanCleaner", "es.exe")
        if os.path.isfile(src_es) and not os.path.isfile(dst_es):
            shutil.copy2(src_es, dst_es)
            print("  -> Placed es.exe at root of dist folder")

    # Clean intermediate build directory to prevent confusing stub executables
    build_dir = os.path.join(PROJECT_ROOT, "build")
    shutil.rmtree(build_dir, ignore_errors=True)

def step_inno_setup():
    print("\n[4/4] Building Windows Installer with Inno Setup...")
    iscc_path = find_iscc()
    if not iscc_path:
        print("  [WARNING] Inno Setup compiler (ISCC.exe) not found on system.")
        print("  Skipping installer compilation. Standalone executable is ready in dist/AppDataOrphanCleaner/.")
        return

    print(f"  Using Inno Setup Compiler: {iscc_path}")
    iss_path = os.path.join(PROJECT_ROOT, "installer.iss")
    out_dir = os.path.join(PROJECT_ROOT, "installer_output")
    os.makedirs(out_dir, exist_ok=True)

    cmd = [iscc_path, f"/O{out_dir}", iss_path]
    t0 = time.time()
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("  [ERROR] Inno Setup compilation failed!")
        sys.exit(1)

    setup_path = os.path.join(out_dir, "AppDataOrphanCleaner_Setup_v1.0.0.exe")
    if os.path.isfile(setup_path):
        size_mb = os.path.getsize(setup_path) / (1024 * 1024)
        print(f"  [SUCCESS] Setup Installer built: {setup_path} ({size_mb:.1f} MB) in {time.time()-t0:.1f}s")
    else:
        print("  [ERROR] Output installer not found.")

def main():
    print("=" * 65)
    print("      AppData Orphan Cleaner — Release Build Pipeline")
    print("=" * 65)
    
    # Pre-clean build directory
    shutil.rmtree(os.path.join(PROJECT_ROOT, "build"), ignore_errors=True)

    step_generate_assets()
    step_prepare_binaries()
    step_pyinstaller()
    step_inno_setup()

    # Post-clean intermediate build directory
    shutil.rmtree(os.path.join(PROJECT_ROOT, "build"), ignore_errors=True)

    print("\n" + "=" * 65)
    print(" BUILD COMPLETE!")
    print("=" * 65)
    portable_exe = os.path.join(PROJECT_ROOT, "dist", "AppDataOrphanCleaner_Portable.exe")
    dist_dir = os.path.join(PROJECT_ROOT, "dist", "AppDataOrphanCleaner")
    installer_exe = os.path.join(PROJECT_ROOT, "installer_output", "AppDataOrphanCleaner_Setup_v1.0.0.exe")

    if os.path.isfile(portable_exe):
        size_mb = os.path.getsize(portable_exe) / (1024 * 1024)
        print(f"  [OK] Portable Single-File: {portable_exe} ({size_mb:.1f} MB)")
    if os.path.isdir(dist_dir):
        print(f"  [OK] Installed App Bundle: {dist_dir}")
    if os.path.isfile(installer_exe):
        size_mb = os.path.getsize(installer_exe) / (1024 * 1024)
        print(f"  [OK] Windows Setup Setup:  {installer_exe} ({size_mb:.1f} MB)")
    print("=" * 65)

if __name__ == "__main__":
    main()
