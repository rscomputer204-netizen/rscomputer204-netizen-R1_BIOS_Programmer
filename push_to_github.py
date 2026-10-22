import os
import sys
import json
import time
import shutil
import datetime
import subprocess

# --- CONFIGURATION LOADER ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

CONFIG_FILE = os.path.join(BASE_DIR, "config", "github_token.json")
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "repo_owner": "rscomputer204-netizen",
        "repo_name": "rscomputer204-netizen-R1_BIOS_Programmer",
        "branch": "main",
        "github_token": ""
    }

cfg = load_config()
REPO_OWNER = cfg.get("repo_owner", "rscomputer204-netizen")
REPO_NAME = cfg.get("repo_name", "rscomputer204-netizen-R1_BIOS_Programmer")
BRANCH = cfg.get("branch", "main")
GITHUB_TOKEN = cfg.get("github_token", "")

def run_cmd(cmd, check=True):
    """Run shell command and return output."""
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed [{cmd}]: {res.stderr.strip()}")
    return res.stdout.strip()

def get_git_status():
    """Returns list of changed files according to git."""
    output = run_cmd("git status --porcelain", check=False)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines

def increment_version(ver_str):
    """Increment patch version, e.g. R1.0.0.5 -> R1.0.0.6"""
    try:
        prefix = "R" if ver_str.startswith("R") else ""
        raw_num = ver_str.lstrip("Rv")
        parts = [int(p) for p in raw_num.split(".")]
        parts[-1] += 1
        return f"{prefix}{'.'.join(str(p) for p in parts)}"
    except Exception:
        return ver_str

def main():
    print("=" * 60)
    print("      R1 FLASH ULTRA - SMART GITHUB AUTO-PUSH TOOL")
    print(f"      Target: {REPO_OWNER}/{REPO_NAME} [{BRANCH}]")
    print("=" * 60)

    # 1. Check if git repo exists
    if not os.path.exists(".git"):
        print("[*] Initializing local git repository...")
        run_cmd("git init")
        run_cmd(f"git branch -m {BRANCH}")
        remote_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"
        run_cmd(f"git remote add origin {remote_url}", check=False)

    # Ensure safe directory
    run_cmd(f'git config --global --add safe.directory "{BASE_DIR}"', check=False)

    # 2. Check for local changes
    changes = get_git_status()
    if not changes:
        print("\n[OK] NO CHANGES DETECTED!")
        print("All your code, resources, and files are already up to date on GitHub.")
        print("=" * 60)
        return

    print(f"\n[+] Detected {len(changes)} changed / new file(s):")
    for change in changes[:15]:
        print(f"    • {change}")
    if len(changes) > 15:
        print(f"    ... and {len(changes) - 15} more files.")

    # 3. Handle Versioning
    ver_file = "version.txt"
    current_ver = "R1.0.0.5"
    if os.path.exists(ver_file):
        with open(ver_file, "r", encoding="utf-8") as f:
            current_ver = f.read().strip()

    next_ver = increment_version(current_ver)
    print(f"\n[*] Current Version : {current_ver}")
    print(f"[*] Suggested New   : {next_ver}")

    # Non-interactive fallback or interactive input
    commit_msg = ""
    new_ver = next_ver
    if sys.stdin.isatty():
        try:
            ver_input = input(f">> Enter version to release [{next_ver}]: ").strip()
            if ver_input:
                new_ver = ver_input
            msg_input = input(">> Enter commit / changelog note (or press Enter for auto): ").strip()
            if msg_input:
                commit_msg = msg_input
        except EOFError:
            pass

    if not commit_msg:
        commit_msg = f"Auto-Update: Release {new_ver} with latest features and bug fixes"

    # Save updated version.txt
    with open(ver_file, "w", encoding="utf-8") as f:
        f.write(new_ver)
    py_ver_file = os.path.join("python_version", "version.txt")
    if os.path.exists(os.path.dirname(py_ver_file)):
        with open(py_ver_file, "w", encoding="utf-8") as f:
            f.write(new_ver)

    # 4. Generate update.zip package
    print("\n[STEP 1/3] Packaging update bundle (update.zip)...")
    payload_dir = os.path.join(BASE_DIR, "temp_update_payload")
    if os.path.exists(payload_dir):
        shutil.rmtree(payload_dir, ignore_errors=True)
    os.makedirs(payload_dir, exist_ok=True)

    # Include vital software files in update.zip
    # python_version, chiplist.xml, version.txt, manifest.json
    try:
        shutil.copytree("python_version", os.path.join(payload_dir, "payload", "python_version"), 
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_internal"))
        shutil.copy2("chiplist.xml", os.path.join(payload_dir, "payload", "chiplist.xml"))
        shutil.copy2(ver_file, os.path.join(payload_dir, "version.txt"))
        
        # Manifest
        manifest = {
            "version": new_ver,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "files": ["chiplist.xml", "python_version/"]
        }
        with open(os.path.join(payload_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)

        # Make update.zip in root
        zip_output_base = os.path.join(BASE_DIR, "update")
        if os.path.exists("update.zip"):
            os.remove("update.zip")
        shutil.make_archive(zip_output_base, "zip", payload_dir)
        print("[+] update.zip successfully created.")
    except Exception as e:
        print(f"[!] Warning during zip packaging: {e}")
    finally:
        shutil.rmtree(payload_dir, ignore_errors=True)

    # 5. Create / Update version.json
    print("[STEP 2/3] Updating version.json metadata...")
    raw_zip_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/update.zip"
    version_info = {
        "version": new_ver,
        "url": raw_zip_url,
        "changelog": commit_msg,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=4)
    print(f"[+] version.json updated to {new_ver}.")

    # 6. Git Add, Commit & Push via GitHub Token
    print(f"\n[STEP 3/3] Pushing to GitHub repository ({BRANCH})...")
    # Ensure git user is configured
    run_cmd('git config user.name "rscomputer204-netizen"', check=False)
    run_cmd('git config user.email "rscomputer204@gmail.com"', check=False)

    run_cmd("git add .")
    run_cmd(f'git commit -m "{commit_msg} (v{new_ver})"', check=False)

    # Push with token authentication
    auth_remote = f"https://{GITHUB_TOKEN}@github.com/{REPO_OWNER}/{REPO_NAME}.git"
    print("[*] Uploading changes to GitHub...")
    push_res = run_cmd(f"git push -u {auth_remote} {BRANCH}", check=False)
    
    print("\n" + "=" * 60)
    print("   [SUCCESS] ALL CHANGES PUSHED TO GITHUB PERFECTLY!")
    print(f"   Repository : https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print(f"   New Version: {new_ver}")
    print("   Users can now click 'UPDATE' to get these new changes!")
    print("=" * 60)

if __name__ == "__main__":
    main()
