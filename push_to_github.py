import os
import sys
import re
import ast
import json
import time
import shutil
import threading
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# --- CONFIGURATION & PATHS ---
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

def run_cmd(cmd, check=True):
    """Run shell command in BASE_DIR and return stdout string."""
    res = subprocess.run(cmd, shell=True, text=True, encoding="utf-8", errors="replace", capture_output=True, cwd=BASE_DIR)
    if check and res.returncode != 0:
        err = (res.stderr or "").strip()
        raise RuntimeError(err or f"Command failed with code {res.returncode}")
    return (res.stdout or "").strip()

def get_current_version():
    ver_file = os.path.join(BASE_DIR, "version.txt")
    if os.path.exists(ver_file):
        try:
            with open(ver_file, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v: return v
        except Exception:
            pass
    return "R1.0.0.6"

def increment_version(ver_str):
    try:
        prefix = "R" if ver_str.startswith("R") else ""
        raw_num = ver_str.lstrip("Rv")
        parts = [int(p) for p in raw_num.split(".")]
        parts[-1] += 1
        return f"{prefix}{'.'.join(str(p) for p in parts)}"
    except Exception:
        return ver_str

# ---------------------------------------------------------------------------
# Deep Change & Function Analyzer
# ---------------------------------------------------------------------------
def analyze_git_changes():
    """
    Scans the repository for all modified/untracked files and extracts
    detailed function-level and resource-level changes.
    """
    raw_status = run_cmd("git status --porcelain", check=False)
    if not raw_status:
        return []

    file_reports = []
    for raw_line in raw_status.splitlines():
        trimmed = raw_line.strip()
        if not trimmed:
            continue
        parts = trimmed.split(None, 1)
        if len(parts) < 2:
            continue
        status_code = parts[0]
        filepath = parts[1].replace('"', '')
        full_path = os.path.join(BASE_DIR, filepath)

        change_type = "MODIFIED"
        if "?" in status_code:
            change_type = "NEW FILE"
        elif "D" in status_code:
            change_type = "DELETED"
        elif "A" in status_code:
            change_type = "ADDED"

        functions_found = []

        # Analyze Python files for function/class modifications
        if filepath.endswith(".py") and os.path.exists(full_path):
            if change_type == "NEW FILE":
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        tree = ast.parse(f.read(), filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            functions_found.append(f"def {node.name}()")
                        elif isinstance(node, ast.ClassDef):
                            functions_found.append(f"class {node.name}")
                except Exception:
                    pass
            elif change_type == "MODIFIED":
                # Check git diff for touched or new functions
                diff_out = run_cmd(f'git diff -U0 -- "{filepath}"', check=False)
                for d_line in diff_out.splitlines():
                    # Diff hunk function headers: @@ ... @@ def func():
                    hunk_match = re.search(r'@@\s+(?:def|class)\s+([A-Za-z0-9_]+)', d_line)
                    if hunk_match:
                        fn = hunk_match.group(1)
                        if f"def {fn}()" not in functions_found:
                            functions_found.append(f"def {fn}()")
                    # Direct additions: +def func_name
                    added_match = re.search(r'^\+\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(', d_line)
                    if added_match:
                        fn = added_match.group(1)
                        tag = f"def {fn}() [NEW]"
                        if tag not in functions_found and f"def {fn}()" not in functions_found:
                            functions_found.append(tag)

        file_reports.append({
            "status": change_type,
            "path": filepath,
            "functions": functions_found
        })

    return file_reports

# ---------------------------------------------------------------------------
# Modern Cyberpunk Tkinter GUI Application
# ---------------------------------------------------------------------------
class GitPushGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("R1 FLASH ULTRA ❖ GITHUB DEPLOYMENT MANAGER")
        self.root.geometry("880x680")
        self.root.minsize(800, 600)

        # Cyber Dark Color Palette
        self.clr_bg = "#030712"        # Slate 950
        self.clr_card = "#0f172a"      # Slate 900
        self.clr_header = "#020617"    # Pitch dark
        self.clr_border = "#1e293b"    # Slate 800
        self.clr_cyan = "#06b6d4"      # Neon Cyan
        self.clr_cyan_bright = "#22d3ee"
        self.clr_green = "#10b981"     # Emerald Green
        self.clr_green_hover = "#059669"
        self.clr_dim = "#94a3b8"       # Slate 400
        self.clr_text = "#f8fafc"      # White
        self.clr_red = "#f43f5e"       # Rose

        self.root.configure(bg=self.clr_bg)

        # Config and state
        self.cfg = load_config()
        self.detected_changes = []
        self.is_busy = False

        self.setup_ui()
        self.center_window()
        self.log("SYSTEM READY. Click '[ 🔍 DETECT NEW UPDATE ]' to scan local code changes.")

    def center_window(self):
        self.root.update_idletasks()
        w = 880
        h = 680
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2) - 30
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def setup_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg=self.clr_header, padx=20, pady=12, highlightthickness=1, highlightbackground=self.clr_border)
        header.pack(fill=tk.X)

        title_box = tk.Frame(header, bg=self.clr_header)
        title_box.pack(side=tk.LEFT)

        tk.Label(title_box, text="R1 FLASH ULTRA", fg=self.clr_cyan, bg=self.clr_header,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(title_box, text="GITHUB LIVE CLOUD DEPLOYMENT & SYNC ENGINE", fg=self.clr_dim, bg=self.clr_header,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        # Remote Target Badge
        repo_badge = tk.Frame(header, bg=self.clr_card, padx=12, pady=6, highlightthickness=1, highlightbackground=self.clr_border)
        repo_badge.pack(side=tk.RIGHT)
        
        repo_name = f"{self.cfg.get('repo_owner', 'rscomputer204-netizen')}/{self.cfg.get('repo_name', 'rscomputer204-netizen-R1_BIOS_Programmer')}"
        tk.Label(repo_badge, text=f"REPO: {repo_name}", fg=self.clr_cyan_bright, bg=self.clr_card, font=("Segoe UI", 8, "bold")).pack(anchor="e")
        tk.Label(repo_badge, text="BRANCH: main  •  STATUS: AUTH TOKEN OK", fg=self.clr_green, bg=self.clr_card, font=("Segoe UI", 8)).pack(anchor="e")

        # 2. Main Content Container
        content = tk.Frame(self.root, bg=self.clr_bg, padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        # Action Buttons Banner (Dual Button Control)
        btn_banner = tk.Frame(content, bg=self.clr_card, padx=14, pady=12, highlightthickness=1, highlightbackground=self.clr_border)
        btn_banner.pack(fill=tk.X, pady=(0, 10))

        # Button 1: DETECT NEW UPDATE
        self.btn_detect = tk.Button(
            btn_banner, text="🔍  DETECT NEW UPDATE", bg=self.clr_cyan, fg="#000000",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=10, cursor="hand2",
            activebackground=self.clr_cyan_bright, activeforeground="#000000",
            command=self.on_detect_click
        )
        self.btn_detect.pack(side=tk.LEFT, padx=(0, 15))

        # Button 2: PUSH TO GITHUB (Initially Disabled)
        self.btn_push = tk.Button(
            btn_banner, text="🚀  PUSH TO GITHUB", bg="#1e293b", fg="#64748b",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=25, pady=10, cursor="arrow",
            state=tk.DISABLED, command=self.on_push_click
        )
        self.btn_push.pack(side=tk.LEFT)

        # Status Summary Label
        self.lbl_status_badge = tk.Label(btn_banner, text="Ready for scan", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 9, "bold"))
        self.lbl_status_badge.pack(side=tk.RIGHT, padx=5)

        # Split Container: Left Config Panel & Right Detected Changes View
        split_frame = tk.Frame(content, bg=self.clr_bg)
        split_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # --- LEFT PANEL: Version & Metadata ---
        left_panel = tk.Frame(split_frame, bg=self.clr_card, width=280, padx=14, pady=12, highlightthickness=1, highlightbackground=self.clr_border)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        tk.Label(left_panel, text="RELEASE METADATA", fg=self.clr_cyan, bg=self.clr_card, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 10))

        # Current Version
        cur_ver = get_current_version()
        tk.Label(left_panel, text="CURRENT VERSION", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 8)).pack(anchor="w")
        self.lbl_cur_ver = tk.Label(left_panel, text=cur_ver, fg=self.clr_text, bg=self.clr_card, font=("Segoe UI", 12, "bold"))
        self.lbl_cur_ver.pack(anchor="w", pady=(0, 8))

        # Next Version Entry
        tk.Label(left_panel, text="NEXT RELEASE VERSION", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 8)).pack(anchor="w")
        self.var_next_ver = tk.StringVar(value=increment_version(cur_ver))
        ver_entry = tk.Entry(left_panel, textvariable=self.var_next_ver, bg=self.clr_bg, fg=self.clr_green,
                             insertbackground=self.clr_cyan, relief="flat", font=("Segoe UI", 10, "bold"),
                             highlightthickness=1, highlightbackground=self.clr_border)
        ver_entry.pack(fill=tk.X, pady=(2, 12), ipady=4, padx=1)

        # Changelog / Commit Message
        tk.Label(left_panel, text="UPDATE DESCRIPTION / NOTE", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 8)).pack(anchor="w")
        self.txt_changelog = tk.Text(left_panel, bg=self.clr_bg, fg=self.clr_text, insertbackground=self.clr_cyan,
                                     relief="flat", font=("Segoe UI", 9), height=7,
                                     highlightthickness=1, highlightbackground=self.clr_border)
        self.txt_changelog.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.txt_changelog.insert(tk.END, "Added new features, optimized performance, and fixed identified bugs.")

        # --- RIGHT PANEL: Detected Changes & Function Tree ---
        right_panel = tk.Frame(split_frame, bg=self.clr_card, padx=14, pady=12, highlightthickness=1, highlightbackground=self.clr_border)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        header_right = tk.Frame(right_panel, bg=self.clr_card)
        header_right.pack(fill=tk.X, pady=(0, 8))
        tk.Label(header_right, text="CODE & RESOURCE CHANGE INSPECTOR", fg=self.clr_cyan, bg=self.clr_card, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_changes_count = tk.Label(header_right, text="0 Changes", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 8))
        self.lbl_changes_count.pack(side=tk.RIGHT)

        # Text View for Changes Analysis
        self.txt_inspector = tk.Text(
            right_panel, bg=self.clr_bg, fg=self.clr_text, relief="flat",
            font=("Consolas", 9), wrap="none",
            highlightthickness=1, highlightbackground=self.clr_border
        )
        self.txt_inspector.pack(fill=tk.BOTH, expand=True)

        # Configure custom text tags for syntax highlighting
        self.txt_inspector.tag_config("title", foreground="#38bdf8", font=("Consolas", 9, "bold"))
        self.txt_inspector.tag_config("file_mod", foreground="#22d3ee", font=("Consolas", 9, "bold"))
        self.txt_inspector.tag_config("file_new", foreground="#34d399", font=("Consolas", 9, "bold"))
        self.txt_inspector.tag_config("func", foreground="#a7f3d0", font=("Consolas", 9))
        self.txt_inspector.tag_config("dim", foreground="#64748b")
        self.txt_inspector.tag_config("success", foreground="#10b981", font=("Consolas", 10, "bold"))

        self.txt_inspector.insert(tk.END, "Click '[ 🔍 DETECT NEW UPDATE ]' to scan code modifications...\n", "dim")

        # 3. Bottom Terminal Log Console
        console_frame = tk.Frame(self.root, bg=self.clr_card, padx=14, pady=10, highlightthickness=1, highlightbackground=self.clr_border)
        console_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(0, 12))

        tk.Label(console_frame, text="ACTIVITY LOG", fg=self.clr_dim, bg=self.clr_card, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        
        self.txt_console = tk.Text(
            console_frame, bg=self.clr_bg, fg="#cbd5e1", relief="flat",
            font=("Consolas", 8), height=5, wrap="word",
            highlightthickness=1, highlightbackground=self.clr_border
        )
        self.txt_console.pack(fill=tk.X)
        self.txt_console.tag_config("info", foreground="#38bdf8")
        self.txt_console.tag_config("ok", foreground="#34d399")
        self.txt_console.tag_config("warn", foreground="#facc15")
        self.txt_console.tag_config("err", foreground="#f87171")

    def log(self, msg, tag="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_console.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.txt_console.see(tk.END)

    # -----------------------------------------------------------------------
    # Step 1: Detect New Update Action
    # -----------------------------------------------------------------------
    def on_detect_click(self):
        if self.is_busy:
            return

        self.btn_detect.config(state=tk.DISABLED, text="⏳  SCANNING...")
        self.lbl_status_badge.config(text="Analyzing repository diff...", fg=self.clr_cyan)
        self.txt_inspector.delete(1.0, tk.END)
        self.txt_inspector.insert(tk.END, "Scanning code files, functions, and resources...\n\n", "dim")
        self.log("Running Deep Code Diff & Function Scanner...")

        def worker():
            try:
                # Ensure git directory is recognized as safe
                run_cmd(f'git config --global --add safe.directory "{BASE_DIR}"', check=False)

                reports = analyze_git_changes()
                self.root.after(0, lambda: self.render_detection_results(reports))
            except Exception as e:
                self.root.after(0, lambda: self.render_detection_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def render_detection_results(self, reports):
        self.btn_detect.config(state=tk.NORMAL, text="🔍  DETECT NEW UPDATE")
        self.detected_changes = reports

        self.txt_inspector.delete(1.0, tk.END)

        if not reports:
            # NO CHANGES DETECTED
            self.lbl_status_badge.config(text="● Up to date (No changes)", fg=self.clr_green)
            self.lbl_changes_count.config(text="0 Changes")

            self.txt_inspector.insert(tk.END, "✔  EVERYTHING IS UP TO DATE!\n\n", "success")
            self.txt_inspector.insert(tk.END, "• No modified code, new functions, or added files found.\n", "dim")
            self.txt_inspector.insert(tk.END, f"• GitHub repository ({self.cfg.get('repo_name')}) is completely synchronized.\n", "dim")
            self.txt_inspector.insert(tk.END, "\nTo deploy an update, make code changes first, then click Detect again.", "dim")

            # Keep Push Button Disabled
            self.btn_push.config(
                state=tk.DISABLED, bg="#1e293b", fg="#64748b",
                cursor="arrow"
            )
            self.log("Scan complete: No changes detected.", "ok")
            return

        # CHANGES DETECTED: Render Detailed Function & File List
        self.lbl_status_badge.config(text=f"● {len(reports)} File(s) Changed", fg=self.clr_cyan_bright)
        self.lbl_changes_count.config(text=f"{len(reports)} File(s)")

        self.txt_inspector.insert(tk.END, f"DETECTED {len(reports)} MODIFIED / NEW ITEM(S):\n\n", "title")

        total_funcs = 0
        for item in reports:
            st = item["status"]
            path = item["path"]
            funcs = item["functions"]
            total_funcs += len(funcs)

            if st == "NEW FILE":
                self.txt_inspector.insert(tk.END, f" ➕ [NEW]      {path}\n", "file_new")
            else:
                self.txt_inspector.insert(tk.END, f" 📝 [MODIFIED] {path}\n", "file_mod")

            if funcs:
                for fn in funcs:
                    self.txt_inspector.insert(tk.END, f"    └── {fn}\n", "func")
            self.txt_inspector.insert(tk.END, "\n")

        # Refresh Next Version Field automatically
        cur = get_current_version()
        self.lbl_cur_ver.config(text=cur)
        self.var_next_ver.set(increment_version(cur))

        # ENABLE THE PUSH BUTTON WITH VIBRANT GREEN
        self.btn_push.config(
            state=tk.NORMAL, bg=self.clr_green, fg="#ffffff",
            activebackground=self.clr_green_hover, activeforeground="#ffffff",
            cursor="hand2"
        )

        msg = f"Scan complete: Found {len(reports)} changed file(s)"
        if total_funcs > 0:
            msg += f" with {total_funcs} function updates."
        self.log(msg, "ok")
        self.log("Push to GitHub is now ENABLED. Click 'PUSH TO GITHUB' to deploy.")

    def render_detection_error(self, err_msg):
        self.btn_detect.config(state=tk.NORMAL, text="🔍  DETECT NEW UPDATE")
        self.lbl_status_badge.config(text="Scan Error", fg=self.clr_red)
        self.txt_inspector.delete(1.0, tk.END)
        self.txt_inspector.insert(tk.END, f"ERROR DURING SCAN:\n{err_msg}\n", "dim")
        self.log(f"Detection failed: {err_msg}", "err")

    # -----------------------------------------------------------------------
    # Step 2: Push to GitHub Action
    # -----------------------------------------------------------------------
    def on_push_click(self):
        if self.is_busy or not self.detected_changes:
            return

        target_ver = self.var_next_ver.get().strip()
        if not target_ver:
            messagebox.showwarning("VERSION REQUIRED", "Please enter a valid version string (e.g. R1.0.0.7).")
            return

        changelog = self.txt_changelog.get("1.0", tk.END).strip()
        if not changelog:
            changelog = f"Auto-Update: Release {target_ver} with latest features"

        # Lock UI
        self.is_busy = True
        self.btn_detect.config(state=tk.DISABLED)
        self.btn_push.config(state=tk.DISABLED, text="⏳  UPLOADING TO GITHUB...")
        self.lbl_status_badge.config(text="Packaging & Pushing...", fg=self.clr_cyan)
        self.log(f"Starting GitHub deployment for version {target_ver}...")

        def push_worker():
            try:
                # 1. Update version.txt
                with open(os.path.join(BASE_DIR, "version.txt"), "w", encoding="utf-8") as f:
                    f.write(target_ver)
                py_ver_path = os.path.join(BASE_DIR, "python_version", "version.txt")
                if os.path.exists(os.path.dirname(py_ver_path)):
                    with open(py_ver_path, "w", encoding="utf-8") as f:
                        f.write(target_ver)
                self.log(f"Updated local version to {target_ver}.")

                # 2. Package complete update.zip with executable and scripts
                self.log("Creating update.zip bundle with executables and scripts...")
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

                # Ensure python_version source is also copied into payload/python_version
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

                # Collect all individual files inside payload for manifest
                manifest_files = []
                for root, dirs, files in os.walk(payload_content):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    for f in files:
                        abs_p = os.path.join(root, f)
                        rel_p = os.path.relpath(abs_p, payload_content).replace("\\", "/")
                        manifest_files.append(rel_p)

                manifest = {
                    "version": target_ver,
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
                self.log("update.zip bundle generated successfully.")

                # 3. Update version.json
                repo_owner = self.cfg.get("repo_owner", "rscomputer204-netizen")
                repo_name = self.cfg.get("repo_name", "rscomputer204-netizen-R1_BIOS_Programmer")
                branch = self.cfg.get("branch", "main")
                token = self.cfg.get("github_token", "")

                raw_zip_url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/{branch}/update.zip"
                ver_info = {
                    "version": target_ver,
                    "url": raw_zip_url,
                    "changelog": changelog,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(os.path.join(BASE_DIR, "version.json"), "w", encoding="utf-8") as f:
                    json.dump(ver_info, f, indent=4)
                self.log("version.json updated with latest changelog & metadata.")

                # 4. Git Add & Commit
                self.log("Committing changes locally...")
                run_cmd("git add .")
                run_cmd(f'git commit -m "{changelog} (v{target_ver})"')

                # 5. Push to GitHub
                self.log(f"Pushing to remote origin [{branch}]...")
                auth_url = f"https://{token}@github.com/{repo_owner}/{repo_name}.git"
                run_cmd(f'git push "{auth_url}" {branch}')

                self.root.after(0, lambda: self.render_push_success(target_ver))
            except Exception as e:
                self.root.after(0, lambda: self.render_push_error(str(e)))
            finally:
                self.is_busy = False

        threading.Thread(target=push_worker, daemon=True).start()

    def render_push_success(self, version):
        self.btn_detect.config(state=tk.NORMAL)
        self.btn_push.config(state=tk.DISABLED, text="🚀  PUSH TO GITHUB", bg="#1e293b", fg="#64748b", cursor="arrow")
        self.lbl_status_badge.config(text=f"✔ Pushed v{version} to GitHub!", fg=self.clr_green)
        self.lbl_cur_ver.config(text=version)
        self.detected_changes = []

        self.txt_inspector.delete(1.0, tk.END)
        self.txt_inspector.insert(tk.END, "🎉  DEPLOYMENT COMPLETED SUCCESSFULLY!\n\n", "success")
        self.txt_inspector.insert(tk.END, f"• All code changes & functions are now LIVE on GitHub.\n", "title")
        self.txt_inspector.insert(tk.END, f"• Repository: https://github.com/{self.cfg.get('repo_owner')}/{self.cfg.get('repo_name')}\n", "dim")
        self.txt_inspector.insert(tk.END, f"• Release Version: {version}\n", "file_new")
        self.txt_inspector.insert(tk.END, f"• Users can now click 'UPDATE' in their software to receive this update instantly.\n", "dim")

        self.log(f"SUCCESS: Version {version} successfully pushed to GitHub!", "ok")
        messagebox.showinfo("DEPLOYMENT SUCCESS", f"All updates have been successfully pushed to GitHub!\n\nVersion: {version}\nUsers can now update their software.")

    def render_push_error(self, err_msg):
        self.btn_detect.config(state=tk.NORMAL)
        self.btn_push.config(state=tk.NORMAL, text="🚀  PUSH TO GITHUB")
        self.lbl_status_badge.config(text="Push Failed", fg=self.clr_red)
        self.log(f"ERROR during GitHub Push: {err_msg}", "err")
        messagebox.showerror("PUSH FAILED", f"Could not push to GitHub:\n\n{err_msg}")

# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    app = GitPushGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
