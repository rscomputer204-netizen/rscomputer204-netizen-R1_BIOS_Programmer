import os
import sys
import shutil
import json
import time
import subprocess
import logging
import ctypes
from datetime import datetime

# --- CONFIGURATION ---
LOG_FILE = "updater.log"
UPDATE_CACHE_DIR = "update_cache"
BACKUP_DIR_BASE = "backup"
MANIFEST_FILE = "manifest.json"
PAYLOAD_DIR = "payload"
VERSION_FILE = "version.txt"
MAIN_EXE_NAME = "R1_BIOS_Programmer.exe"

# Configure Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log(msg, level="info"):
    print(msg)
    if level == "info": logging.info(msg)
    elif level == "error": logging.error(msg)
    elif level == "warning": logging.warning(msg)

def wait_for_process_exit(pid):
    """Waits for the specified PID to exit."""
    if not pid: return
    log(f"Waiting for main process (PID: {pid}) to exit...")
    try:
        # Check if process exists
        # This is a basic check. For more robust checking we might need psutil, 
        # but we want to avoid external deps in this lightweight updater.
        # We'll use a simple loop checking if we can access the process handle (conceptually)
        # In Python, we can't easily check remote PID existence without os.kill(pid, 0)
        # on Unix or ctypes on Windows.
        
        # Windows specific wait
        import ctypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        process = kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if process:
             kernel32.WaitForSingleObject(process, 10000) # Wait up to 10s
             kernel32.CloseHandle(process)
             log("Main process exited.")
        else:
             log("Process not found or already exited.")

    except Exception as e:
        log(f"Warning: Could not wait on PID {pid}: {e}", "warning")
        time.sleep(2) # Fallback wait

def load_manifest(cache_path):
    manifest_path = os.path.join(cache_path, MANIFEST_FILE)
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("Manifest file missing in update cache.")
    
    try:
        with open(manifest_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Invalid manifest JSON.")

def create_backup(manifest, root_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(root_dir, BACKUP_DIR_BASE, timestamp)
    os.makedirs(backup_path, exist_ok=True)
    
    log(f"Creating backup at {backup_path}...")
    
    backup_map = [] # List of (original_path, backup_path) to allow restoration
    
    files_to_update = manifest.get("files", [])
    files_to_update.append(VERSION_FILE) # Always back up version file
    
    for rel_path in files_to_update:
        # Sanitize path to prevent directory traversal
        if ".." in rel_path or rel_path.startswith("/") or rel_path.startswith("\\"):
            log(f"Skipping unsafe path: {rel_path}", "warning")
            continue
            
        src = os.path.join(root_dir, rel_path)
        dst = os.path.join(backup_path, rel_path)
        
        if os.path.exists(src):
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            backup_map.append((src, dst))
            # log(f"Backed up: {rel_path}")
        else:
            log(f"File new (no backup needed): {rel_path}")
            
    # Save the backup map just in case
    with open(os.path.join(backup_path, "backup_map.json"), "w") as f:
        json.dump(backup_map, f)
        
    return float(timestamp) # Return timestamp as ID or path

def restore_backup(root_dir, timestamp_id):
    pass # Implementation below if needed, but we might just copy back

def perform_update(manifest, cache_path, root_dir):
    payload_path = os.path.join(cache_path, PAYLOAD_DIR)
    if not os.path.exists(payload_path):
        raise FileNotFoundError("Payload directory missing.")
        
    log("Applying updates...")
    files = manifest.get("files", [])
    
    # 1. Update Files
    for rel_path in files:
        src = os.path.join(payload_path, rel_path)
        dst = os.path.join(root_dir, rel_path)
        
        if not os.path.exists(src):
            log(f"Warning: Source file missing in payload: {rel_path}", "warning")
            continue
            
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        log(f"Updated: {rel_path}")

    # 2. Update Version File
    ver_src = os.path.join(cache_path, VERSION_FILE)
    ver_dst = os.path.join(root_dir, VERSION_FILE)
    if os.path.exists(ver_src):
        shutil.copy2(ver_src, ver_dst)
        log(f"Updated version info.")

def rollback(root_dir, backup_timestamp):
    log(f"CRITICAL: Rolling back to {backup_timestamp}...")
    backup_path = os.path.join(root_dir, BACKUP_DIR_BASE, str(backup_timestamp))
    
    if not os.path.exists(backup_path):
        log("Rollback failed: Backup directory not found!", "error")
        return

    # Simple restore: copy everything from backup back to root
    for root, dirs, files in os.walk(backup_path):
        for file in files:
            # Calculate relative path from backup root
            full_backup_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_backup_path, backup_path)
            
            if rel_path == "backup_map.json": continue
            
            target_path = os.path.join(root_dir, rel_path)
            
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(full_backup_path, target_path)
                log(f"Restored: {rel_path}")
            except Exception as e:
                log(f"Failed to restore {rel_path}: {e}", "error")

def main():
    if len(sys.argv) < 2:
        print("Usage: updater.exe <PID_OF_MAIN_PROCESS>")
        # For testing, we might allow running without PID
        # sys.exit(1)
        pid = None
        log("No PID provided. Assuming standalone test mode.", "warning")
    else:
        pid = sys.argv[1]

    # Determine paths
    # Assuming updater.exe is in dist/ (same level as R1...exe)
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Wait for main app to close
    wait_for_process_exit(pid)
    
    # Small buffer ensuring file locks are released
    time.sleep(1)

    cache_path = os.path.join(base_dir, UPDATE_CACHE_DIR)
    
    # Validate Environment
    if not os.path.exists(cache_path):
        log("Update cache not found. Nothing to do.", "error")
        # Relaunch main anyway
        subprocess.Popen([os.path.join(base_dir, MAIN_EXE_NAME)])
        sys.exit(1)

    backup_id = None
    
    try:
        # 1. Load Manifest
        manifest = load_manifest(cache_path)
        log(f"Starting update to version {manifest.get('version', 'unknown')}...")

        # 2. Create Backup
        backup_id = create_backup(manifest, base_dir)

        # 3. Perform Safe Update
        perform_update(manifest, cache_path, base_dir)

        log("Update completed successfully.")
        
        # 4. Cleanup Cache (Only on success)
        try:
            shutil.rmtree(cache_path)
        except Exception as e:
            log(f"Warning: Could not cleanup cache: {e}", "warning")

    except Exception as e:
        log(f"UPDATE FAILED: {e}", "error")
        import traceback
        log(traceback.format_exc(), "error")
        
        if backup_id:
            rollback(base_dir, backup_id)
            log("Rollback completed. Application restored.")
        
        # Show error to user via simple message box (using ctypes)
        try:
            ctypes.windll.user32.MessageBoxW(0, f"Update Failed!\n\nError: {e}\n\nThe application has been restored to the previous version.", "Update Error", 0x10)
        except:
            pass

    # 5. Relaunch Main Application
    main_exe = os.path.join(base_dir, MAIN_EXE_NAME)
    if os.path.exists(main_exe):
        log(f"Relaunching {MAIN_EXE_NAME}...")
        clean_env = os.environ.copy()
        clean_env.pop("_R1_HOT_RELOADED", None)
        subprocess.Popen([main_exe], cwd=base_dir, env=clean_env)
    else:
        log(f"CRITICAL: Main executable not found at {main_exe}", "error")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Fatal Updater Error: {e}", "error")
        # Attempt to relaunch main if possible
        try:
            if getattr(sys, 'frozen', False):
               base = os.path.dirname(sys.executable)
               subprocess.Popen([os.path.join(base, "R1_BIOS_Programmer.exe")])
        except:
            pass
