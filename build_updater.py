import os
import shutil
import PyInstaller.__main__

# --- CONFIGURATION ---
APP_NAME = "updater"
MAIN_SCRIPT = "updater.py"
DIST_DIR = "dist"
BUILD_DIR = "build_updater"

def clean_build():
    """Clean previous build artifacts"""
    print("CLEANING UPDATER BUILD...")
    if os.path.exists(BUILD_DIR): shutil.rmtree(BUILD_DIR)
    if os.path.exists(f"{APP_NAME}.spec"): os.remove(f"{APP_NAME}.spec")
    # Note: We do NOT clean DIST_DIR here because we want to append to it (where the main app lives)

def run_build():
    print("STARTING UPDATER BUILD PROCESS...")
    
    clean_build()
    
    cmd = [
        MAIN_SCRIPT,
        '--name=%s' % APP_NAME,
        '--onefile',            # Updater should be a single file for simplicity
        '--console',            # Keep console for debugging (optional: make windowed later if desired)
        '--clean',
        '--noupx',
    ]

    print(f"RUNNING PYINSTALLER FOR UPDATER...")
    PyInstaller.__main__.run(cmd)
    
    # Move the single file executable to the main dist folder
    # PyInstaller with --onefile puts the exe in dist/
    
    # However, our main build script puts the main app in dist/R1_BIOS_Programmer/
    # We want the updater to be INSIDE that folder.
    
    # Since we can't easily know the exact folder name of the main app from here without config sharing,
    # we will just leave it in dist/updater.exe and let the main build script move it.
    
    print("\nUPDATER BUILD COMPLETE.")

if __name__ == "__main__":
    run_build()
