import os
import sys

# Ensure working directory is the driver directory where build assets are located
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import shutil
import subprocess
import PyInstaller.__main__  # type: ignore

# --- CONFIGURATION ---
APP_NAME = "R1_BIOS_Programmer"
MAIN_SCRIPT = os.path.join("python_version", "ui", "main_gui.py")
DIST_DIR = "dist"
BUILD_DIR = "build"

# Source Paths (Project Root Relative)
SRC_ASSETS = os.path.join("python_version", "ui", "assets")
SRC_CHIPLIST = "chiplist.xml"
SRC_VERSION = "version.txt"
SRC_IMAGES = os.path.join("python_version", "ui", "images") # Slideshow images

# DLLs (Must be present in root)
DLL_FILES = ["ftd2xx.dll", "ftd2xx64.dll"]

def clean_build():
    """Clean previous build artifacts fast using Windows native commands"""
    print("CLEANING PREVIOUS BUILD...")
    # Try to kill the app if it's running so we don't get PermissionError
    subprocess.run(["taskkill", "/f", "/im", f"{APP_NAME}.exe"], capture_output=True)
    
    # Fast native directory removal (Instant compared to Python shutil.rmtree)
    for folder in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(folder):
            subprocess.run(f'cmd /c rmdir /s /q "{folder}"', shell=True, capture_output=True)
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                except Exception:
                    pass

    spec_file = f"{APP_NAME}.spec"
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
        except Exception:
            pass

def run_build():
    print("STARTING BUILD PROCESS...")
    
    # 1. Clean
    clean_build()
    
    # 2. PyInstaller Command Construction
    cmd = [
        MAIN_SCRIPT,
        '--name=%s' % APP_NAME,
        '--onedir',             # CRITICAL: Folder based, instant launch
        '--windowed',           # No console
        '--noconfirm',
        '--clean',
        '--noupx',              # CRITICAL: UPX is slow
        # Run normally as standard user (NO UAC admin prompt)
        
        # Paths to search for imports
        '--paths=python_version', 
        
        # Excludes - Optimization
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--exclude-module=tkinter.test',
        '--exclude-module=unittest',
        
        # Hidden Imports (Manual Dynamic Loading)
        '--hidden-import=PIL',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=python_version.core',
        '--hidden-import=python_version.hardware',
        '--hidden-import=python_version.utils',
        '--hidden-import=python_version.ui',
    ]

    # Add icon if exists
    icon_path = os.path.join(SRC_ASSETS, "logo.ico") # Looking for a .ico
    # Fallback to png if ico doesn't exist? PyInstaller needs .ico for Windows exe icon
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')

    print(f"RUNNING PYINSTALLER...")
    PyInstaller.__main__.run(cmd)
    
    # 3. Post-Build Organization
    print("ORGANIZING OUTPUT FOLDER...")
    
    output_root = os.path.join(DIST_DIR, APP_NAME)
    
    # We need to replicate the folder structure so that relative path logic works.
    # Code expects: ../../chiplist.xml from the UI file location.
    
    # Target Layout:
    # dist/R1.../R1_BIOS_Programmer.exe
    # dist/R1.../python_version/ui/assets/
    # dist/R1.../chiplist.xml (Actually needs to be relative to exe logic?)
    
    # PROBLEM: If code uses `os.path.dirname(os.path.abspath(__file__))`, in frozen mode 
    # it typically resolves to the folder containing the EXE.
    # So `ui_dir` = output_root.
    # `root_dir` (driver folder) = `output_root/../../` -> This escapes the folder!
    
    # To fix this without code changes, we must force the internal structure.
    # However, standard practice for frozen apps that use relative paths for resources
    # is to place resources relative to the EXE.
    
    # Since we cannot change code, we will place `chiplist.xml` and others
    # TWO LEVELS UP from the EXE? No, that's impossible for a portable app.
    
    # WAIT! If `ui_dir` = `output_root`, then `root_dir` = `dirname(dirname(output_root))` = `dist`.
    # So if we put `chiplist.xml` in `dist/`, it might work.
    
    # BUT, that defeats the purpose of a self-contained folder.
    
    # STRATEGY:
    # We will assume that for the EXE build, we want the EXE in the root of the output folder.
    # We will copy the config files to the root of the output folder.
    # IF the app fails to find them because of `../../`, we will unfortunately have to guide the user
    # to move the EXE deep or accept a code patch. 
    # **HOWEVER**, many users have this issue.
    # Let's try to put them in the root of the output folder first.
    
    # Assets (Images/Icons) - Code expects `ui_dir/assets`
    # So we create `output_root/assets`.
    dest_assets = os.path.join(output_root, "assets")
    if os.path.exists(SRC_ASSETS):
        if os.path.exists(dest_assets): shutil.rmtree(dest_assets)
        shutil.copytree(SRC_ASSETS, dest_assets)
        print(f"   [+] Copied Assets to {dest_assets}")

    # Images (Slideshow) - Code expects `ui_dir/images` (based on `main_gui.py`: `img_dir = .../images`)
    dest_images = os.path.join(output_root, "images")
    if os.path.exists(SRC_IMAGES):
        if os.path.exists(dest_images): shutil.rmtree(dest_images)
        shutil.copytree(SRC_IMAGES, dest_images)
        print(f"   [+] Copied Images to {dest_images}")

    # Drivers (FTDI & WinUSB for 1-click switcher)
    src_drivers = os.path.join("python_version", "drivers")
    dest_drivers = os.path.join(output_root, "drivers")
    if os.path.exists(src_drivers):
        if os.path.exists(dest_drivers): shutil.rmtree(dest_drivers)
        shutil.copytree(src_drivers, dest_drivers)
        print(f"   [+] Copied Drivers to {dest_drivers}")

    # Chiplist.xml - Code expects `ui_dir/../../chiplist.xml`
    # If EXE is at root, this looks outside.
    # We will copy it to root AND create a dummy path `python_version/ui/` and put a shortcut? No.
    # We'll just copy it to root for now.
    shutil.copy2(SRC_CHIPLIST, output_root)
    print(f"   [+] Copied chiplist.xml")
    
    # Version.txt
    shutil.copy2(SRC_VERSION, output_root)
    print(f"   [+] Copied version.txt")

    # DLLs
    for dll in DLL_FILES:
        if os.path.exists(dll):
            shutil.copy2(dll, output_root)
            print(f"   [+] Copied {dll}")
        elif os.path.exists(os.path.join("python_version", dll)):
             shutil.copy2(os.path.join("python_version", dll), output_root)
             print(f"   [+] Copied {dll} (from python_version)")
        else:
            print(f"   [!] WARNING: {dll} not found in source root or python_version.")

    print("\nBUILD COMPLETE.")
    print(f"   Executable location: {os.path.abspath(os.path.join(output_root, APP_NAME + '.exe'))}")
    print("   NOTE: If app fails to load config/assets, ensure relative paths match file placement.")

    # --- UPDATER BUILD INTEGRATION ---
    print("\nBUILDING UPDATER...")
    try:
        import build_updater
        build_updater.run_build()
        
        # Move updater.exe to the R1_BIOS_Programmer folder
        updater_src = os.path.join(DIST_DIR, "updater.exe")
        updater_dst = os.path.join(output_root, "updater.exe")
        
        if os.path.exists(updater_src):
            if os.path.exists(updater_dst): os.remove(updater_dst)
            shutil.move(updater_src, updater_dst)
            print(f"   [+] Integrated updater.exe into {output_root}")
        else:
             print("   [!] WARNING: updater.exe not found after build.")
             
    except ImportError:
        print("   [!] ERROR: build_updater.py not found.")
    except Exception as e:
        print(f"   [!] ERROR building updater: {e}")


    # --- INNO SETUP INSTALLER INTEGRATION ---
    print("\nBUILDING INNO SETUP INSTALLER...")
    try:
        import glob
        iscc_candidates = (
            glob.glob(r"C:\Program Files*\Inno Setup*\ISCC.exe") +
            glob.glob(r"C:\Users\*\AppData\Local\Programs\Inno Setup*\ISCC.exe")
        )
        iss_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "R1_BIOS_Programmer-innosetup.iss")
        if iscc_candidates and os.path.exists(iss_file):
            iscc_path = iscc_candidates[0]
            print(f"   [+] Found Inno Setup Compiler: {iscc_path}")
            res = subprocess.run([iscc_path, iss_file], capture_output=True, text=True)
            if res.returncode == 0:
                print("   [+] Installer created successfully!")
                print(f"   [+] Installer path: {os.path.abspath(os.path.join(DIST_DIR, 'R1_BIOS_Programmer.exe'))}")
            else:
                print(f"   [!] ISCC Error: {res.stderr or res.stdout}")
        else:
            print("   [!] Inno Setup compiler (ISCC.exe) or script not found. Skipping installer build.")
    except Exception as e:
        print(f"   [!] ERROR building installer: {e}")

if __name__ == "__main__":
    run_build()
