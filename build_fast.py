import PyInstaller.__main__
import shutil
import os

# Configuration
APP_NAME = "BIOS_Programmer"
DIST_DIR = "dist"
BUILD_DIR = "build"

def build():
    print(f"Starting Build for {APP_NAME}...")

    # 1. Clean previous build
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    # 2. Run PyInstaller
    # We exclude the project modules so they remain as external folders (modular)
    # But we MUST bundle standard libs (tk, ctypes, etc)
    
    print("Running PyInstaller...")
    PyInstaller.__main__.run([
        'launcher.py',
        '--name=%s' % APP_NAME,
        '--windowed',
        '--onedir',
        '--clean',
        '--noconfirm',
        # Icon for the EXE file itself
        '--icon=python_version/ui/assets/logo.png', 
        # Excludes: Keep source code external
        '--exclude-module=core',
        '--exclude-module=hardware',
        '--exclude-module=ui',
        '--exclude-module=utils',
        '--exclude-module=sound_engine',
        '--exclude-module=bios_editor',
    ])

    print("PyInstaller finished. Organizing files...")

    # 3. Organize Output
    # PyInstaller output is in dist/BIOS_Programmer
    TARGET_DIR = os.path.join(DIST_DIR, APP_NAME)
    
    if not os.path.exists(TARGET_DIR):
        print(f"Error: Target directory {TARGET_DIR} does not exist!")
        return

    # Copy 'python_version' contents (flattened logic)
    # We want dist/BIOS_Programmer/core, dist/BIOS_Programmer/ui, etc.
    SRC_PY_VER = "python_version"
    
    for item in os.listdir(SRC_PY_VER):
        s = os.path.join(SRC_PY_VER, item)
        d = os.path.join(TARGET_DIR, item)
        
        if os.path.isdir(s):
            print(f"Copying {item}...")
            if os.path.exists(d):
                shutil.rmtree(d) # Clean collision from OneDir if any
            shutil.copytree(s, d)
        else: # Files (__init__.py ?)
            shutil.copy2(s, d)

    # Copy Assets to Root (Critical for main_gui.py frozen logic)
    # main_gui expects assets in {root_dir}/assets
    assets_src = os.path.join(SRC_PY_VER, "ui", "assets")
    assets_dst = os.path.join(TARGET_DIR, "assets")
    if os.path.exists(assets_src):
        print("Copying assets to root...")
        if os.path.exists(assets_dst):
             shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)

    # Copy Images to Root (Slideshow)
    images_src = os.path.join(SRC_PY_VER, "ui", "images")
    images_dst = os.path.join(TARGET_DIR, "images")
    if os.path.exists(images_src):
        print("Copying images to root...")
        if os.path.exists(images_dst):
             shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)

    # Create Drivers Folder structure
    print("Setting up drivers folder...")
    drv_dir = os.path.join(TARGET_DIR, "drivers", "FTDI")
    os.makedirs(drv_dir, exist_ok=True)
    
    # Copy chiplist.xml and version.txt
    for f in ["chiplist.xml", "version.txt"]:
        if os.path.exists(f):
            print(f"Copying {f}...")
            shutil.copy2(f, os.path.join(TARGET_DIR, f))

    print(f"\nBuild Successful! Output: {TARGET_DIR}")
    print(f"Executable: {os.path.join(TARGET_DIR, APP_NAME + '.exe')}")

if __name__ == "__main__":
    build()
