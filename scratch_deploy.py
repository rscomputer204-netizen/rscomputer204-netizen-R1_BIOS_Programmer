import os
import sys
import shutil
import json
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

TARGET_VER = "R1.0.2.3"
CHANGELOG = "HexViewer dummy data lines set to 45 lines"

CONFIG_FILE = os.path.join(BASE_DIR, "config", "github_token.json")
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    cfg = json.load(f)

repo_owner = cfg.get("repo_owner", "rscomputer204-netizen")
repo_name = cfg.get("repo_name", "rscomputer204-netizen-R1_BIOS_Programmer")
branch = cfg.get("branch", "main")
token = cfg.get("github_token", "")

print(f"[*] Deploying version {TARGET_VER} to GitHub ({repo_owner}/{repo_name})...")

# 1. Update version files
for vpath in [
    os.path.join(BASE_DIR, "version.txt"),
    os.path.join(BASE_DIR, "python_version", "version.txt"),
    os.path.join(BASE_DIR, "dist", "R1_BIOS_Programmer", "version.txt"),
    os.path.join(os.path.dirname(BASE_DIR), "version.txt")
]:
    try:
        with open(vpath, "w", encoding="utf-8") as f:
            f.write(TARGET_VER)
        print(f"Updated {vpath}")
    except Exception as e:
        print(f"Warning writing {vpath}: {e}")

# 2. Sync python_version into dist/R1_BIOS_Programmer/python_version
dist_py = os.path.join(BASE_DIR, "dist", "R1_BIOS_Programmer", "python_version")
if os.path.exists(dist_py):
    shutil.rmtree(dist_py, ignore_errors=True)
shutil.copytree(
    os.path.join(BASE_DIR, "python_version"),
    dist_py,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_internal", "tools")
)
print("[*] Synced python_version into dist folder.")

# 3. Create update.zip payload
payload_dir = os.path.join(BASE_DIR, "temp_update_payload")
if os.path.exists(payload_dir):
    shutil.rmtree(payload_dir, ignore_errors=True)
os.makedirs(payload_dir, exist_ok=True)

payload_content = os.path.join(payload_dir, "payload")
os.makedirs(payload_content, exist_ok=True)

dist_source = os.path.join(BASE_DIR, "dist", "R1_BIOS_Programmer")
forbidden = {"updater.exe", "drivers", "logs", "backup", "update_cache", "tools"}

if os.path.exists(dist_source):
    for root, dirs, files in os.walk(dist_source):
        dirs[:] = [d for d in dirs if d not in forbidden and d != "__pycache__"]
        for f in files:
            if f in forbidden or f.endswith(".log") or f.endswith(".dump"):
                continue
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, dist_source)
            dest_p = os.path.join(payload_content, rel_p)
            os.makedirs(os.path.dirname(dest_p), exist_ok=True)
            shutil.copy2(abs_p, dest_p)

dest_py_ver = os.path.join(payload_content, "python_version")
if os.path.exists(dest_py_ver):
    shutil.rmtree(dest_py_ver, ignore_errors=True)
shutil.copytree(
    os.path.join(BASE_DIR, "python_version"),
    dest_py_ver,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_internal", "tools")
)

if os.path.exists(os.path.join(BASE_DIR, "chiplist.xml")):
    shutil.copy2(os.path.join(BASE_DIR, "chiplist.xml"), os.path.join(payload_content, "chiplist.xml"))
shutil.copy2(os.path.join(BASE_DIR, "version.txt"), os.path.join(payload_dir, "version.txt"))

manifest_files = []
for root, dirs, files in os.walk(payload_content):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        abs_p = os.path.join(root, f)
        rel_p = os.path.relpath(abs_p, payload_content).replace("\\", "/")
        manifest_files.append(rel_p)

manifest = {
    "version": TARGET_VER,
    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "files": sorted(manifest_files)
}
with open(os.path.join(payload_dir, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=4)

zip_out = os.path.join(BASE_DIR, "update")
if os.path.exists(os.path.join(BASE_DIR, "update.zip")):
    try: os.remove(os.path.join(BASE_DIR, "update.zip"))
    except Exception: pass
shutil.make_archive(zip_out, "zip", payload_dir)
shutil.rmtree(payload_dir, ignore_errors=True)
print("[*] update.zip successfully packaged.")

# 4. Update version.json
raw_zip_url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/{branch}/update.zip"
ver_info = {
    "version": TARGET_VER,
    "url": raw_zip_url,
    "changelog": CHANGELOG,
    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}
with open(os.path.join(BASE_DIR, "version.json"), "w", encoding="utf-8") as f:
    json.dump(ver_info, f, indent=4)
print("[*] version.json updated.")

# 5. Git Commit & Push
print("[*] Staging and committing changes...")
subprocess.run(["git", "add", "."], check=True, cwd=BASE_DIR)
commit_res = subprocess.run(["git", "commit", "-m", f"{CHANGELOG} (v{TARGET_VER})"], cwd=BASE_DIR, capture_output=True, text=True)
print("Git commit output:", commit_res.stdout or commit_res.stderr)

print(f"[*] Pushing to GitHub remote {branch}...")
auth_url = f"https://{token}@github.com/{repo_owner}/{repo_name}.git"
push_res = subprocess.run(["git", "push", auth_url, branch], cwd=BASE_DIR, capture_output=True, text=True)
if push_res.returncode == 0:
    print(f"\n[SUCCESS] Deployed v{TARGET_VER} to GitHub!")
else:
    print(f"\n[ERROR] Git push failed:\n{push_res.stderr}")
    sys.exit(1)
