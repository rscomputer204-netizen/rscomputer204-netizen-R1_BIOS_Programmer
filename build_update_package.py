import os
import sys
import shutil
import json
import argparse
from pathlib import Path

# --- CONFIGURATION ---
FORBIDDEN_PATHS = [
    "drivers",         # Folder
    "bios_dumps",      # Folder
    "logs",            # Folder
    "backup",          # Folder
    "update_cache",    # Folder
    "updater.exe",     # File (Self-updating updater is risky without careful handling, safer to exclude for now unless requested)
    "R1_BIOS_Programmer.spec",
    "bootloader",      # Folder (if present)
]

# Files that MUST be in the root of the source to be valid (optional, but good for sanity check)
REQUIRED_FILES = [
    "R1_BIOS_Programmer.exe"
]

def is_allowed(relative_path):
    """
    Check if a file path is allowed in the update package.
    """
    parts = Path(relative_path).parts
    
    # Check if any part of the path is forbidden
    for part in parts:
        if part in FORBIDDEN_PATHS: # Exact match for folder/file names in forbidden list
            return False
        
        # also check for .log extensions or other specific patterns if needed
        if part.endswith(".log") or part.endswith(".dump"):
            return False

    # Check for forbidden directories at the start of the path
    if parts[0] in FORBIDDEN_PATHS:
        return False
        
    return True

def create_update_package(source_dir, output_dir_name, version):
    """
    Generates the update package directory.
    """
    source_path = Path(source_dir).resolve()
    # If output_dir_name is provided, use it, otherwise default to "update_package_v{version}"
    if not output_dir_name:
        output_dir_name = f"update_package_v{version}"
    
    output_path = Path(output_dir_name).resolve()
    
    if not source_path.exists():
        print(f"[!] Source directory not found: {source_path}")
        return False

    # Clean existing output directory if it exists
    if output_path.exists():
        print(f"[*] Cleaning existing output directory: {output_path}")
        shutil.rmtree(output_path)
    
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Analyzing source: {source_path}")
    
    payload_files = []
    skipped_files = []
    
    # 1. Collect Valid Files
    for root, dirs, files in os.walk(source_path):
        # Modify dirs in-place to skip forbidden directories during walk
        dirs[:] = [d for d in dirs if d not in FORBIDDEN_PATHS]
        
        for file in files:
            abs_file_path = Path(root) / file
            rel_path = abs_file_path.relative_to(source_path)
            str_rel_path = str(rel_path).replace("\\", "/") # Normalize to forward slashes for JSON
            
            if is_allowed(rel_path):
                payload_files.append((abs_file_path, str_rel_path))
            else:
                skipped_files.append(str_rel_path)

    if not payload_files:
        print("[!] No valid files found to package!")
        return False

    # Check if R1_BIOS_Programmer.exe is included
    has_main_exe = any("R1_BIOS_Programmer.exe" in p[1] for p in payload_files)
    if not has_main_exe:
        print("[!] WARNING: R1_BIOS_Programmer.exe not found in source! Package might be incomplete.")

    print(f"[*] Found {len(payload_files)} valid files.")
    if skipped_files:
        print(f"[*] Skipped {len(skipped_files)} forbidden/excluded files.")

    # 2. Generate Manifest
    manifest = {
        "version": version,
        "files": [p[1] for p in payload_files]
    }
    
    # 3. Create Package Structure
    print(f"[*] Creating package structure at: {output_path}")
    
    try:
        # A. Write Manifest
        with open(output_path / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=4)
            
        # B. Write Version
        with open(output_path / "version.txt", "w") as f:
            f.write(version)
            
        # C. Copy Payload
        payload_dir = output_path / "payload"
        payload_dir.mkdir(exist_ok=True)
        
        for abs_path, rel_path in payload_files:
            # Determine destination path inside payload folder
            dest_file_path = payload_dir / rel_path
            
            # Ensure parent directories exist
            dest_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(abs_path, dest_file_path)
                
        print(f"[+] Package created successfully at: {output_path}")
        print("    Contents:")
        print(f"    - manifest.json (v{version})")
        print(f"    - version.txt")
        print(f"    - payload/ ({len(payload_files)} files)")
        print(f"\n[INFO] You can now ZIP this folder as 'update.zip' for distribution.")
        return True
        
    except Exception as e:
        print(f"[!] Error creating package: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate R1 BIOS Programmer Update Package (Folder)")
    parser.add_argument("--source", "-s", required=True, help="Source directory containing the new build files")
    parser.add_argument("--output", "-o", default=None, help="Output directory path (default: update_package_vX.X.X)")
    parser.add_argument("--version", "-v", required=True, help="Version string (e.g., 1.2.0)")
    
    args = parser.parse_args()
    
    create_update_package(args.source, args.output, args.version)

