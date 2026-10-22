
import os
import sys
import subprocess
import shutil

def main():
    # Change working directory to the script's directory to find dependencies
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("==================================================")
    print("    R1 FLASH ULTRA - AUTO UPDATE BUILDER TOOL")
    print("==================================================")
    print("This script will automatically compile your latest")
    print("source code and generate a ready-to-upload Update ZIP.\n")
    
    # 1. Read current version
    version_file = "version.txt"
    current_version = "R1.0.0.0"
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            current_version = f.read().strip()
            
    print(f"[*] Current Software Version: {current_version}")
    new_version = input(">> Enter new version (or press Enter to keep same): ").strip()
    
    if not new_version:
        new_version = current_version
    else:
        with open(version_file, "w") as f:
            f.write(new_version)
        # Also update version inside python_version if exists
        py_ver_file = os.path.join("python_version", "version.txt")
        if os.path.exists(py_ver_file):
            with open(py_ver_file, "w") as f:
                f.write(new_version)
        print(f"[*] Updated version to {new_version}")

    # 2. Compile Source Code
    print("\n[STEP 1/3] Compiling source code into EXE...")
    try:
        subprocess.run([sys.executable, "build_exe.py"], check=True)
    except subprocess.CalledProcessError:
        print("\n[!] ERROR: Failed to compile EXE. Please check your code for errors.")
        sys.exit(1)
    
    # 3. Create Update Package Folder
    print("\n[STEP 2/3] Generating update package folder...")
    output_dir = os.path.join("dist", f"update_{new_version}")
    try:
        subprocess.run([sys.executable, "build_update_package.py", 
                        "--source", os.path.join("dist", "R1_BIOS_Programmer"), 
                        "--output", output_dir, 
                        "--version", new_version], check=True)
    except subprocess.CalledProcessError:
        print("\n[!] ERROR: Failed to generate update package.")
        sys.exit(1)
                    
    # 4. Zip the Update Package
    print("\n[STEP 3/3] Zipping update package for GitHub...")
    try:
        # shutil.make_archive adds .zip automatically
        zip_path = shutil.make_archive(output_dir, 'zip', output_dir)
        print(f"\n==================================================")
        print(f"[SUCCESS] Update package perfectly created!")
        print(f"ZIP File: {zip_path}")
        print("==================================================")
        print("NEXT STEPS:")
        print("1. Upload this ZIP file to your GitHub repository.")
        print("2. Update your 'version.json' file online with the new version.")
        print("3. Users will now automatically get your latest code changes!")
        
    except Exception as e:
        print(f"\n[!] ERROR zipping file: {e}")


if __name__ == "__main__":
    main()
