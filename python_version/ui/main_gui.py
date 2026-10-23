import sys
import os

# --- LIVE GITHUB UPDATE HOT-RELOAD HOOK ---
# When running as frozen PyInstaller EXE, dynamically run the latest disk-based main_gui.py
# so that all GitHub updates downloaded by updater.exe take effect immediately on automatic restart!
if getattr(sys, 'frozen', False) and not getattr(sys, '_r1_hot_reloaded', False):
    sys._r1_hot_reloaded = True
    base_dir = os.path.dirname(sys.executable)
    disk_gui = os.path.join(base_dir, "python_version", "ui", "main_gui.py")
    if os.path.exists(disk_gui):
        py_dir = os.path.join(base_dir, "python_version")
        if py_dir not in sys.path:
            sys.path.insert(0, py_dir)
        import runpy
        runpy.run_path(disk_gui, run_name="__main__")
        sys.exit(0)

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import winsound
import time
import threading
import requests
import zipfile
import subprocess
import shutil
import tempfile
import json
import re

def is_newer_version(remote_ver, current_ver):
    """Compares version strings robustly (e.g. R1.0.2.1 vs R1.0.2.0)."""
    try:
        def parse(v):
            cleaned = re.sub(r'[^0-9.]', '', str(v))
            return [int(x) for x in cleaned.split('.') if x.isdigit()]
        r = parse(remote_ver)
        c = parse(current_ver)
        if not c:
            return True
        return r > c
    except Exception:
        return str(remote_ver) > str(current_ver)

# Import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import dialog_fixer
from utils.chip_db import ChipDatabase
from utils.version_manager import VersionManager
from hardware.ft232h_handler import FT232HDriver
from core.spi25_handler import SPI25Handler
from core.i2c_handler import I2CHandler
from core.logic_manager import LogicManager
from PIL import Image, ImageTk

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-alpha", 0.9)
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#010409", foreground="#58a6ff", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 8, "bold"), padx=5, pady=2)
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()





class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=kwargs.get("bg", "#000000"), highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=kwargs.get("bg", "#000000"))

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Smooth Scroll Physics State
        self.velocity = 0.0
        self.current_pos = 0.0
        self.is_animating = False
        self.friction = 0.85 # 0.0 to 1.0 (Higher = more slide)
        self.sensitivity = 0.002 # Tune for speed
        
        # Bind mousewheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        # FIX: Only scroll if mouse is actually over THIS specific frame
        if not self.winfo_exists(): return

        try:
            # global mouse coordinates
            ptr_x, ptr_y = self.winfo_pointerxy()
            
            # widget strict bounding box
            win_x = self.winfo_rootx()
            win_y = self.winfo_rooty()
            win_w = self.winfo_width()
            win_h = self.winfo_height()

            # Hit Test: Is mouse inside this frame?
            if (win_x <= ptr_x <= win_x + win_w) and (win_y <= ptr_y <= win_y + win_h):
                 # Add momentum instead of direct scroll
                 # Windows delta is normally +-120. Normalize.
                 delta = event.delta
                 if abs(delta) >= 120: delta = delta / 120
                 
                 self.velocity -= delta * self.sensitivity
                 
                 # Cap velocity to prevent insane speeds
                 max_v = 0.05
                 if self.velocity > max_v: self.velocity = max_v
                 if self.velocity < -max_v: self.velocity = -max_v

                 if not self.is_animating:
                     self.is_animating = True
                     self._process_inertia()
                     
        except Exception:
            pass

    def _process_inertia(self):
        if not self.winfo_exists(): 
            self.is_animating = False
            return

        # Apply friction
        self.velocity *= self.friction
        
        # Stop if too slow
        if abs(self.velocity) < 0.0001:
            self.velocity = 0
            self.is_animating = False
            return

        # Get current scroll position (tuple: start, end)
        # We only care about start (0.0 to 1.0)
        try:
            current = self.canvas.yview()[0]
            
            # Predict next pos
            new_pos = current + self.velocity
            
            # Boundary Clamp (Elastic bounce optional, but let's stick to hard clamp for now)
            if new_pos < 0: 
                new_pos = 0
                self.velocity = 0
            elif new_pos > 1: 
                # This logic is tricky because yview()[1] is the bottom.
                # Ideally, we clamp such that we don't scroll past end.
                # Canvas yview_moveto handles clamping implicitly effectively enough typically.
                # But strictly: new_pos should not exceed 1.0
                pass 
                
            self.canvas.yview_moveto(new_pos)
            
            # Next frame
            self.after(10, self._process_inertia)
            
        except Exception:
            self.is_animating = False


class WatermarkTerminal(tk.Frame):
    """Cyberpunk Terminal with Translucent Watermark Background Logo"""
    def __init__(self, parent, logo_path=None, bg_color="#010409", *args, **kwargs):
        super().__init__(parent, bg=bg_color, *args, **kwargs)
        self.bg_color = bg_color
        self.logo_path = logo_path
        self.raw_logo = None
        
        if logo_path and os.path.exists(logo_path):
            try:
                base = Image.open(logo_path).convert("RGBA")
                r, g, b, a = base.split()
                # 16% opacity watermark for clean background visibility
                a = a.point(lambda p: int(p * 0.16))
                base.putalpha(a)
                self.raw_logo = base
            except Exception as e:
                print(f"Terminal Logo Error: {e}")
                
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_scroll_command)
        self.canvas.configure(yscrollcommand=self._on_canvas_yview)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.lines = []
        self.line_height = 20
        self.text_start_y = 15
        self.text_start_x = 15
        self.logo_photo = None
        self.watermark_id = None
        
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _on_scroll_command(self, *args):
        self.canvas.yview(*args)
        self._update_watermark_position()

    def _on_canvas_yview(self, *args):
        self.scrollbar.set(*args)
        self._update_watermark_position()

    def _update_watermark_position(self):
        if self.watermark_id is not None:
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w > 10 and h > 10:
                cx = self.canvas.canvasx(w / 2)
                cy = self.canvas.canvasy(h / 2)
                self.canvas.coords(self.watermark_id, cx, cy)
                self.canvas.tag_lower(self.watermark_id)

    def _on_resize(self, event):
        w, h = event.width, event.height
        if self.raw_logo and w > 60 and h > 60:
            target_size = min(int(min(w, h) * 0.94), 630)
            if target_size > 40:
                resized = self.raw_logo.resize((target_size, target_size), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(resized)
                if self.watermark_id is None:
                    self.watermark_id = self.canvas.create_image(w // 2, h // 2, image=self.logo_photo, anchor="center")
                else:
                    self.canvas.itemconfig(self.watermark_id, image=self.logo_photo)
                self.canvas.tag_lower(self.watermark_id)
        self._update_scroll_region()
        self._update_watermark_position()

    def _update_scroll_region(self):
        total_h = self.text_start_y + len(self.lines) * self.line_height + 30
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), max(total_h, self.canvas.winfo_height())))

    def insert(self, index, text, tag=None):
        split_lines = text.split("\n")
        for l in split_lines:
            if not l and l == split_lines[-1]:
                continue
            y = self.text_start_y + len(self.lines) * self.line_height
            
            # Smart Cyber Color Scheme
            fg = "#00FF41" # Neon Green
            if "ERROR" in l or "FATAL" in l or "FAIL" in l:
                fg = "#FF4444"
            elif "SUCCESS" in l or "COMPLETE" in l or "PASSED" in l:
                fg = "#00FFCC"
            elif "SYSTEM" in l or "HARDWARE" in l or "TARGET" in l:
                fg = "#58A6FF"
            elif "IDENTIFY" in l or "DETECTED" in l:
                fg = "#FFD700"
            elif "NOTICE" in l or "WARNING" in l:
                fg = "#FFA500"
                
            tid = self.canvas.create_text(
                self.text_start_x, y, text=l, anchor="w", fill=fg, font=("Consolas", 10, "bold")
            )
            self.lines.append(tid)
            
        self._update_scroll_region()
        self.see("end")

    def see(self, index):
        self.canvas.yview_moveto(1.0)
        self._update_watermark_position()
        
    def tag_config(self, *args, **kwargs):
        pass

    def delete(self, *args):
        for tid in self.lines:
            self.canvas.delete(tid)
        self.lines.clear()
        self._update_scroll_region()
        self._update_watermark_position()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._update_watermark_position()


class CyberFlashUltra:
    def __init__(self, root):
        self.root = root
        self.root.title("R1 FLASH ULTRA - FT232H SPECIAL EDITION")
        self.root.geometry("1100x650") # Smaller default for laptops
        self.root.minsize(950, 600)    # Allow smaller resizing
        self.root.configure(bg="#010409") # Total Black
        
        # Maximize on startup (Windows compatible)
        try:
            self.root.state('zoomed')
        except:
            pass

        # Versioning & Update Settings
        self.app_version = VersionManager.get_version()
        self.update_url = "https://raw.githubusercontent.com/rscomputer204-netizen/rscomputer204-netizen-R1_BIOS_Programmer/main/version.json"
        # Database and System Log
        # Database and System Log
        if getattr(sys, 'frozen', False):
            # If frozen (EXE), root is where the EXE lives
            root_dir = os.path.dirname(sys.executable)
            # In flat build, assets are in root_dir/assets, so ui_dir should treat root as base
            ui_dir = root_dir
        else:
            # If source, calculate from file path
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(ui_dir) # Up to 'python_version/'
            
        self.db = ChipDatabase(os.path.join(root_dir, "chiplist.xml"))
        
        # System Log (The Brain)
        from core.system_log import SystemLog
        self.syslog = SystemLog(root_dir)


        # Hardware Driver
        try:
            self.hw = FT232HDriver(log_callback=self.log_write)
            self.spi = SPI25Handler(self.hw)
            self.i2c = I2CHandler(self.hw)
        except Exception as e:
            self.hw = None
            self.spi = None
            self.i2c = None
            print(f"Driver Error: {e}")

        # State Info
        self.current_protocol = "SPI"
        self.selected_chip = None
        self.buffer_data = None
        self.is_connected = False
        self.io_busy = False
        self.monitor_visible = True
        self.hex_visible = True  # Responsive layout flag for hex panel
        self.filtered_chips = []
        self.op_start_time = None
        self.in_auto_sequence = False
        
        # Action Icons (Only needed for connection/etc now)
        # Action Icons (Only needed for connection/etc now)
        self.icons = {}
        assets_dir = os.path.join(ui_dir, "assets")
        
        # Load Main Application Logo
        self.logo_img = None
        self.header_logo = None
        logo_path = os.path.join(assets_dir, "logo.png")
        self.logo_path = logo_path
        if os.path.exists(logo_path):
            # For Window Icon
            icon_img = Image.open(logo_path)
            self.logo_photo = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self.logo_photo)
            ico_path = os.path.join(assets_dir, "logo.ico")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    pass
            
            # For Header Display (Resized)
            header_img = icon_img.resize((45, 45), Image.Resampling.LANCZOS)
            self.header_logo = ImageTk.PhotoImage(header_img)

        # Removed read/write/verify/identify from icon loading to force text mode
        for icon_name in ["wiring"]: 
            icon_path = os.path.join(assets_dir, f"{icon_name}.png")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((24, 24), Image.Resampling.LANCZOS)
                self.icons[icon_name.upper()] = ImageTk.PhotoImage(img)
        
        # Button Text Mapping
        self.btn_map = {
            "IDENTIFY": "SM", 
            "READ": "RD", 
            "WRITE": "WR", 
            "VERIFY": "VFY"
        }
        
        # IC Parameters
        self.ic_address_var = tk.StringVar(value="")
        self.ic_series_var = tk.StringVar(value="")
        self.ic_size_var = tk.StringVar(value="")
        self.ic_page_var = tk.StringVar(value="")
        self.ic_voltage_var = tk.StringVar(value="")
        self.ic_capacity_var = tk.StringVar(value="")

        # AUTO Sequence Configuration
        self.auto_erase_var = tk.BooleanVar(value=True)
        self.auto_write_var = tk.BooleanVar(value=True)
        self.auto_verify_var = tk.BooleanVar(value=True)
        
        # Filter State
        self.man_var = tk.StringVar(value="ALL")

        # --- SETTINGS VARIABLES ---
        self.config_hex_viewer = tk.BooleanVar(value=True)
        self.config_pc_sound = tk.BooleanVar(value=True)
        self.config_hw_buzzer = tk.BooleanVar(value=False)

        # UI Colors (Ultra Modern / Stealth theme)
        self.clr_bg = "#010409"   # GitHub Darkest Black
        self.clr_card = "#0d1117"  # GitHub Dark Sidebar
        self.clr_header = "#161b22"
        self.clr_accent = "#58a6ff" # Soft Blue (Pro looking)
        self.clr_neon_blue = "#00f2ff" # Vibrant Cyan
        self.clr_neon_red = "#ff2d55"
        self.clr_text = "#c9d1d9"
        self.clr_dim = "#8b949e"
        self.clr_border = "#30363d"

        self.setup_styles()
        
        # --- LAYOUT MANAGER STATE ---
        self.layout_initialized = False
        self.layout_sash_h = 340 # Default Sidebar
        self.layout_sash_v = 0   # Will calculate dynamically
        
        self.create_layout()
        
        # Initialize Layout Manager (Replaces naive after(200))
        self.initialize_layout_manager()

        # --- SOUND SYSTEM INJECTION (NON-DESTRUCTIVE) ---
        self.initialize_sound_system()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Custom Scrollbar
        style.configure("Vertical.TScrollbar", gripcount=0, background="#21262d", 
                        darkcolor="#21262d", lightcolor="#21262d", 
                        troughcolor="#010409", bordercolor="#30363d", arrowcolor="#8b949e")
        
        # Custom Progressbar
        style.configure("Cyber.Horizontal.TProgressbar", 
                        troughcolor="#010409", 
                        background=self.clr_neon_blue, 
                        bordercolor="#30363d", 
                        lightcolor=self.clr_neon_blue, 
                        darkcolor=self.clr_neon_blue)

        # Custom Combobox
        style.configure("TCombobox", fieldbackground="#0d1117", background="#0d1117", 
                        foreground="white", arrowcolor=self.clr_neon_blue, bordercolor=self.clr_border)

    def create_layout(self):
        # --- Top Navigation / Header ---
        self.header = tk.Frame(self.root, bg=self.clr_header)
        self.header.pack(side=tk.TOP, fill=tk.X)
        
        # 1. Top Bar: App Branding on Left, System Controls on Right
        self.header_top_row = tk.Frame(self.header, bg=self.clr_header)
        self.header_top_row.pack(side=tk.TOP, fill=tk.X, padx=(20, 20), pady=(8, 4))
        
        # App Branding
        brand_frame = tk.Frame(self.header_top_row, bg=self.clr_header)
        brand_frame.pack(side=tk.LEFT)
        
        if self.header_logo:
            tk.Label(brand_frame, image=self.header_logo, bg=self.clr_header).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(brand_frame, text="R1 FLASH", bg=self.clr_header, fg=self.clr_neon_blue, 
                 font=("Orbitron", 20, "bold")).pack(side=tk.LEFT)
        tk.Label(brand_frame, text="ULTRA", bg=self.clr_header, fg="white", 
                 font=("Orbitron", 12)).pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))

        # Right-side Buttons (Master & System)
        right_btn_frame = tk.Frame(self.header_top_row, bg=self.clr_header)
        right_btn_frame.pack(side=tk.RIGHT)
        
        # Slot in top row between brand and right controls (for wide screen single row)
        self.top_nav_slot = tk.Frame(self.header_top_row, bg=self.clr_header)
        self.top_nav_slot.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # 2. Bottom Toolbar Frame (Dedicated full-width row along user red mark when in small window)
        self.bottom_nav_slot = tk.Frame(self.header, bg=self.clr_header)

        # Main Action Buttons Container
        self.main_btn_frame = tk.Frame(self.top_nav_slot, bg=self.clr_header)
        self.main_btn_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store button configs to repack them responsive
        self.nav_buttons = []
        
        # Define buttons to add
        buttons = [
            ("SAVE", self.action_save),
            ("OPEN", self.action_open),
            ("IDENTIFY", self.action_read_id),
            ("READ", self.action_read),
            ("WRITE", self.action_write),
            ("VERIFY", self.action_verify),
            ("ERASE", self.action_erase, True),
            ("UNLOCK", self.action_unlock),
            ("WIRING", self.action_connection)
        ]

        for b_info in buttons:
            is_danger = False
            if len(b_info) > 2: is_danger = b_info[2]
            self.create_nav_btn(b_info[0], b_info[1], is_danger)

        # AUTO Group
        auto_group = tk.Frame(right_btn_frame, bg=self.clr_header)
        auto_group.pack(side=tk.LEFT)
        

        
        # --- BIOS EDITOR INTEGRATION (LEFT SIDE) ---
        btn_editor = tk.Button(auto_group, text="BIOS EDITOR", bg=self.clr_card, fg="#d2a8ff", 
                               activebackground="#d2a8ff", activeforeground="black",
                               relief="flat", font=("Orbitron", 9, "bold"), 
                               padx=10, pady=5, cursor="hand2", 
                               command=self.launch_bios_editor,
                               highlightthickness=1, highlightbackground="#d2a8ff")
        btn_editor.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(btn_editor, "Open Standalone BIOS Editor (BETA)")
        
        # --- SETTINGS BUTTON ---
        btn_settings = tk.Button(auto_group, text="⚙", bg=self.clr_card, fg="#d2a8ff", 
                               activebackground="#d2a8ff", activeforeground="black",
                               relief="flat", font=("Segoe UI", 12, "bold"), 
                               padx=5, pady=2, cursor="hand2", 
                               command=self.show_settings_dialog,
                               highlightthickness=1, highlightbackground="#d2a8ff")
        btn_settings.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(btn_settings, "Settings Configuration")
        
        # Separator for Update
        tk.Frame(right_btn_frame, bg=self.clr_border, width=2, height=30).pack(side=tk.LEFT, padx=15)
        
        self.add_nav_btn_legacy(right_btn_frame, "UPDATE", self.action_update)

        # Bottom Border Accent
        accent_bar = tk.Frame(self.root, bg=self.clr_neon_blue, height=2)
        accent_bar.pack(fill=tk.X)

        # --- Main Workspace (Paned Layout) ---
        self.h_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.h_pane.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Left Column: Selection (Now Scrollable)
        # We need a container frame for the sidebar because ScrollableFrame uses pack
        left_col_container = tk.Frame(self.h_pane, bg=self.clr_bg, width=350)
        # No pack, PanedWindow handles it
        
        # [VERSION SYSTEM] Fixed Version Label at Bottom of Sidebar
        version_frame = tk.Frame(left_col_container, bg=self.clr_bg)
        version_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        tk.Label(version_frame, text=f"VER: {self.app_version}", bg=self.clr_bg, fg=self.clr_dim, 
                 font=("Consolas", 8), anchor="w").pack(side=tk.LEFT, padx=15, pady=2)

        self.left_scroll = ScrollableFrame(left_col_container, bg=self.clr_bg)
        self.left_scroll.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # We attach items to self.left_scroll.scrollable_frame instead of left_col
        left_col = self.left_scroll.scrollable_frame # Alias for easier replacement
        # Important: Calculate width for inner frame to avoid weird shrinking
        def _update_scroll_region(event):
            self.left_scroll.canvas.itemconfig(self.left_scroll.window_id, width=left_col_container.winfo_width()-20)
        left_col_container.bind('<Configure>', _update_scroll_region)

        # Add Sidebar to Horizontal Pane
        self.h_pane.add(left_col_container, weight=0)

        # --- TOP ENGINE ROW (Split horizontally in half: Hardware Engine & Protocol Engine) ---
        top_engines_row = tk.Frame(left_col, bg=self.clr_bg)
        top_engines_row.pack(fill=tk.X, pady=(0, 3))
        top_engines_row.columnconfigure(0, weight=1)
        top_engines_row.columnconfigure(1, weight=1)

        # 1. Left Box: HARDWARE ENGINE
        status_card = tk.Frame(top_engines_row, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        
        tk.Label(status_card, text="HARDWARE ENGINE", bg=self.clr_card, fg=self.clr_dim, 
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.status_label = tk.Label(status_card, text="NOT CONNECT", bg=self.clr_card, fg=self.clr_neon_red, 
                                     font=("Segoe UI", 11, "bold"))
        self.status_label.pack(anchor="w", padx=10, pady=(3, 1))
        
        self.buffer_info_label = tk.Label(status_card, text="BUFFER: EMPTY", bg=self.clr_card, fg=self.clr_dim, 
                                        font=("Segoe UI", 7, "bold"))
        self.buffer_info_label.pack(anchor="w", padx=10, pady=(0, 8))

        # 2. Right Box: PROTOCOL ENGINE
        proto_card = tk.Frame(top_engines_row, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        proto_card.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        
        tk.Label(proto_card, text="PROTOCOL ENGINE", bg=self.clr_card, fg=self.clr_dim, 
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        
        self.proto_btn_frame = tk.Frame(proto_card, bg=self.clr_card)
        self.proto_btn_frame.pack(fill=tk.X, padx=10, pady=(6, 8))
        
        self.proto_display = tk.Button(self.proto_btn_frame, text=f"✔ {self.current_protocol}", 
                                     bg=self.clr_neon_blue, fg="black",
                                     activebackground=self.clr_neon_blue, activeforeground="black",
                                     relief="flat", font=("Orbitron", 8, "bold"),
                                     command=self.show_proto_menu)
        self.proto_display.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        # 3-Dot Menu Button
        self.proto_menu_btn = tk.Button(self.proto_btn_frame, text="⋮", bg=self.clr_bg, fg=self.clr_text,
                                      activebackground=self.clr_card, activeforeground=self.clr_neon_blue,
                                      relief="flat", font=("Segoe UI", 11, "bold"), width=2,
                                      command=self.show_proto_menu)
        self.proto_menu_btn.pack(side=tk.LEFT)

        # Create the Menu (Hidden)
        self.proto_menu = tk.Menu(self.root, tearoff=0, bg=self.clr_card, fg="white", 
                                borderwidth=0, activebackground=self.clr_neon_blue, activeforeground="black")
        for p in ["SPI", "I2C"]:
            self.proto_menu.add_command(label=p, command=lambda proto=p: self.set_protocol_manual(proto))

        # --- AUTO ACTION / PROGRAMMING CARD (Below Top Engines Row) ---
        auto_card = tk.Frame(left_col, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        auto_card.pack(fill=tk.X, pady=(0, 3))

        auto_header_frame = tk.Frame(auto_card, bg=self.clr_card)
        auto_header_frame.pack(fill=tk.X, padx=15, pady=(8, 2))

        tk.Label(auto_header_frame, text="AUTO PROGRAMMING", bg=self.clr_card, fg=self.clr_dim, 
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)

        auto_body = tk.Frame(auto_card, bg=self.clr_card)
        auto_body.pack(fill=tk.X, padx=15, pady=(2, 8))

        # Big prominent AUTO button
        self.auto_btn = tk.Button(auto_body, text="⚡ AUTO", bg=self.clr_neon_blue, fg="black", 
                                  activebackground="white", activeforeground="black", 
                                  relief="flat", font=("Orbitron", 10, "bold"), 
                                  cursor="hand2", command=self.action_auto, pady=6)
        self.auto_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ToolTip(self.auto_btn, "Automatic Erase, Write & Verify Sequence")

        # Config ⋮ button
        self.config_btn = tk.Button(auto_body, text="⋮", bg=self.clr_bg, fg=self.clr_neon_blue, 
                                    activebackground=self.clr_neon_blue, activeforeground="black", 
                                    relief="flat", font=("Segoe UI", 12, "bold"), width=3,
                                    cursor="hand2", command=self.show_config_menu,
                                    highlightthickness=1, highlightbackground=self.clr_neon_blue)
        self.config_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.config_btn, "Auto Sequence Settings")

        # Quick Actions Stack (Read + Identify / Select)
        qa_frame = tk.Frame(auto_body, bg=self.clr_card)
        qa_frame.pack(side=tk.RIGHT)

        def create_mini_btn(text, cmd):
            w, h = 85, 23
            bg_color = self.clr_card
            accent_color = self.clr_neon_blue
            
            canvas = tk.Canvas(qa_frame, width=w, height=h, bg=bg_color, highlightthickness=0, cursor="hand2")
            canvas.pack(side=tk.TOP, pady=1)
            
            shadow = canvas.create_rectangle(3, 3, w, h, fill="#000000", outline="", stipple="gray50")
            body = canvas.create_rectangle(1, 1, w-1, h-1, fill=bg_color, outline=accent_color, width=1)
            label = canvas.create_text(w/2, h/2, text=text, fill=accent_color, font=("Orbitron", 8, "bold"))
            
            def on_enter(e):
                canvas.move(body, -1, -1)
                canvas.move(label, -1, -1)
                canvas.itemconfig(body, outline="#00ffff", width=1)
                canvas.itemconfig(label, fill="#00ffff")
                
            def on_leave(e):
                canvas.coords(body, 1, 1, w-1, h-1)
                canvas.coords(label, w/2, h/2)
                canvas.itemconfig(body, outline=accent_color, width=1)
                canvas.itemconfig(label, fill=accent_color)
                
            def on_click(e):
                canvas.itemconfig(body, fill=accent_color)
                canvas.itemconfig(label, fill="black")
                self.root.after(100, lambda: canvas.itemconfig(body, fill=bg_color))
                self.root.after(100, lambda: canvas.itemconfig(label, fill="#00ffff"))
                if cmd:
                    cmd()

            canvas.bind("<Enter>", on_enter)
            canvas.bind("<Leave>", on_leave)
            canvas.bind("<Button-1>", on_click)
            
            return canvas

        self.mini_btn_read = create_mini_btn("READ", self.action_read)
        self.mini_btn_id = create_mini_btn("IDENTIFY", self.action_read_id)
        self.mini_btn_select = create_mini_btn("SELECT", self.show_i2c_chip_selector)
        self.mini_btn_select.pack_forget()
            
        self.update_proto_ui()

        # Chip Selection Card (Simplified)
        chip_card = tk.Frame(left_col, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        chip_card.pack(fill=tk.X, pady=(0, 3))

        self.db_explorer_label = tk.Label(chip_card, text="SPI FLASH EXPLORER", bg=self.clr_card, fg="white", 
                 font=("Segoe UI", 9, "bold"))
        self.db_explorer_label.pack(anchor="w", padx=20, pady=(8, 2))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        
        search_bg = tk.Frame(chip_card, bg=self.clr_bg, highlightbackground=self.clr_border, highlightthickness=1)
        search_bg.pack(fill=tk.X, padx=20, pady=2)
        
        tk.Entry(search_bg, textvariable=self.search_var, bg=self.clr_bg, fg="white", 
                 insertbackground=self.clr_neon_blue, borderwidth=0, font=("Segoe UI", 10)).pack(fill=tk.X, padx=10, pady=5)
        
        self.chip_list = tk.Listbox(chip_card, bg=self.clr_bg, fg=self.clr_text, height=3,
                                    borderwidth=0, highlightthickness=0, font=("Segoe UI", 9), 
                                    selectbackground=self.clr_neon_blue, selectforeground="black", exportselection=False)
        self.chip_list.pack(fill=tk.X, padx=20, pady=(2, 8))
        self.chip_list.bind("<<ListboxSelect>>", self.on_chip_select)

        # IC Parameter Panel (New Professional Section)
        self.volt_btns = {}
        self.active_manual_voltage = "OFF"

        def _build_ic_param_card(parent):
            card = tk.Frame(parent, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
            
            self.ic_param_label = tk.Label(card, text="IC PARAMETERS", bg=self.clr_card, fg="white", 
                     font=("Segoe UI", 9, "bold"))
            self.ic_param_label.pack(anchor="w", padx=20, pady=(15, 10))

            self.add_param_field(card, "ADDRESS", self.ic_address_var)
            self.add_param_field(card, "SERIES", self.ic_series_var)
            self.add_param_field(card, "SIZE (BYTES)", self.ic_size_var)
            self.add_param_field(card, "PAGE SIZE", self.ic_page_var)
            self.add_param_field(card, "VOLTAGE", self.ic_voltage_var)
            
            cap_frame = tk.Frame(card, bg=self.clr_card)
            cap_frame.pack(fill=tk.X, padx=20, pady=10)
            tk.Label(cap_frame, text="TOTAL CAPACITY", bg=self.clr_card, fg=self.clr_dim, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(cap_frame, textvariable=self.ic_capacity_var, bg=self.clr_card, fg=self.clr_neon_blue, font=("Orbitron", 14, "bold")).pack(anchor="w", pady=5)

            volt_ctrl_frame = tk.Frame(card, bg=self.clr_card)
            volt_ctrl_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
            
            btn_container = tk.Frame(volt_ctrl_frame, bg=self.clr_card)
            btn_container.pack(anchor="w")
            
            def create_volt_btn(voltage_str):
                lbl = tk.Label(btn_container, text=voltage_str, bg=self.clr_bg, fg=self.clr_dim,
                               font=("Orbitron", 10, "bold"), relief="solid", borderwidth=1, width=4,
                               cursor="arrow")
                lbl.pack(side=tk.LEFT, padx=(0, 10))
                if voltage_str not in self.volt_btns:
                    self.volt_btns[voltage_str] = []
                self.volt_btns[voltage_str].append(lbl)

            create_volt_btn("3.3")
            create_volt_btn("1.8")
            create_volt_btn("1.2")
            return card

        self.param_card_left = _build_ic_param_card(left_col)
        self.param_card_left.pack(fill=tk.BOTH, expand=True)

        # --- Right Panel (Main Structure) ---
        self.right_main_frame = tk.Frame(self.h_pane, bg=self.clr_bg)
        self.h_pane.add(self.right_main_frame, weight=1)

        # Progress Bar Frame (Bottom of right_main_frame, full width)
        prog_frame = tk.Frame(self.right_main_frame, bg=self.clr_bg, height=30)
        prog_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))
        prog_frame.pack_propagate(False)
        
        self.progress_pct_var = tk.StringVar(value="0%")
        self.progress_label = tk.Label(prog_frame, textvariable=self.progress_pct_var, bg=self.clr_bg, fg=self.clr_neon_blue, font=("Orbitron", 10, "bold"), width=5, anchor="e")
        self.progress_label.pack(side=tk.RIGHT, padx=(5, 0))

        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100, style="Cyber.Horizontal.TProgressbar")
        self.progress.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.root.after(1500, self._responsive_tracker)

        # Center Area (Tab Container)
        self.tab_container = tk.Frame(self.right_main_frame, bg=self.clr_bg)
        self.tab_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tab Button Bar (Pack BOTTOM first so buttons are ALWAYS visible and never pushed off!)
        self.tab_btn_bar = tk.Frame(self.tab_container, bg=self.clr_bg)
        self.tab_btn_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        # Helper for creating tab buttons
        def _create_tab_btn(parent, text, cmd):
            btn = tk.Button(parent, text=text, font=("Segoe UI", 12, "bold"), 
                            bg=self.clr_card, fg="white", relief="flat", width=12,
                            activebackground="white", activeforeground="black", cursor="hand2", command=cmd)
            btn.pack(side=tk.LEFT, padx=(0, 5))
            return btn

        self.btn_tab_log = _create_tab_btn(self.tab_btn_bar, "LOG", lambda: self.show_tab("LOG"))
        self.btn_tab_hex = _create_tab_btn(self.tab_btn_bar, "HEX", lambda: self.show_tab("HEX"))

        # Tab Content (Pack TOP expand second so it uses the remaining cavity above buttons)
        self.tab_content_frame = tk.Frame(self.tab_container, bg=self.clr_bg, highlightbackground=self.clr_border, highlightthickness=1)
        self.tab_content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Log Area with Translucent Watermark Logo Background
        self.log_container = tk.Frame(self.tab_content_frame, bg=self.clr_bg)
        self.log_area = WatermarkTerminal(self.log_container, logo_path=getattr(self, 'logo_path', None), bg_color=self.clr_bg)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 5))

        # Hex Area
        # Hex Area
        self.hex_frame = tk.Frame(self.tab_content_frame, bg=self.clr_bg)
        self.hex_text = scrolledtext.ScrolledText(self.hex_frame, bg=self.clr_bg, fg=self.clr_accent, 
                                                 font=("Consolas", 12), borderwidth=0, highlightthickness=0)
        self.hex_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.fill_dummy_hex()

        def _show_tab(tab_name):
            self.hex_frame.pack_forget()
            self.log_container.pack_forget()

            self.btn_tab_log.config(bg=self.clr_card if tab_name != "LOG" else "white", fg="white" if tab_name != "LOG" else "black")
            self.btn_tab_hex.config(bg=self.clr_card if tab_name != "HEX" else "white", fg="white" if tab_name != "HEX" else "black")

            if tab_name == "LOG":
                self.log_container.pack(fill=tk.BOTH, expand=True)
            elif tab_name == "HEX":
                self.hex_frame.pack(fill=tk.BOTH, expand=True)
                self.hex_text.yview_moveto(0.0)

        self.show_tab = _show_tab
        self.show_tab("LOG")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.log_write(f"SYSTEM: R1 FLASH ULTRA {self.app_version} READY.")
        
        # Start Real-Time Monitor
        self.start_monitor()
        
        # Check for Crash Recovery (System Brain)
        self.check_recovery()
        
        # Initialize default protocol layout (SPI Mode)
        self.switch_protocol_layout("SPI")

        # Silent automatic update check on application startup (delayed 3.0s for smooth launch)
        self.root.after(3000, self.auto_check_update_startup)

    def create_nav_btn(self, text, command, is_danger=False):
        # Store for loose packing
        self.nav_buttons.append({"text": text, "cmd": command, "danger": is_danger})

    def repack_header_buttons(self, event=None, force=False):
        try:
            current_width = self.root.winfo_width()
            if current_width < 200: current_width = 1100 
            
            curr_proto = getattr(self, "current_protocol", "SPI").upper()
            
            # Filter active buttons based on protocol
            active_buttons = []
            for btn_data in self.nav_buttons:
                btn_name = btn_data["text"].upper()
                if curr_proto == "I2C":
                    # In I2C mode: no IDENTIFY (no JEDEC auto-ID for 24-series) and no UNLOCK (SPI only)
                    if btn_name in ["IDENTIFY", "UNLOCK"]:
                        continue
                active_buttons.append(btn_data)

            # Available width in top row between brand and right controls
            top_available = current_width - 620
            
            # Needed width for all buttons in one single row
            needed_single_row_width = len(active_buttons) * 85
            
            # When screen is small / normal (< 1350px or top space isn't enough):
            # Move to bottom toolbar row (full width, exactly along the user's red mark)
            use_bottom_toolbar = (current_width < 1350) or (top_available < needed_single_row_width)
            
            layout_key = (use_bottom_toolbar, curr_proto, len(active_buttons))
            if not force and hasattr(self, "_last_layout_key") and self._last_layout_key == layout_key:
                return
            self._last_layout_key = layout_key

            # Clear buttons
            if hasattr(self, 'main_btn_frame') and self.main_btn_frame.winfo_exists():
                for widget in self.main_btn_frame.winfo_children():
                    widget.destroy()

            # Switch container parent
            if use_bottom_toolbar:
                if hasattr(self, 'top_nav_slot'):
                    self.top_nav_slot.pack_forget()
                if hasattr(self, 'bottom_nav_slot'):
                    self.bottom_nav_slot.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(2, 6))
                    if hasattr(self, 'main_btn_frame') and self.main_btn_frame.winfo_exists():
                        self.main_btn_frame.destroy()
                    self.main_btn_frame = tk.Frame(self.bottom_nav_slot, bg=self.clr_header)
                    self.main_btn_frame.pack(side=tk.LEFT)
            else:
                if hasattr(self, 'bottom_nav_slot'):
                    self.bottom_nav_slot.pack_forget()
                if hasattr(self, 'top_nav_slot'):
                    self.top_nav_slot.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
                    if hasattr(self, 'main_btn_frame') and self.main_btn_frame.winfo_exists():
                        self.main_btn_frame.destroy()
                    self.main_btn_frame = tk.Frame(self.top_nav_slot, bg=self.clr_header)
                    self.main_btn_frame.pack(side=tk.LEFT)

            # Add all buttons strictly in row 0 (single horizontal line)
            col = 0
            for btn_data in active_buttons:
                self._add_btn_to_frame(self.main_btn_frame, btn_data["text"], btn_data["cmd"], btn_data["danger"], 0, col)
                col += 1
        except Exception as e:
            print(f"Repack Error: {e}")

    def _add_btn_to_frame(self, parent, text, command, is_danger, row, col):
        clr = self.clr_neon_red if is_danger else self.clr_neon_blue
        
        # Check for Short Code Mapping
        display_text = self.btn_map.get(text, text)
        is_special = text in self.btn_map
        
        icon = self.icons.get(text)
        
        # Use grid instead of pack
        if icon and not is_special:
             btn = tk.Button(parent, image=icon, bg=self.clr_card, activebackground=clr,
                             relief="flat", cursor="hand2", command=command, 
                             highlightthickness=1, highlightbackground=clr, padx=10, pady=5)
             ToolTip(btn, text)
        else:
             # Regular or Special Text Button
             # Approx 20% larger for Special buttons (SM, RD, WR, VFY)
             # Base: 10px / 5px -> New: 12px / 7px
             padx = 12 if is_special else 10
             pady = 7 if is_special else 5
             font_size = 11 if is_special else 9 # Slightly larger font too
             
             btn = tk.Button(parent, text=display_text, bg=self.clr_card, fg=clr, activebackground=clr, 
                             activeforeground="black", relief="flat", font=("Orbitron", font_size, "bold"), 
                             padx=padx, pady=pady, cursor="hand2", command=command, highlightthickness=1, highlightbackground=clr)
             ToolTip(btn, text)
        
        btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")

    def add_nav_btn_legacy(self, parent, text, command, is_danger=False):
        clr = self.clr_neon_red if is_danger else self.clr_neon_blue
        
        display_text = self.btn_map.get(text, text)
        is_special = text in self.btn_map
        
        icon = self.icons.get(text)
        
        if text == "AUTO":
            # Extra prominent style for AUTO
            btn = tk.Button(parent, text=text, bg=self.clr_neon_blue, fg="black", activebackground="white", 
                            activeforeground="black", relief="flat", font=("Orbitron", 10, "bold"), 
                            padx=25, pady=8, cursor="hand2", command=command)
        elif icon and not is_special:
            # Icon-based button with tooltip
            btn = tk.Button(parent, image=icon, bg=self.clr_card, activebackground=clr,
                            relief="flat", cursor="hand2", command=command, 
                            highlightthickness=1, highlightbackground=clr, padx=10, pady=5)
            
            tooltip_txt = "SMART IDENTIFY" if text == "IDENTIFY" else text
            ToolTip(btn, tooltip_txt) # Universal tooltip for icon buttons
        else:
            padx = 12 if is_special else 15
            pady = 7 if is_special else 8
            font_size = 11 if is_special else 10
             
            btn = tk.Button(parent, text=display_text, bg=self.clr_card, fg=clr, activebackground=clr, 
                            activeforeground="black", relief="flat", font=("Orbitron", font_size, "bold"), 
                            padx=padx, pady=pady, cursor="hand2", command=command, highlightthickness=1, highlightbackground=clr)
            ToolTip(btn, text)
        btn.pack(side=tk.LEFT, padx=5)

    def check_recovery(self):
        suggestion = self.syslog.get_recovery_suggestion()
        if suggestion:
            self.log_write(f"SYSTEM_BRAIN: {suggestion}")
            self.notify_cyber("SYSTEM RECOVERY", suggestion, "WARNING")

    def _responsive_tracker(self):
        # Track software window state and width for responsive layout adjustments
        current_state = self.root.state()
        current_width = self.root.winfo_width()
        last_state = getattr(self, "_last_track_state", "")
        last_width = getattr(self, "_last_track_width", 0)
        
        if current_state != last_state or abs(current_width - last_width) > 30:
            self._last_track_state = current_state
            self._last_track_width = current_width
            self.repack_header_buttons()

        # Loop every 200ms to guarantee tracking works flawlessly
        self.root.after(200, self._responsive_tracker)

    def check_hardware(self):
        if self.io_busy: return 
        
        def _init_thread():
            try:
                # Give Windows PnP 500ms to stabilize USB driver endpoints after reconnect
                time.sleep(0.5)
                retries = 3
                success = False
                for i in range(retries):
                    try:
                        if self.hw:
                            self.hw.force_cleanup()
                            if self.hw.open():
                                print("SYSTEM: HARDWARE PINS FORCED TO SAFE STATE (LOW).")
                                self.hw.set_voltage_pins("OFF")
                                # Close handle so hardware is clean, idle, and ready for operations
                                self.hw.close()
                                success = True
                                break
                    except Exception as e:
                        print(f"RETRYING HARDWARE INIT... ({i+1}/{retries})")
                        time.sleep(0.4)
                
                if success:
                    self.root.after(0, lambda: winsound.Beep(1000, 200))
                else:
                    self.log_write("WARNING: FAILED TO AUTO-INITIALIZE PINS.")
            except Exception as e:
                self.log_write(f"CRITICAL: INIT THREAD FAILED: {e}")

        try:
            connected = False
            if self.hw and self.hw.list_devices() > 0:
                connected = True
            
            if connected != self.is_connected:
                self.is_connected = connected
                if connected:
                    self.status_label.config(text="CONNECTED", fg=self.clr_neon_blue)
                    self.log_write("SYSTEM: FT232H CONNECTED.")
                    threading.Thread(target=_init_thread, daemon=True).start()
                else:
                    self.status_label.config(text="NOT CONNECT", fg=self.clr_neon_red)
                    self.log_write("WARNING: FT232H DISCONNECTED.")
                    if self.hw:
                        try:
                            self.hw.force_cleanup()
                        except Exception:
                            pass
                    winsound.Beep(500, 400)
                    
        except Exception as e:
            pass

    def start_monitor(self):
        self.check_hardware()
        # Check every 2 seconds
        self.root.after(2000, self.start_monitor)

    def start_slideshow(self):
        pass

    def add_nav_btn_legacy(self, parent, text, command, is_danger=False):
        clr = self.clr_neon_red if is_danger else self.clr_neon_blue
        icon = self.icons.get(text)
        
        if text == "AUTO":
            # Extra prominent style for AUTO
            btn = tk.Button(parent, text=text, bg=self.clr_neon_blue, fg="black", activebackground="white", 
                            activeforeground="black", relief="flat", font=("Orbitron", 10, "bold"), 
                            padx=25, pady=8, cursor="hand2", command=command)
        elif icon:
            # Icon-based button with tooltip
            btn = tk.Button(parent, image=icon, bg=self.clr_card, activebackground=clr,
                            relief="flat", cursor="hand2", command=command, 
                            highlightthickness=1, highlightbackground=clr, padx=10, pady=5)
            
            tooltip_txt = "SMART IDENTIFY" if text == "IDENTIFY" else text
            ToolTip(btn, tooltip_txt) # Universal tooltip for icon buttons
        else:
            btn = tk.Button(parent, text=text, bg=self.clr_card, fg=clr, activebackground=clr, 
                            activeforeground="black", relief="flat", font=("Orbitron", 10, "bold"), 
                            padx=15, pady=8, cursor="hand2", command=command, highlightthickness=1, highlightbackground=clr)
        btn.pack(side=tk.LEFT, padx=5)

    def add_label(self, parent, text):
        tk.Label(parent, text=text, bg=self.clr_card, fg=self.clr_dim, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(5, 5))

    def refresh_chip_list(self):
        self.chip_list.delete(0, tk.END)
        man_filter = self.man_var.get() if hasattr(self, 'man_var') else "ALL"
        search_query = self.search_var.get().upper().strip()
        
        filtered = self.db.chips
        current_proto = getattr(self, "current_protocol", "SPI").upper()
        if current_proto == "I2C":
            filtered = [
                c for c in filtered 
                if c.get('protocol', '').upper() == "I2C" 
                or '24C' in str(c.get('name', '')).upper()
            ]
        else:
            filtered = [
                c for c in filtered 
                if c.get('protocol', '').upper() != "I2C"
                and '24C' not in str(c.get('name', '')).upper()
            ]
        
        if man_filter and man_filter != "ALL":
            filtered = [c for c in filtered if c['manufacturer'] == man_filter]
        
        if search_query:
            filtered = [c for c in filtered if search_query in c['name'].upper() or search_query in c.get('manufacturer', '').upper()]

        for chip in filtered[:500]:
            self.chip_list.insert(tk.END, f" {chip['manufacturer']} - {chip['name']}")

    def on_search_change(self, *args):
        self.refresh_chip_list()

    def start_op_timer(self):
        self.op_start_time = time.time()

    def get_op_elapsed(self):
        if getattr(self, 'op_start_time', None) is None:
            return 1
        elapsed = int(time.time() - self.op_start_time) + 1
        return max(1, elapsed)

    def stop_op_timer(self):
        self.op_start_time = None

    def log_write(self, msg):
        def _write():
            if getattr(self, 'op_start_time', None) is not None:
                sec = int(time.time() - self.op_start_time) + 1
                ts = f"[{sec:02d}s]"
            else:
                ts = "[01s]"
            self.log_area.insert(tk.END, f"{ts} {msg}\n", "status")
            self.log_area.see(tk.END)
        
        # Check if we are in the main thread
        if threading.current_thread() is threading.main_thread():
            _write()
        else:
            self.root.after(0, _write)

    def notify_cyber(self, title, message, type="INFO", duration=2000):
        # Create a translucent borderless toast/popup
        self.root.update_idletasks()
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.95) # Translucency
        toast.configure(bg=self.clr_card, highlightbackground=self.clr_neon_blue, highlightthickness=2)
        
        # Center the toast
        w = 420 if len(message) > 50 else 350
        h = 170 if ("\n" in message or len(message) > 50) else 150
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        toast.geometry(f"{w}x{h}+{x}+{y}")
        
        # Color based on type
        accent = self.clr_neon_red if type == "ERROR" else self.clr_neon_blue
        toast.configure(highlightbackground=accent)
        
        tk.Label(toast, text=title.upper(), bg=self.clr_header, fg=accent, 
                 font=("Orbitron", 10, "bold"), pady=8).pack(fill=tk.X)
        
        msg_frame = tk.Frame(toast, bg=self.clr_card)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(msg_frame, text=message, bg=self.clr_card, fg="white", 
                 font=("Segoe UI", 10), wraplength=w - 40, justify="center").pack(expand=True)
        
        btn = tk.Button(toast, text="DISMISS", bg=accent, fg="black", 
                        font=("Orbitron", 8, "bold"), relief="flat", padx=20, pady=5, 
                        command=toast.destroy, cursor="hand2")
        btn.pack(pady=(0, 15))
        
        # Auto-dismiss after duration
        if duration > 0:
            self.root.after(duration, lambda: toast.destroy() if toast.winfo_exists() else None)
        toast.lift()
        toast.focus_set()

    def confirm_cyber(self, title, message):
        # Translucent confirmation box
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-alpha", 0.95)
        win.configure(bg=self.clr_card, highlightbackground=self.clr_neon_blue, highlightthickness=2)
        
        w, h = 380, 180
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        
        tk.Label(win, text=title.upper(), bg=self.clr_header, fg=self.clr_neon_blue, 
                 font=("Orbitron", 10, "bold"), pady=8).pack(fill=tk.X)
        
        msg_frame = tk.Frame(win, bg=self.clr_card)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(msg_frame, text=message, bg=self.clr_card, fg="white", 
                 font=("Segoe UI", 10), wraplength=340, justify="center").pack(expand=True)
        
        btn_frame = tk.Frame(win, bg=self.clr_card)
        btn_frame.pack(pady=(0, 15))
        
        res = {"value": False}
        def set_res(val):
            res["value"] = val
            win.destroy()
            
        tk.Button(btn_frame, text="CONFIRM", bg=self.clr_neon_blue, fg="black", 
                  font=("Orbitron", 8, "bold"), relief="flat", padx=15, pady=5, 
                  command=lambda: set_res(True), cursor="hand2").pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="CANCEL", bg=self.clr_header, fg="white", 
                  font=("Orbitron", 8, "bold"), relief="flat", padx=15, pady=5, 
                  command=lambda: set_res(False), cursor="hand2").pack(side=tk.LEFT, padx=10)
        
        win.grab_set()
        win.lift()
        win.transient(self.root)
        self.root.wait_window(win)
        return res["value"]

    def reset_workspace(self):
        """Resets the entire workspace to a clean, fresh state (as if newly launched)."""
        # 1. Clear Memory Buffer and status label
        self.buffer_data = None
        if hasattr(self, 'buffer_info_label'):
            self.buffer_info_label.config(text="BUFFER: EMPTY", fg=self.clr_dim)
            
        # 2. Reset Hex View to initial dummy FF state
        if hasattr(self, 'fill_dummy_hex'):
            self.fill_dummy_hex()
            
        # 3. Clear Selected Chip & Parameter variables
        self.selected_chip = None
        self.ic_address_var.set("")
        self.ic_series_var.set("")
        self.ic_size_var.set("")
        self.ic_page_var.set("")
        self.ic_voltage_var.set("")
        self.ic_capacity_var.set("")
        
        # 4. Clear Search & Listbox Selection instantly
        had_search = bool(self.search_var.get())
        self.search_var.set("")
        if hasattr(self, 'chip_list'):
            try:
                self.chip_list.selection_clear(0, tk.END)
            except Exception:
                pass
        if had_search and hasattr(self, 'refresh_chip_list'):
            self.refresh_chip_list()
                
        # 5. Reset Progress Bar
        if hasattr(self, 'progress_var'):
            self.progress_var.set(0)
            
        # 6. Reset Voltage UI to OFF
        if hasattr(self, 'update_voltage_ui'):
            self.update_voltage_ui("OFF")

    def action_read_id(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        if getattr(self, "current_protocol", "SPI") == "I2C":
            self.log_write("NOTICE: I2C (24-SERIES EEPROM) DOES NOT SUPPORT JEDEC AUTO-ID.")
            self.log_write("NOTICE: OPENING I2C CHIP SELECTOR...")
            self.show_i2c_chip_selector()
            return
        if self.io_busy:
            return
            
        if not self.hw:
            self.log_write("ERROR: FTD2XX DRIVER NOT INITIALIZED.")
            return

        # Auto-Reset Workspace: Instant clean of previous IC data, buffer, hex & parameters
        self.reset_workspace()

        def identify_worker():
            self.start_op_timer()
            self.io_busy = True
            try:
                if not self.db.chips:
                    self.log_write("ERROR: CHIP DATABASE NOT LOADED. CHECK chiplist.xml")
                    return

                if not self.spi:
                    self.log_write("ERROR: PROTOCOL HANDLER NOT INITIALIZED.")
                    return

                if self.hw.open():
                    # 3.3V Pulse Logic for Smart ID
                    self.hw.set_voltage_pins("3.3V")
                    self.hw.set_led(True) # Turn ON LED during identify
                    self.root.after(0, lambda: self.update_voltage_ui("3.3"))
                    
                    time.sleep(0.05) # 50ms fast voltage stabilization
                    
                    try:
                        id_hex = self.spi.read_id()
                        
                        if id_hex and id_hex not in ["000000", "FFFFFF"]:
                            self._id_wait_event = threading.Event()
                            self.root.after(0, lambda: self.match_chip_by_id(id_hex))
                            # Block worker thread until user selects chip or closes dialog
                            self._id_wait_event.wait()
                            
                            if hasattr(self, 'sound_manager'):
                                self.sound_manager.play_event("IDENTIFY_COMPLETE")
                            
                            time.sleep(0.05) # Fast clean release
                        else:
                            self.log_write("IDENTIFY: NO IC DETECTED.")
                            self.root.after(0, lambda: self.notify_cyber("NOT DETECTED", "NO IC FOUND IN PROGRAMMER.", "INFO"))
                            time.sleep(0.05)
                            
                    finally:
                        self.hw.set_led(False) # Turn OFF LED
                        # hw.close() will automatically turn off voltage safely due to recent fixes
                        self.hw.close()
                        self.root.after(0, lambda: self.update_voltage_ui(self.ic_voltage_var.get() if self.selected_chip else "OFF"))
                else:
                    self.log_write("ERROR: IDENTIFY FAILED - DEVICE NOT DETECTED.")
                    self.root.after(0, lambda: self.notify_cyber("HARDWARE ERROR", "FT232H NOT FOUND. CHECK USB.", "ERROR"))
            except Exception as e:
                self.log_write(f"ERROR: IDENTIFY FAILED ({str(e)})")
            finally:
                self.stop_op_timer()
                self.io_busy = False
                self.root.after(0, lambda: self.progress_var.set(0))

        threading.Thread(target=identify_worker, daemon=True).start()

    def match_chip_by_id(self, hex_id):
        # Update UI instantly (Sidebar Sync)
        self.ic_address_var.set(f"0x{hex_id}")

        # Look for all chips matching this ID
        matches = [chip for chip in self.db.chips if chip['id'].upper() == hex_id]
        
        if not matches:
            self.log_write(f"IDENTIFY: UNKNOWN CHIP ID [0x{hex_id}]")
            self.notify_cyber("UNKNOWN ID", f"CHIP ID 0x{hex_id} IS NOT IN DATABASE.", "ERROR")
            if hasattr(self, '_id_wait_event') and self._id_wait_event:
                self._id_wait_event.set()
            return

        # Auto-select first match instead of opening dialog
        selected_chip = matches[0]
        self.log_write(f"IDENTIFY: DETECTED {selected_chip['name']} ({selected_chip['manufacturer']}) [0x{hex_id}]")
        
        # Apply selection to main UI
        self.search_var.set(selected_chip['name'])
        self.select_chip(selected_chip)
        
        self.notify_cyber("CHIP SELECTED", f"{selected_chip['name']}\n{selected_chip['manufacturer']}", "INFO")
        
        if hasattr(self, '_id_wait_event') and self._id_wait_event:
            self._id_wait_event.set()

    def show_chip_selection_dialog(self, chips):
        # Ensure focus and prevent multiple dialogs
        if hasattr(self, '_id_dialog') and self._id_dialog.winfo_exists():
            self._id_dialog.destroy()
            
        self._id_dialog = dialog = tk.Toplevel(self.root)
        dialog.title("Find IC")
        dialog.geometry("450x550")
        dialog.configure(bg=self.clr_card)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 225
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 275
        dialog.geometry(f"+{x}+{y}")
        
        # Professional Header
        title_frame = tk.Frame(dialog, bg=self.clr_header)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="CHIP SELECTION REQUIRED", bg=self.clr_header, fg=self.clr_neon_blue, 
                 font=("Orbitron", 10, "bold"), pady=10).pack()

        # List Area (No extra search filter needed, just select from matches)
        list_frame = tk.Frame(dialog, bg=self.clr_bg, highlightbackground=self.clr_border, highlightthickness=1)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=10)

        listbox = tk.Listbox(list_frame, bg=self.clr_bg, fg=self.clr_text, selectbackground=self.clr_neon_blue,
                             selectforeground="black", font=("Segoe UI", 10), borderwidth=0, highlightthickness=0, exportselection=False)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)

        self._current_matches = chips
        for chip in self._current_matches:
            listbox.insert(tk.END, f" {chip['manufacturer']} - {chip['name']}")
        
        if self._current_matches:
            listbox.selection_set(0)


        def on_close_dialog():
            if hasattr(self, '_id_wait_event') and self._id_wait_event:
                self._id_wait_event.set()
                self._id_wait_event = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close_dialog)

        def on_confirm(event=None):
            selection = listbox.curselection()
            if selection:
                selected_chip = self._current_matches[selection[0]]
                self.log_write(f"SUCCESS: SELECTED {selected_chip['manufacturer']} {selected_chip['name']}")
                
                # Apply selection to main UI
                self.search_var.set(selected_chip['name'])
                self.select_chip(selected_chip)
                
                on_close_dialog()
                self.notify_cyber("IC CONFIGURED", f"{selected_chip['name']} READY FOR OPERATIONS.", "INFO")

        # Double click or Enter to select
        listbox.bind("<Double-Button-1>", on_confirm)
        dialog.bind("<Return>", on_confirm)

        # Select Button
        select_btn = tk.Button(dialog, text="SELECT IC & READY", bg=self.clr_neon_blue, fg="black", 
                               activebackground="white", activeforeground="black",
                               font=("Orbitron", 9, "bold"), relief="flat", pady=10,
                               command=on_confirm, cursor="hand2")
        select_btn.pack(pady=(10, 20), padx=25, fill=tk.X)

    def show_progress_dialog(self, title, total_size, task_callback):
        # Reset and initialize bottom main progress bar
        self.progress_var.set(0)
        if hasattr(self, 'progress_pct_var'):
            self.progress_pct_var.set("0%")

        stop_flag = {"stop": False}

        def worker():
            def update_progress(current, status_text=""):
                if total_size > 0:
                    pct = (current / total_size) * 100
                else:
                    pct = 0
                pct = max(0.0, min(100.0, float(pct)))
                
                # Update main UI progress bar and percentage indicator
                self.root.after(0, lambda: self.progress_var.set(pct))
                if hasattr(self, 'progress_pct_var'):
                    self.root.after(0, lambda p=pct: self.progress_pct_var.set(f"{int(p)}%"))

            try:
                task_callback(update_progress, stop_flag)
            finally:
                # Keep 100% visible for 1.2 seconds, then reset
                def _cleanup():
                    if not getattr(self, 'io_busy', False):
                        self.progress_var.set(0)
                        if hasattr(self, 'progress_pct_var'):
                            self.progress_pct_var.set("0%")
                self.root.after(1200, _cleanup)

        threading.Thread(target=worker, daemon=True).start()

    def manual_voltage_override(self, voltage_str):
        pass # Non-clickable indicator

    def update_voltage_ui(self, active_voltage_str):
        # Sync the UI indicators based on active voltage from database
        for v_str, btn_list in self.volt_btns.items():
            for btn in btn_list:
                if active_voltage_str and v_str in active_voltage_str and active_voltage_str != "OFF":
                    btn.config(bg=self.clr_neon_blue, fg="black")
                else:
                    btn.config(bg=self.clr_bg, fg=self.clr_dim)

    def apply_current_voltage(self):
        target_volt = self.ic_voltage_var.get()
        if not target_volt:
            target_volt = "3.3" # fallback
                 
        # Format string to match hardware logic ("3.3V" instead of "3.3")
        hw_volt = f"{target_volt}V" if "V" not in target_volt else target_volt
        ui_volt = target_volt.replace("V", "")
        
        self.hw.set_voltage_pins(hw_volt)
        
        # [Patch] Configure 4-Byte Addressing for large chips
        if getattr(self, "current_protocol", "") == "SPI" and getattr(self, "spi", None) and self.selected_chip:
            try:
                size = int(self.selected_chip.get('size', 0))
                if size > 16777216:
                    self.spi.address_bytes = 4
                    self.log_write("SPI: AUTOMATIC 4-BYTE ADDRESSING ENABLED FOR >16MB CHIP.")
                else:
                    self.spi.address_bytes = 3
            except Exception as e:
                pass
                
        self.root.after(0, lambda: self.update_voltage_ui(ui_volt))
        time.sleep(0.1) # Let voltage settle

    def show_i2c_chip_selector(self):
        """Displays a modal dialog to select an I2C EEPROM chip manually."""
        win = tk.Toplevel(self.root)
        win.title("SELECT I2C EEPROM CHIP")
        win.geometry("450x550")
        win.configure(bg=self.clr_bg)
        win.transient(self.root)
        win.grab_set()

        # Title
        tk.Label(win, text="I2C EEPROM DATABASE", bg=self.clr_bg, fg=self.clr_neon_blue, font=("Orbitron", 13, "bold")).pack(pady=(15, 4))
        tk.Label(win, text="24-Series I2C EEPROMs do not support Auto-ID.\nPlease select your chip model from the list below.", 
                 bg=self.clr_bg, fg=self.clr_dim, font=("Segoe UI", 9), justify=tk.CENTER).pack(pady=(0, 10))

        # Search Box
        search_frame = tk.Frame(win, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        search_frame.pack(fill=tk.X, padx=20, pady=5)
        search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=search_var, bg=self.clr_card, fg="white", 
                 insertbackground=self.clr_neon_blue, borderwidth=0, font=("Segoe UI", 10)).pack(fill=tk.X, padx=10, pady=6)

        # Listbox Container
        list_frame = tk.Frame(win, bg=self.clr_bg)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.clr_bg, troughcolor=self.clr_card, activebackground=self.clr_neon_blue)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        chip_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, bg=self.clr_card, fg="white", 
                               borderwidth=0, highlightthickness=1, highlightbackground=self.clr_border,
                               selectbackground=self.clr_neon_blue, selectforeground="black", font=("Segoe UI", 10))
        chip_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=chip_list.yview)

        # Filter I2C chips
        i2c_chips = []
        for c in self.db.chips:
            proto = str(c.get('protocol', '')).upper()
            name = str(c.get('name', '')).upper()
            if proto == 'I2C' or '24C' in name:
                i2c_chips.append(c)
        
        def refresh_list(*args):
            chip_list.delete(0, tk.END)
            query = search_var.get().upper().strip()
            for c in i2c_chips:
                c_name = str(c.get('name', '')).upper()
                c_man = str(c.get('manufacturer', '')).upper()
                if not query or query in c_name or query in c_man:
                    chip_list.insert(tk.END, f"{c.get('manufacturer', 'UNKNOWN')} - {c.get('name', 'UNKNOWN')}")
                    
        search_var.trace_add("write", refresh_list)
        refresh_list()

        def on_select(event=None):
            selection = chip_list.curselection()
            if selection:
                val = chip_list.get(selection[0])
                parts = val.split(" - ")
                if len(parts) >= 2:
                    man, name = parts[0].strip(), parts[1].strip()
                    for c in i2c_chips:
                        if c['name'] == name and c['manufacturer'] == man:
                            self.select_chip(c)
                            self.log_write(f"CHIP SELECTED: {man} {name} (I2C)")
                            self.notify_cyber("CHIP SELECTED", f"Target set to: {name}", "INFO")
                            win.destroy()
                            return

        chip_list.bind("<Double-Button-1>", on_select)
        
        # Select Button
        btn_select = tk.Button(win, text="SELECT CHIP", bg=self.clr_neon_blue, fg="black", 
                               activebackground="white", activeforeground="black",
                               relief="flat", font=("Orbitron", 10, "bold"), cursor="hand2", command=on_select, pady=6)
        btn_select.pack(fill=tk.X, padx=20, pady=(0, 15))

    def on_chip_select(self, event):
        selection = self.chip_list.curselection()
        if selection:
            index = selection[0]
            chip_text = self.chip_list.get(index)
            # Fix: Handle possible spaces and different formats
            try:
                parts = chip_text.strip().split(" - ")
                if len(parts) >= 2:
                    man, name = parts[0], parts[1]
                    for chip in self.db.chips:
                        if chip['name'] == name and chip['manufacturer'] == man:
                            self.select_chip(chip)
                            break
            except:
                pass

    def add_param_field(self, parent, label_text, var):
        frame = tk.Frame(parent, bg=self.clr_card)
        frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(frame, text=label_text, bg=self.clr_card, fg=self.clr_dim, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        
        entry_bg = tk.Frame(frame, bg=self.clr_bg, highlightbackground=self.clr_border, highlightthickness=1)
        entry_bg.pack(fill=tk.X, pady=2)
        
        tk.Entry(entry_bg, textvariable=var, bg=self.clr_bg, fg="white", 
                 insertbackground=self.clr_neon_blue, borderwidth=0, font=("Segoe UI", 9)).pack(fill=tk.X, padx=8, pady=4)

    def select_chip(self, chip):
        if not self.buffer_data:
            self.buffer_data = None
            self.hex_text.delete(1.0, tk.END)
            self.fill_dummy_hex()
            # Reset Status Label explicitly
            self.buffer_info_label.config(text="BUFFER: EMPTY", fg=self.clr_dim)
        else:
            b_len = len(self.buffer_data)
            size_str = f"{b_len / (1024*1024):.2f} MB" if b_len >= 1024*1024 else f"{b_len // 1024} KB"
            self.buffer_info_label.config(text=f"BUFFER: {size_str}", fg=self.clr_neon_blue)
        
        # Reset Capacity display until calced
        self.ic_capacity_var.set("")
        
        self.selected_chip = chip
        
        # Determine protocol
        proto = str(chip.get('protocol', '')).upper()
        cmd = str(chip.get('spicmd', '')).lower()
        name = str(chip['name']).upper()
        
        detected_proto = "I2C" if (proto == "I2C" or '24' in cmd or 'i2c' in cmd or '24' in name) else "SPI"
        self.current_protocol = detected_proto
        if hasattr(self, 'repack_header_buttons'):
            self.repack_header_buttons(force=True)
            
        # Update Protocol Mini Quick Actions in Sidebar
        if hasattr(self, 'mini_btn_id') and hasattr(self, 'mini_btn_select'):
            if self.current_protocol == "I2C":
                self.mini_btn_id.pack_forget()
                self.mini_btn_select.pack(side=tk.TOP, pady=2)
            else:
                self.mini_btn_select.pack_forget()
                self.mini_btn_id.pack(side=tk.TOP, pady=2)

        # Update Database Explorer Header
        if hasattr(self, 'db_explorer_label'):
            if self.current_protocol == "I2C":
                self.db_explorer_label.config(text="I2C EEPROM EXPLORER")
            else:
                self.db_explorer_label.config(text="SPI FLASH EXPLORER")

        # Update IC Parameters Header
        if hasattr(self, 'ic_param_label'):
            if self.current_protocol == "I2C":
                self.ic_param_label.config(text="I2C EEPROM PARAMETERS")
            else:
                self.ic_param_label.config(text="IC PARAMETERS")
            
        # Update IC Parameters
        if self.current_protocol == "I2C":
            self.ic_address_var.set("0x50")
            self.ic_series_var.set(chip.get('manufacturer', '24Cxx') + " I2C")
            self.ic_size_var.set(str(chip['size']))
            self.ic_page_var.set(str(chip.get('page', '16')))
        else:
            self.ic_series_var.set(chip.get('manufacturer', 'UNKNOWN') + " SPI")
            self.ic_size_var.set(str(chip['size']))
            self.ic_page_var.set(str(chip.get('page', '256')))
        
        # Dynamic Voltage Parsing
        if "_1.8V" in name:
            self.ic_voltage_var.set("1.8V")
        elif "_3.3V" in name:
            self.ic_voltage_var.set("3.3V")
        elif "_2.5V" in name:
            self.ic_voltage_var.set("2.5V")
        elif "_5V" in name:
            self.ic_voltage_var.set("5V")
        else:
            # Fallback based on simple string search if suffix is missing
            self.ic_voltage_var.set("1.8V" if "1.8V" in name else "3.3V")
        
        # Calculate MB Capacity
        size_bytes = int(chip['size'])
        if size_bytes >= 1024 * 1024:
            mb = size_bytes / (1024 * 1024)
            self.ic_capacity_var.set(f"{mb:g} MB")
        else:
            kb = size_bytes / 1024
            self.ic_capacity_var.set(f"{kb:g} KB")
        
        self.update_voltage_ui(self.ic_voltage_var.get())
        self.update_proto_ui()

    def is_buffer_valid(self, op_name="OPERATION"):
        """Thread-safe buffer validation with main-thread reporting."""
        if self.buffer_data is None or len(self.buffer_data) == 0:
            msg = f"CRITICAL: {op_name} ABORTED. DATA BUFFER IS EMPTY!"
            self.log_write(msg)
            
            # Use root.after to ensure messagebox always runs on main thread
            def show_err():
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
                messagebox.showerror("IO ERROR", f"CANNOT EXECUTE {op_name}!\n\nReason: No data found in memory buffer.\n\nPlease 'OPEN' a file or 'READ' a chip first.")
            
            self.root.after(0, show_err)
            return False
        return True

    def switch_protocol_layout(self, proto):
        """Dynamically adapts UI layout and visible controls based on active protocol."""
        self.current_protocol = proto
        self.update_proto_ui()
        
        # 1. Update Top Header Navigation Bar (Hides IDENTIFY and UNLOCK in I2C)
        if hasattr(self, 'repack_header_buttons'):
            self.repack_header_buttons(force=True)
            
        # 2. Update Protocol Mini Quick Actions in Sidebar
        if hasattr(self, 'mini_btn_id') and hasattr(self, 'mini_btn_select'):
            if proto == "I2C":
                self.mini_btn_id.pack_forget()
                self.mini_btn_select.pack(side=tk.TOP, pady=2)
            else:
                self.mini_btn_select.pack_forget()
                self.mini_btn_id.pack(side=tk.TOP, pady=2)

        # 3. Update Database Explorer Header
        if hasattr(self, 'db_explorer_label'):
            if proto == "I2C":
                self.db_explorer_label.config(text="I2C EEPROM EXPLORER")
            else:
                self.db_explorer_label.config(text="SPI FLASH EXPLORER")

        # 4. Update IC Parameters Header
        if hasattr(self, 'ic_param_label'):
            if proto == "I2C":
                self.ic_param_label.config(text="I2C EEPROM PARAMETERS")
            else:
                self.ic_param_label.config(text="IC PARAMETERS")

        # 5. Clear or reset selected chip if mismatched
        if self.selected_chip:
            chip_proto = str(self.selected_chip.get('protocol', '')).upper()
            chip_name = str(self.selected_chip.get('name', '')).upper()
            is_i2c_chip = (chip_proto == "I2C" or '24' in chip_name)
            if proto == "I2C" and not is_i2c_chip:
                self.selected_chip = None
                self.ic_address_var.set("")
                self.ic_series_var.set("")
                self.ic_size_var.set("")
                self.ic_capacity_var.set("")
            elif proto == "SPI" and is_i2c_chip:
                self.selected_chip = None
                self.ic_address_var.set("")
                self.ic_series_var.set("")
                self.ic_size_var.set("")
                self.ic_capacity_var.set("")

        # 6. Refresh sidebar chip list with protocol filtering
        self.refresh_chip_list()

        # 7. Log status and notify
        if proto == "I2C":
            self.log_write("SYSTEM: PROTOCOL SET TO I2C EEPROM. (IDENTIFY/UNLOCK HIDDEN).")
            self.notify_cyber("I2C MODE", "Layout adapted for 24-Series I2C EEPROM.\nOnly READ, WRITE, ERASE, VERIFY active.", "INFO")
            self.show_i2c_chip_selector()
        else:
            self.log_write("SYSTEM: PROTOCOL SET TO SPI FLASH.")

    def set_protocol_manual(self, proto):
        self.switch_protocol_layout(proto)

    def update_proto_ui(self):
        self.proto_display.config(text=f"✔ {self.current_protocol}")

    def show_proto_menu(self):
        try:
            x = self.proto_menu_btn.winfo_rootx()
            y = self.proto_menu_btn.winfo_rooty() + self.proto_menu_btn.winfo_height() + 5
            self.proto_menu.tk_popup(x, y)
        finally:
            self.proto_menu.grab_release()

    def action_unlock(self):
        if not self.selected_chip: 
            self.notify_cyber("NOTICE", "PLEASE SELECT A CHIP FIRST.", "ERROR")
            return
        if self.current_protocol != "SPI":
            self.notify_cyber("INFO", "UNLOCK IS ONLY FOR SPI CHIPS.")
            return
            
        if self.hw.open():
            self.log_write("SYSTEM: UNLOCKING CHIP (WRITING 00h TO STATUS REGISTER)...")
            self.hw.init_mpsse()
            self.hw.set_spi_speed(1) # Safe speed for unlock
            # Send Write Enable (06h)
            self.hw.spi_write_read([0x06])
            # Write Status Register (01h) with 00h
            self.hw.spi_write_read([0x01, 0x00])
            self.log_write("SUCCESS: CHIP UNLOCKED / PROTECTION REMOVED.")
            self.hw.close()

    def action_open(self):
        from tkinter import filedialog
        supported = [("BIOS/IC Files", "*.bin;*.rom;*.cap;*.fd"), ("All supported", "*.bin;*.rom;*.cap;*.fd")]
        file_path = dialog_fixer.ask_open_filename_safe(self.root, filetypes=supported)
        
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ['.bin', '.rom', '.cap', '.fd']:
                self.notify_cyber("UNSUPPORTED FILE", f"This file cannot support: {os.path.basename(file_path)}\nSupported: .bin, .rom, .cap, .fd", "ERROR")
                self.log_write(f"ERROR: UNSUPPORTED FILE TYPE ({ext})")
                return

            # Clear previous buffer data to free memory
            self.buffer_data = None
            self.hex_text.delete(1.0, tk.END)
            self.root.update_idletasks()
            
            try:
                with open(file_path, 'rb') as f:
                    self.buffer_data = bytearray(f.read())
                    self.update_hex_view(self.buffer_data)
                    b_len = len(self.buffer_data)
                    size_str = f"{b_len / (1024*1024):.2f} MB" if b_len >= 1024*1024 else f"{b_len // 1024} KB"
                    self.log_write(f"FILE: LOADED {os.path.basename(file_path)} ({size_str})")
                    # [SYSTEM LOG] Track opened file
                    self.syslog.log_operation("OPEN", "SUCCESS", path=file_path, size=len(self.buffer_data))
                    
                    # [Patch] Validate Size on Field Load
                    if self.selected_chip:
                        is_safe, msg = LogicManager.validate_safe_write(self.selected_chip['size'], len(self.buffer_data))
                        if not is_safe:
                            self.root.after(100, lambda: self.notify_cyber("SAFETY WARNING", "FILE LARGER THAN CHIP! WRITING WILL BE BLOCKED.", "ERROR"))
            except Exception as e:
                self.log_write(f"ERROR: COULD NOT LOAD FILE - {str(e)}")
                self.syslog.log_operation("OPEN", "FAILED", path=file_path, error=str(e))

    def action_save(self):
        if not self.buffer_data:
            self.notify_cyber("NOTICE", "NO DATA IN BUFFER TO SAVE.", "ERROR")
            return
            
        from tkinter import filedialog
        supported = [("Binary file", "*.bin"), ("ROM file", "*.rom"), ("CAP file", "*.cap"), ("Flash Descriptor", "*.fd")]
        file_path = dialog_fixer.ask_save_as_filename_safe(self.root, defaultextension=".bin", filetypes=supported)
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self.buffer_data)
                self.log_write(f"FILE: SAVED {os.path.basename(file_path)}")
                self.notify_cyber("SUCCESS", "DATA SAVED SUCCESSFULLY.")
                # [SYSTEM LOG] Track saved file
                self.syslog.log_operation("SAVE", "SUCCESS", path=file_path, size=len(self.buffer_data))
            except Exception as e:
                self.log_write(f"ERROR: FAILED TO SAVE FILE - {str(e)}")
                self.notify_cyber("SAVE ERROR", f"COULD NOT SAVE FILE: {str(e)}", "ERROR")
                self.syslog.log_operation("SAVE", "FAILED", path=file_path, error=str(e))

    def action_read(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        if not self.selected_chip:
            self.sound_manager.play_event("ERROR")
            self.notify_cyber("NOTICE", "PLEASE SELECT TARGET CHIP.", "ERROR")
            return
        
        if self.io_busy: return
        
        size = int(self.selected_chip['size'])
        chip_name = self.selected_chip['name']

        def read_task(update_cb, stop_flag):
            self.start_op_timer()
            self.io_busy = True
            self.log_write(f"READ: READING FROM {chip_name}...")
            
            # [SYSTEM LOG] Start Operation
            self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_STARTED, chip=chip_name, protocol=self.current_protocol, size=size)
            
            if self.hw.open():
                self.apply_current_voltage()
                time.sleep(0.050) # 50ms chip stabilization delay
                self.hw.set_led(True) # Turn ON LED during read
                # HW.open calls init_mpsse (30MHz) automatically for SPI.
                if self.current_protocol == "I2C":
                    self.hw.i2c_init()

                full_data = bytearray()
                chunk_size = 4096 if self.current_protocol == "SPI" else 256
                success = True

                try:
                    for addr in range(0, size, chunk_size):
                        if stop_flag["stop"]: 
                            self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_ABORTED)
                            break
                        
                        length = min(chunk_size, size - addr)
                        if addr % 65536 == 0 or addr + length >= size or self.current_protocol == "I2C":
                            update_cb(addr, f"READING: 0x{addr:06X} / 0x{size:06X}")
                        
                        data = None
                        for attempt in range(3):
                            if self.current_protocol == "SPI":
                                data = self.spi.read_data(addr, length)
                            elif self.current_protocol == "I2C":
                                data = self.i2c.read_data(addr, length, chip_info=self.selected_chip)

                            if data and len(data) == length:
                                break
                            else:
                                if hasattr(self.hw, 'ft') and getattr(self.hw, 'handle', None) and self.hw.handle.value:
                                    try:
                                        self.hw.ft.FT_Purge(self.hw.handle, 3)
                                    except Exception:
                                        pass
                                time.sleep(0.02)
                                data = None

                        if data and len(data) == length:
                            full_data.extend(data)
                        else:
                            self.log_write(f"ERROR: READ FAILED AT ADDRESS 0x{addr:06X}")
                            success = False
                            break
                    
                    update_cb(size, "READ COMPLETE")
                except Exception as e:
                    self.log_write(f"ERROR: READ FAILED ({str(e)})")
                    success = False
                    self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_FAILED, error=str(e))

                # User requested: Wait 1 second after Read finishes before turning voltage low
                time.sleep(1.0)
                self.hw.set_led(False) # Turn OFF LED
                self.hw.close()

                if success and len(full_data) == size:
                    self.buffer_data = full_data
                    self.root.after(0, lambda d=full_data: self.update_hex_view(d))
                    
                    # [SYSTEM LOG] Success
                    self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_SUCCESS, size=size)
                    
                    # Check if chip is empty (all bytes are 0xFF)
                    is_empty = all(b == 0xFF for b in full_data)
                    
                    elapsed_sec = self.get_op_elapsed()
                    size_mb = size / (1024 * 1024)
                    size_str = f"{int(size_mb)}MB" if size_mb.is_integer() else f"{size_mb:.2f}MB"
                    if size < 1024 * 1024:
                        size_str = f"{size // 1024}KB"
                    
                    if is_empty:
                        self.log_write(f"SUCCESS: READ COMPLETE (CHIP IS EMPTY - ALL 0xFF) - {elapsed_sec}s")
                        self.sound_manager.play_event("READ_COMPLETE")
                        self.root.after(100, lambda: self.notify_cyber("NOTICE", "CHIP IS EMPTY (NO DATA FOUND).", "INFO"))
                    else:
                        self.sound_manager.play_event("READ_COMPLETE")
                        self.root.after(100, lambda: self.notify_cyber("READ COMPLETE", f"SUCCESSFULLY READ {size} BYTES."))
                        self.log_write(f"SUCCESS: READ COMPLETE ({size_str}) - {elapsed_sec}s")
                else:
                    if success: # If loop finished but data len mismatch (rare)
                         self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_FAILED, reason="Data length mismatch")
                    self.sound_manager.play_event("ERROR")
                    self.root.after(100, lambda: self.notify_cyber("READ ERROR", "DATA RETRIEVAL INCOMPLETE OR FAILED.", "ERROR"))
            else:
                self.syslog.log_operation(self.syslog.OP_READ, self.syslog.STATUS_FAILED, reason="Hardware not detected")
                self.log_write("ERROR: READ FAILED - DEVICE NOT DETECTED.")
                self.sound_manager.play_event("ERROR")
                self.root.after(0, lambda: self.status_label.config(text="NOT CONNECT", fg=self.clr_neon_red))
                self.root.after(100, lambda: self.notify_cyber("HARDWARE ERROR", "PROGRAMMER NOT DETECTED.", "ERROR"))
            
            self.stop_op_timer()
            self.io_busy = False

        self.show_progress_dialog(f"READING CHIP", size, read_task)

    def auto_check_update_startup(self):
        """Silent background update checker triggered automatically on software launch."""
        def _check_worker():
            try:
                response = requests.get(self.update_url, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    remote_version = data.get("version", "0.0.0")
                    download_url = data.get("url", "")
                    changelog = data.get("changelog", "No details provided.")

                    # Convert GitHub Blob URL to Raw URL if needed
                    if "github.com" in download_url and "/blob/" in download_url:
                        download_url = download_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

                    current_ver_str = self.app_version
                    if is_newer_version(remote_version, current_ver_str):
                        self.root.after(0, lambda: self._prompt_auto_update(remote_version, changelog, download_url))
            except Exception:
                # Completely silent on startup failure/offline - do not interrupt user
                pass

        threading.Thread(target=_check_worker, daemon=True).start()

    def _prompt_auto_update(self, remote_version, changelog, download_url):
        """Displays a cyberpunk update prompt when an update is detected on startup."""
        if getattr(self, "_update_prompt_active", False) or getattr(self, "io_busy", False):
            return
        self._update_prompt_active = True

        win = tk.Toplevel(self.root)
        win.title("R1 AUTO UPDATE")
        win.geometry("480x360")
        win.configure(bg=self.clr_bg, highlightbackground=self.clr_neon_blue, highlightthickness=2)
        win.transient(self.root)
        win.attributes("-topmost", True)
        
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 240
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 180
        win.geometry(f"+{x}+{y}")

        def on_close():
            self._update_prompt_active = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(win, text="⚡ NEW UPDATE AVAILABLE ⚡", bg=self.clr_bg, fg=self.clr_neon_blue,
                 font=("Orbitron", 12, "bold"), pady=15).pack(fill=tk.X)

        ver_card = tk.Frame(win, bg=self.clr_card, highlightbackground=self.clr_border, highlightthickness=1)
        ver_card.pack(fill=tk.X, padx=25, pady=5)

        tk.Label(ver_card, text=f"Current Version:   {self.app_version}", bg=self.clr_card, fg=self.clr_dim,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(8, 2))
        tk.Label(ver_card, text=f"New Version:       v{remote_version}", bg=self.clr_card, fg="#00FFCC",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(0, 8))

        changes_frame = tk.Frame(win, bg=self.clr_bg)
        changes_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=8)

        tk.Label(changes_frame, text="What's New:", bg=self.clr_bg, fg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")

        tk.Label(changes_frame, text=changelog, bg=self.clr_bg, fg=self.clr_dim,
                 font=("Segoe UI", 9), justify=tk.LEFT, wraplength=420).pack(anchor="w", pady=(3, 5))

        btn_frame = tk.Frame(win, bg=self.clr_bg)
        btn_frame.pack(fill=tk.X, padx=25, pady=(10, 20))

        def confirm_update():
            on_close()
            self.action_update_direct(remote_version, download_url)

        btn_update = tk.Button(btn_frame, text="🚀 UPDATE NOW", bg=self.clr_neon_blue, fg="black",
                               activebackground="white", activeforeground="black",
                               font=("Orbitron", 10, "bold"), relief="flat", padx=18, pady=8,
                               cursor="hand2", command=confirm_update)
        btn_update.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_later = tk.Button(btn_frame, text="REMIND LATER", bg=self.clr_card, fg=self.clr_dim,
                              activebackground=self.clr_card, activeforeground="white",
                              font=("Orbitron", 9), relief="flat", padx=12, pady=8,
                              cursor="hand2", command=on_close)
        btn_later.pack(side=tk.RIGHT)

    def action_update_direct(self, remote_version, download_url):
        """Directly launch update downloader and restart with progress UI."""
        win = tk.Toplevel(self.root)
        win.title("R1 UPDATE MANAGER")
        win.geometry("450x300")
        win.configure(bg=self.clr_bg, highlightbackground=self.clr_neon_blue, highlightthickness=1)
        win.transient(self.root)
        win.grab_set()

        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 225
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 150
        win.geometry(f"+{x}+{y}")

        tk.Label(win, text="SYSTEM AUTO UPDATE", bg=self.clr_bg, fg=self.clr_neon_blue, 
                 font=("Orbitron", 12, "bold"), pady=15).pack(fill=tk.X)

        tk.Label(win, text=f"Upgrading to v{remote_version}", bg=self.clr_bg, fg="#00FFCC", 
                 font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))

        self.set_safe_mode(True)
        self.start_update_download(win, download_url, auto_restart=True)

    def action_update(self):
        """Check for updates via GitHub JSON - MANUAL SAFE UPDATE SYSTEM."""
        # Disable Critical Operations
        self.btn_map_enabled = False
        
        win = tk.Toplevel(self.root)
        win.title("R1 UPDATE MANAGER")
        win.geometry("450x350")
        win.configure(bg=self.clr_bg, highlightbackground=self.clr_neon_blue, highlightthickness=1)
        win.transient(self.root)
        win.grab_set()
        
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 225
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 175
        win.geometry(f"+{x}+{y}")
        
        tk.Label(win, text="SYSTEM UPDATE CHECK", bg=self.clr_bg, fg=self.clr_neon_blue, 
                 font=("Orbitron", 12, "bold"), pady=20).pack(fill=tk.X)
        
        status_lbl = tk.Label(win, text="Connecting to GitHub server...", bg=self.clr_bg, fg="white", 
                             font=("Segoe UI", 10))
        status_lbl.pack(pady=10)
        
        prog = ttk.Progressbar(win, mode='indeterminate', length=250)
        prog.pack(pady=10)
        prog.start()
        
        def run_check():
            try:
                # Disable Hardware Interaction buttons for safety
                self.root.after(0, lambda: self.set_safe_mode(True))
                
                response = requests.get(self.update_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    remote_version = data.get("version", "0.0.0")
                    download_url = data.get("url", "")
                    
                    # Convert GitHub Blob URL to Raw URL if needed
                    if "github.com" in download_url and "/blob/" in download_url:
                        download_url = download_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                    
                    changelog = data.get("changelog", "No details provided.")

                    def update_ui():
                        prog.stop()
                        prog.pack_forget()
                        
                        current_ver_str = self.app_version
                        if is_newer_version(remote_version, current_ver_str):
                            status_txt = f"NEW VERSION FOUND: v{remote_version}"
                            status_lbl.config(text=status_txt, fg=self.clr_neon_blue)
                            # Show changelog
                            log_lbl = tk.Label(win, text=f"Changes: {changelog}", bg=self.clr_bg, fg=self.clr_dim, 
                                              font=("Segoe UI", 9), wraplength=400)
                            log_lbl.pack(pady=5)
                            
                            tk.Button(win, text="DOWNLOAD & UPDATE", bg=self.clr_neon_blue, fg="black", 
                                      font=("Orbitron", 10, "bold"), relief="flat", padx=20, pady=10,
                                      command=lambda: self.start_update_download(win, download_url, auto_restart=True)).pack(pady=20)
                        else:
                            status_lbl.config(text=f"YOU ARE ON THE LATEST VERSION (v{self.app_version})")
                            tk.Button(win, text="CLOSE", bg=self.clr_card, fg="white", font=("Orbitron", 9),
                                      command=lambda: [self.set_safe_mode(False), win.destroy()], width=15).pack(pady=20)
                    
                    self.root.after(0, update_ui)
                else:
                    self.root.after(0, lambda: [self.set_safe_mode(False), status_lbl.config(text="SERVER ERROR: VERSION FILE NOT FOUND", fg="red")])
            except Exception as e:
                self.root.after(0, lambda: [self.set_safe_mode(False), status_lbl.config(text=f"CONNECTION FAILED: {str(e)}", fg="red")])
            finally:
                self.root.after(0, prog.stop)

        threading.Thread(target=run_check, daemon=True).start()

    def set_safe_mode(self, enabled):
        """Disable dangerous buttons during update checks."""
        state = tk.DISABLED if enabled else tk.NORMAL
        for widget in self.main_btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                txt = widget.cget('text')
                # Keep READ enabled, disable others
                if txt not in ["READ", "RD", "SM", "IDENTIFY", "OPEN", "SAVE", "WIRING"]:
                     widget.config(state=state)

    def start_update_download(self, window, url, auto_restart=False):
        """Download update.zip, validate manifest, and extract payload."""
        for widget in window.winfo_children():
            if isinstance(widget, tk.Button): widget.config(state=tk.DISABLED)
            
        status_lbl = tk.Label(window, text="Downloading Update Package...", bg=self.clr_bg, fg="white")
        status_lbl.pack(pady=10)
        
        prog = ttk.Progressbar(window, mode='determinate', length=300)
        prog.pack(pady=10)
        
        def download_worker():
            try:
                # Prepare Paths
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                cache_dir = os.path.join(base_dir, "update_cache")
                
                # Safer Clean-up
                if os.path.exists(cache_dir):
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as e:
                        print(f"Update Cache Cleanup Failed: {e}")
                
                os.makedirs(cache_dir, exist_ok=True)
                
                local_zip = os.path.join(cache_dir, "update.zip")
                
                # 1. Download
                try:
                    self.root.after(0, lambda: status_lbl.config(text="Starting Download..."))
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status() # Raise HTTP errors
                    
                    total_size = int(response.headers.get('content-length', 0))
                    
                    downloaded = 0
                    with open(local_zip, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1024*64):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    self.root.after(0, lambda p=percent: [prog.configure(value=p), 
                                                                        status_lbl.config(text=f"Downloading... ({int(p)}%)")])
                except Exception as dl_err:
                     raise RuntimeError(f"Download failed: {dl_err}")

                # 2. Validate ZIP Structure
                self.root.after(0, lambda: status_lbl.config(text="Validating Package..."))
                
                if not zipfile.is_zipfile(local_zip):
                    raise ValueError("Invalid ZIP file format.")
                
                try:
                    with zipfile.ZipFile(local_zip, 'r') as zf:
                        file_list = zf.namelist()
                        
                        if "manifest.json" not in file_list:
                            raise ValueError("Missing manifest.json in update package.")
                        if "version.txt" not in file_list:
                            raise ValueError("Missing version.txt in update package.")
                        
                        # 3. Extract & Validate Manifest
                        zf.extract("manifest.json", cache_dir)
                        zf.extract("version.txt", cache_dir)
                        
                        with open(os.path.join(cache_dir, "manifest.json"), 'r') as mf:
                            manifest = json.load(mf)
                        
                        # Security Check: Forbidden Paths
                        forbidden = ["drivers/", "bios_dumps/", "logs/"]
                        for fpath in manifest.get("files", []):
                             norm_path = fpath.replace("\\", "/")
                             for bad in forbidden:
                                 if bad in norm_path:
                                      if norm_path.startswith("drivers/"): raise ValueError(f"Security Violation: Update attempts to modify driver {fpath}")
                                      if norm_path.startswith("logs/"): raise ValueError(f"Security Violation: Update attempts to modify logs {fpath}")
                                      if ".." in norm_path: raise ValueError("Security Violation: Directory Traversal detected.")

                        # 4. Extract Payload
                        self.root.after(0, lambda: status_lbl.config(text="Extracting Payload..."))
                        payload_dir = os.path.join(cache_dir, "payload")
                        os.makedirs(payload_dir, exist_ok=True)
                        
                        for z_item in file_list:
                            if z_item.startswith("payload/"):
                                 zf.extract(z_item, cache_dir)
                                 
                except zipfile.BadZipFile:
                     raise ValueError("Corrupted Update Package.")
                except Exception as z_err:
                     raise RuntimeError(f"Package validation failed: {z_err}")
                
                # Ready for Updater.exe
                if auto_restart:
                    self.root.after(0, lambda: status_lbl.config(text="Update verified! Restarting application in 1s...", fg="#00FFCC"))
                    self.root.after(1000, lambda: self.launch_updater(base_dir))
                else:
                    self.root.after(0, lambda: self.prompt_restart(base_dir))

            except Exception as e:
                self.root.after(0, lambda: [messagebox.showerror("UPDATE FAILED", f"Error: {str(e)}"), self.set_safe_mode(False), window.destroy()])
        
        threading.Thread(target=download_worker, daemon=True).start()

    def prompt_restart(self, base_dir):
        """Ask user to confirm restart to apply updates."""
        if messagebox.askyesno("RESTART REQUIRED", "Update package verified and ready.\n\nThe application must restart to apply changes.\n\nProceed?"):
            self.launch_updater(base_dir)
        else:
             self.set_safe_mode(False)

    def launch_updater(self, base_dir):
        """Launch updater.exe and exit."""
        updater_exe = os.path.join(base_dir, "updater.exe")
        if not os.path.exists(updater_exe):
            messagebox.showerror("ERROR", f"Updater component missing at:\n{updater_exe}\n\nReinstall application.")
            self.set_safe_mode(False)
            return

        try:
            pid = os.getpid()
            self.log_write(f"SYSTEM: HANDING OVER TO UPDATER (PID: {pid})...")
            
            # Launch updater with PID argument and clean working directory
            clean_env = os.environ.copy()
            clean_env.pop("_R1_HOT_RELOADED", None)
            subprocess.Popen([updater_exe, str(pid)], cwd=base_dir, env=clean_env)
            
            # Exit clean
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("LAUNCH ERROR", f"Failed to launch updater: {e}")
            self.set_safe_mode(False)

    def action_auto(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        if not self.selected_chip:
            self.notify_cyber("NOTICE", "PLEASE SELECT A CHIP FIRST.", "ERROR")
            return
        
        # [Patch] Critical Size Validation before AUTO
        f_size = len(self.buffer_data) if self.buffer_data else 0
        if f_size > 0:
            is_safe, msg = LogicManager.validate_safe_write(self.selected_chip['size'], f_size)
            if not is_safe:
                self.sound_manager.play_event("ERROR")
                self.notify_cyber("SAFETY BLOCK", msg, "ERROR")
                return

        if self.auto_write_var.get() or self.auto_verify_var.get():
            if not self.is_buffer_valid("AUTO SEQUENCE"):
                return

        tasks = []
        if self.auto_erase_var.get(): tasks.append("ERASE")
        if self.auto_write_var.get(): tasks.append("WRITE")
        if self.auto_verify_var.get(): tasks.append("VERIFY")
        
        if not tasks:
            self.notify_cyber("INFO", "NO TASKS SELECTED IN AUTO CONFIG.")
            return

        size = int(self.selected_chip['size'])
        
        def auto_task(update_cb, stop_flag):
            self.in_auto_sequence = True
            self.start_op_timer()
            try:
                self.log_write(f"AUTO: STARTING SEQUENCE ({' -> '.join(tasks)})...")
                
                # ERASE
                if self.auto_erase_var.get():
                    if stop_flag["stop"]: return
                    self.log_write("AUTO: ERASING...")
                    self._do_erase(silent=True, external_dialog=True, update_cb=update_cb)

                # WRITE
                if self.auto_write_var.get():
                    if stop_flag["stop"]: return
                    self.log_write("AUTO: WRITING...")
                    self._do_write(silent=True, external_dialog=True, update_cb=update_cb)

                # VERIFY
                if self.auto_verify_var.get():
                    if stop_flag["stop"]: return
                    self.log_write("AUTO: VERIFYING...")
                    self._do_verify(silent=True, external_dialog=True, update_cb=update_cb)
                
                total_sec = self.get_op_elapsed()
                self.log_write(f"SUCCESS: AUTO SEQUENCE COMPLETE (TOTAL: {total_sec}s)")
                    
                if hasattr(self, 'sound_manager'):
                    self.sound_manager.play_event("AUTO_COMPLETE")
                self.root.after(100, lambda: self.notify_cyber("AUTO DONE", f"ALL OPERATIONS FINISHED IN {total_sec}s."))
            finally:
                self.in_auto_sequence = False
                self.stop_op_timer()

        self.show_progress_dialog("AUTO SEQUENCE", size, auto_task)

    def action_auto_config(self):
        # Create a borderless popup
        win = tk.Toplevel(self.root)
        win.overrideredirect(True) # Remove title bar for 'small page' feel
        win.attributes("-alpha", 0.95) # Slight translucency
        win.configure(bg=self.clr_card, highlightbackground=self.clr_neon_blue, highlightthickness=2)
        
        # Geometry and Relative Positioning (Next to 3-dot button)
        w, h = 280, 240
        # Get absolute coordinates of the button
        btn_x = self.config_btn.winfo_rootx()
        btn_y = self.config_btn.winfo_rooty()
        
        # Position below the button, aligned to the right edge of the window if needed
        x = btn_x - w + self.config_btn.winfo_width()
        if x < 10:
            x = btn_x + 5
        y = btn_y + self.config_btn.winfo_height() + 5
        win.geometry(f"{w}x{h}+{x}+{y}")
        
        tk.Label(win, text="AUTO CONFIGURATION", bg=self.clr_header, fg=self.clr_neon_blue, 
                 font=("Orbitron", 10, "bold"), pady=10).pack(fill=tk.X)
        
        content = tk.Frame(win, bg=self.clr_card)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        def add_check(text, var):
            cb = tk.Checkbutton(content, text=text, variable=var, bg=self.clr_card, fg=self.clr_text, 
                                selectcolor=self.clr_bg, activebackground=self.clr_card, 
                                activeforeground=self.clr_neon_blue, font=("Segoe UI", 10),
                                padx=10, pady=5)
            cb.pack(anchor="w")
            
        add_check("ERASE CHIP", self.auto_erase_var)
        add_check("WRITE BUFFER", self.auto_write_var)
        add_check("VERIFY DATA", self.auto_verify_var)
        
        btn_save = tk.Button(win, text="SAVE SETTINGS", bg=self.clr_neon_blue, fg="black", 
                           font=("Orbitron", 9, "bold"), relief="flat", padx=20, pady=10, 
                           command=win.destroy, cursor="hand2")
        btn_save.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Close on lost focus or clicking outside (optional, but let's keep it simple for now)
        win.bind("<FocusOut>", lambda e: win.destroy())
        win.focus_set()

    def _do_erase(self, silent=False, external_dialog=False, update_cb=None):
        if not self.selected_chip:
            self.sound_manager.play_event("ERROR")
            self.notify_cyber("NOTICE", "PLEASE SELECT A CHIP FIRST.", "ERROR")
            return
            
        if not silent and not self.confirm_cyber("DANGER", f"ARE YOU SURE YOU WANT TO ERASE {self.selected_chip['name']}? ALL DATA WILL BE LOST."):
            return

        size = int(self.selected_chip['size'])
        chip_name = self.selected_chip['name']

        def erase_task(up_cb, stop_flag):
            if not getattr(self, "in_auto_sequence", False):
                self.start_op_timer()
            self.io_busy = True
            if not getattr(self, "in_auto_sequence", False):
                self.log_write(f"ERASE: ERASING {chip_name}...")
            
            # [SYSTEM LOG] Start Operation
            self.syslog.log_operation(self.syslog.OP_ERASE, self.syslog.STATUS_STARTED, chip=chip_name)
            
            if self.hw.open():
                self.apply_current_voltage()
                time.sleep(0.050) # 50ms chip stabilization delay
                self.hw.set_led(True) # Turn ON LED during erase
                # Heuristic: Flash Chip erase typically takes 5-7s per MB depending on chip vendor
                mb_size = size / 1048576.0
                est_duration = max(10.0, 4.0 + (mb_size * 7.0))
                start_time = time.time()
                
                up_cb(0, "SENDING ERASE COMMAND...")
                
                last_update = [0]
                def erase_tick():
                    # Called periodically by wait_busy loop
                    now = time.time()
                    if now - last_update[0] < 0.15: return
                    last_update[0] = now
                    
                    elapsed = now - start_time
                    # Smooth asymptotic progress curve so it never freezes at 99%
                    ratio = elapsed / est_duration
                    if ratio <= 0.85:
                        pct = ratio * 100.0
                    else:
                        extra = elapsed - (0.85 * est_duration)
                        pct = 85.0 + 13.0 * (1.0 - (1.0 / (1.0 + (extra / 15.0))))
                    pct = min(98.0, max(0.0, pct))
                    up_cb(size * (pct / 100.0), f"ERASING... {int(pct)}% ({int(elapsed)}s)")

                try:
                    if self.current_protocol == "SPI":
                        # Auto-unprotect SPI chip if write-protection (BP bits) is active
                        try:
                            sr = self.hw.spi_write_read([0x05], 1)
                            if sr and (sr[0] & 0x7C):
                                self.log_write("NOTICE: DETECTED CHIP WRITE-PROTECTION (BP BITS). AUTO-UNLOCKING...")
                                self.hw.spi_write_read([0x06])
                                self.hw.spi_write_read([0x01, 0x00])
                                time.sleep(0.02)
                        except Exception:
                            pass
                        # Pass tick callback to spi handler
                        self.spi.chip_erase(tick_callback=erase_tick) 
                    elif self.current_protocol == "I2C":
                        self.hw.i2c_init()
                        page_size = int(self.selected_chip.get('page', 16)) if self.selected_chip else 16
                        blank_page = bytearray([0xFF] * page_size)
                        for addr in range(0, size, page_size):
                            if stop_flag["stop"]:
                                break
                            chunk = blank_page[:min(page_size, size - addr)]
                            if not self.i2c.write_page(addr, chunk, chip_info=self.selected_chip):
                                raise Exception(f"I2C write failed at 0x{addr:04X}")
                            erase_tick()
                    
                    # Force 100% on completion
                    up_cb(size, "ERASE COMPLETE")
                    if not getattr(self, "in_auto_sequence", False):
                        elapsed_sec = self.get_op_elapsed()
                        self.log_write(f"SUCCESS: ERASE COMPLETE - {elapsed_sec}s")
                        self.sound_manager.play_event("ERASE_COMPLETE")
                    
                    # [SYSTEM LOG] Success
                    self.syslog.log_operation(self.syslog.OP_ERASE, self.syslog.STATUS_SUCCESS, duration=f"{time.time() - start_time:.1f}s")
                    
                except Exception as e:
                    self.log_write(f"ERROR: ERASE FAILED ({str(e)})")
                    self.sound_manager.play_event("ERROR")
                    self.syslog.log_operation(self.syslog.OP_ERASE, self.syslog.STATUS_FAILED, error=str(e))
                self.hw.set_led(False) # Turn OFF LED
                self.hw.close()
            else:
                self.syslog.log_operation(self.syslog.OP_ERASE, self.syslog.STATUS_FAILED, reason="Hardware not detected")
                self.log_write("ERROR: ERASE FAILED - DEVICE NOT DETECTED.")
                self.sound_manager.play_event("ERROR")
            if not getattr(self, "in_auto_sequence", False):
                self.stop_op_timer()
            self.io_busy = False

        if external_dialog and update_cb:
            erase_task(update_cb, {"stop": False})
        else:
            self.show_progress_dialog(f"ERASING IC", size, erase_task)

    def action_erase(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        if not self.selected_chip: return
        if self.confirm_cyber("CONFIRM ERASE", f"WIPE ALL DATA FROM {self.selected_chip['name']}?"):
            self._do_erase(silent=False)

    def _do_write(self, silent=False, external_dialog=False, update_cb=None):
        if not self.selected_chip:
            self.sound_manager.play_event("ERROR")
            self.root.after(0, lambda: messagebox.showwarning("ID ERROR", "Target chip is not selected. Please select a chip from the database first."))
            return
            
        # STEP 1: Main Thread Validation (Thread-Safe)
        if not self.is_buffer_valid("WRITE OPERATION"):
            self.sound_manager.play_event("ERROR")
            return
            
        if not silent and not self.confirm_cyber("FLASH CONFIRMATION", f"Proceed to write {len(self.buffer_data)} bytes to {self.selected_chip['name']}?"):
            return

        # [Patch] Critical Size Validation before Write
        is_safe, msg = LogicManager.validate_safe_write(self.selected_chip['size'], len(self.buffer_data))
        if not is_safe:
            self.sound_manager.play_event("ERROR")
            self.notify_cyber("SAFETY BLOCK", msg, "ERROR")
            return

        size = len(self.buffer_data)
        chip_name = self.selected_chip['name']

        def write_task(up_cb, stop_flag):
            if not getattr(self, "in_auto_sequence", False):
                self.start_op_timer()
            # STEP 2: Redundant Thread-Level Validation
            if self.buffer_data is None or len(self.buffer_data) == 0:
                self.log_write("IO ERROR: BUFFER LOST DURING THREAD INITIALIZATION.")
                self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_ABORTED, reason="Buffer Lost")
                if not getattr(self, "in_auto_sequence", False):
                    self.stop_op_timer()
                return

            self.io_busy = True
            
            # [SYSTEM LOG] Start Operation
            self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_STARTED, chip=chip_name, size=size)
            
            if self.hw.open():
                self.apply_current_voltage()
                time.sleep(0.050) # 50ms chip stabilization delay
                self.hw.set_led(True) # Turn ON LED during write
                if self.current_protocol == "I2C":
                    self.hw.i2c_init()
                
                page_size = int(self.selected_chip.get('page', 256))
                if self.current_protocol == "I2C":
                    page_size = int(self.selected_chip.get('page', 16))
                elif self.current_protocol == "SPI":
                    # Auto-unprotect SPI chip if write-protection (BP bits) is active
                    try:
                        sr = self.hw.spi_write_read([0x05], 1)
                        if sr and (sr[0] & 0x7C):
                            self.log_write("NOTICE: DETECTED CHIP WRITE-PROTECTION (BP BITS). AUTO-UNLOCKING...")
                            self.hw.spi_write_read([0x06])
                            self.hw.spi_write_read([0x01, 0x00])
                            time.sleep(0.02)
                    except Exception:
                        pass
                
                success = True
                try:
                    for addr in range(0, size, page_size):
                        if stop_flag["stop"]: 
                             self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_ABORTED)
                             break
                        chunk = self.buffer_data[addr : addr + page_size]
                        
                        # Optimization: Update UI only every 4KB or last page to prevent UI lag
                        if addr % 4096 == 0 or addr + page_size >= size or self.current_protocol == "I2C":
                             up_cb(addr, f"WRITING: 0x{addr:06X} / 0x{size:06X}")

                        if self.current_protocol == "SPI":
                            self.spi.page_program(addr, chunk)
                        elif self.current_protocol == "I2C":
                            if not self.i2c.write_page(addr, chunk, chip_info=self.selected_chip):
                                raise Exception(f"I2C write failed at 0x{addr:04X}")
                    up_cb(size, "WRITE COMPLETE")
                except Exception as e:
                    self.log_write(f"ERROR: WRITE FAILED ({str(e)})")
                    success = False
                    self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_FAILED, error=str(e))
                self.hw.set_led(False) # Turn OFF LED
                self.hw.close()
                if success:
                    if not getattr(self, "in_auto_sequence", False):
                        elapsed_sec = self.get_op_elapsed()
                        self.log_write(f"SUCCESS: WRITE COMPLETE - {elapsed_sec}s")
                        self.sound_manager.play_event("WRITE_COMPLETE")
                    self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_SUCCESS)
                else:
                    self.syslog.log_operation(self.syslog.OP_WRITE, self.syslog.STATUS_FAILED, reason="Hardware not detected")
                    self.log_write("ERROR: WRITE FAILED - DEVICE NOT DETECTED.")
                    self.sound_manager.play_event("ERROR")
            if not getattr(self, "in_auto_sequence", False):
                self.stop_op_timer()
            self.io_busy = False

        if external_dialog and update_cb:
            write_task(update_cb, {"stop": False})
        else:
            self.show_progress_dialog(f"WRITING IC", size, write_task)

    def action_write(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        self._do_write(silent=False)

    def _do_verify(self, silent=False, external_dialog=False, update_cb=None):
        if not self.selected_chip:
            self.sound_manager.play_event("ERROR")
            self.notify_cyber("NOTICE", "PLEASE SELECT A CHIP FIRST.", "ERROR")
            return
            
        if not self.is_buffer_valid("VERIFY"):
            self.sound_manager.play_event("ERROR")
            return

        size = len(self.buffer_data)
        chip_name = self.selected_chip['name']

        def verify_task(up_cb, stop_flag):
            if not getattr(self, "in_auto_sequence", False):
                self.start_op_timer()
            self.io_busy = True
            if not getattr(self, "in_auto_sequence", False):
                self.log_write("VERIFY: VERIFYING CHIP DATA...")
            
            # [SYSTEM LOG] Start Operation
            self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_STARTED, chip=chip_name, size=size)
            
            if self.hw.open():
                self.apply_current_voltage()
                time.sleep(0.050) # 50ms chip stabilization delay
                self.hw.set_led(True) # Turn ON LED during verify
                if self.current_protocol == "I2C":
                    self.hw.i2c_init()
                
                chip_data = bytearray()
                chunk_size = 4096 if self.current_protocol == "SPI" else 256
                success = True
                try:
                    for addr in range(0, size, chunk_size):
                        if stop_flag["stop"]: 
                             self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_ABORTED)
                             break
                        length = min(chunk_size, size - addr)
                        if addr % 65536 == 0 or addr + length >= size or self.current_protocol == "I2C":
                            up_cb(addr, f"VERIFYING: 0x{addr:06X} / 0x{size:06X}")
                        
                        data = None
                        for attempt in range(3):
                            if self.current_protocol == "SPI":
                                data = self.spi.read_data(addr, length)
                            elif self.current_protocol == "I2C":
                                data = self.i2c.read_data(addr, length, chip_info=self.selected_chip)

                            if data and len(data) == length:
                                break
                            else:
                                if hasattr(self.hw, 'ft') and getattr(self.hw, 'handle', None) and self.hw.handle.value:
                                    try:
                                        self.hw.ft.FT_Purge(self.hw.handle, 3)
                                    except Exception:
                                        pass
                                time.sleep(0.02)
                                data = None

                        if data and len(data) == length:
                            chip_data.extend(data)
                        else:
                            self.log_write(f"ERROR: VERIFY READ FAILED AT ADDRESS 0x{addr:06X}")
                            success = False
                            break
                except Exception as e:
                    self.log_write(f"ERROR: VERIFY FAILED ({str(e)})")
                    success = False
                    self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_FAILED, error=str(e))

                self.hw.set_led(False) # Turn OFF LED
                self.hw.close()
                if success and list(chip_data) == list(self.buffer_data):
                    if not getattr(self, "in_auto_sequence", False):
                        elapsed_sec = self.get_op_elapsed()
                        self.log_write(f"SUCCESS: VERIFICATION PASSED - {elapsed_sec}s")
                        self.sound_manager.play_event("VERIFY_COMPLETE")
                    self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_SUCCESS)
                    self.root.after(0, lambda: messagebox.showinfo("VERIFY", "Verification successful! Data on chip matches the buffer."))
                else:
                    if success: # If loop finished but data mismatch
                        mismatch_cnt = sum(1 for a, b in zip(chip_data, self.buffer_data) if a != b)
                        first_err = next((idx for idx, (a, b) in enumerate(zip(chip_data, self.buffer_data)) if a != b), None)
                        err_detail = f" ({mismatch_cnt} bytes mismatch, first at 0x{first_err:06X})" if first_err is not None else ""
                        self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_FAILED, reason=f"Data Content Mismatch{err_detail}")
                        self.log_write(f"ERROR: VERIFICATION FAILED{err_detail}.")
                    else:
                        self.log_write("ERROR: VERIFICATION FAILED (READ ERROR).")
                    self.sound_manager.play_event("ERROR")
                    self.root.after(0, lambda: messagebox.showerror("VERIFY ERROR", "Verification FAILED!\n\nData mismatch detected between chip and buffer."))
                    success = False
            else:
                self.syslog.log_operation(self.syslog.OP_VERIFY, self.syslog.STATUS_FAILED, reason="Hardware not detected")
                self.log_write("ERROR: VERIFY FAILED - DEVICE NOT DETECTED.")
                self.sound_manager.play_event("ERROR")
            if not getattr(self, "in_auto_sequence", False):
                self.stop_op_timer()
            self.io_busy = False

        if external_dialog and update_cb:
            verify_task(update_cb, {"stop": False})
        else:
            self.show_progress_dialog(f"VERIFYING IC", size, verify_task)

    def action_verify(self):
        if hasattr(self, 'show_tab'):
            self.show_tab("LOG")
        self._do_verify(silent=False)

    def action_connection(self):
        win = tk.Toplevel(self.root)
        win.title(f"PINOUT: FT232H [{self.current_protocol}]")
        win.geometry("550x450")
        win.configure(bg=self.clr_bg)
        
        tk.Label(win, text=f"FT232H WIRING ({self.current_protocol} MODE)", bg=self.clr_bg, fg=self.clr_accent, font=("Orbitron", 12, "bold")).pack(pady=20)
        
        info = ""
        if self.current_protocol == "I2C":
            info = (
                "FT232H (AD-BUS)    ->    I2C CHIP (24Cxx)\n"
                "----------------------------------------\n"
                "AD0 (SCL)          ->    PIN 6 (SCL)\n"
                "AD1 + AD2 (SDA)    ->    PIN 5 (SDA)\n"
                "* SHORT AD1 & AD2 TOGETHER FOR SDA *\n"
                "----------------------------------------\n"
                "3.3V               ->    PIN 8 (VCC)\n"
                "GND                ->    PIN 4 (GND)\n"
                "GND                ->    PIN 1,2,3,7 (A0-A2, WP)\n"
            )
        else: # Default SPI
            info = (
                "FT232H (AD-BUS)    ->    SPI CHIP (25Qxx)\n"
                "----------------------------------------\n"
                "AD0 (CLK)          ->    PIN 6 (CLK)\n"
                "AD1 (MOSI)         ->    PIN 5 (DI)\n"
                "AD2 (MISO)         ->    PIN 2 (DO)\n"
                "AD3 (CS)           ->    PIN 1 (CS)\n"
                "----------------------------------------\n"
                "3.3V               ->    PIN 8 (VCC)\n"
                "GND                ->    PIN 4 (GND)\n"
            )
        
        tk.Label(win, text=info, bg=self.clr_card, fg=self.clr_text, font=("Consolas", 11), 
                 justify=tk.LEFT, highlightthickness=1, highlightbackground=self.clr_border, padx=20, pady=20).pack()
        
        tk.Button(win, text="CLOSE", command=win.destroy, bg=self.clr_neon_blue, fg="black", 
                  font=("Orbitron", 8, "bold"), relief="flat", padx=25, pady=8).pack(pady=20)

    def _get_cp1252_char(self, b):
        if b < 32 or b == 127: return "."
        try:
            c = bytes([b]).decode('cp1252')
            if c.isprintable(): return c
            return "."
        except:
            return "."

    def update_hex_view(self, data):
        self.hex_text.delete(1.0, tk.END)
        if not data: 
            self.buffer_info_label.config(text="BUFFER: EMPTY", fg=self.clr_dim)
            self.fill_dummy_hex()
            return
        
        if hasattr(self.hex_text, 'vbar'):
            self.hex_text.vbar.pack(side=tk.RIGHT, fill=tk.Y)
            
        # Update Buffer Status Indicator
        size_kb = len(data) / 1024
        self.buffer_info_label.config(text=f"BUFFER: {size_kb:,.1f} KB IS READY", fg=self.clr_neon_blue)
        
        # Performance optimization: Limit preview to first 64KB for large BIOS files
        limit = min(len(data), 65536)
        
        header = "Offset (h) 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F Decoded text\n"
        result = [header]
        
        for i in range(0, limit, 16):
            chunk = data[i:i+16]
            addr = format(i, '08X')
            bytes_str = " ".join([format(b, '02X') for b in chunk])
            ascii_str = "".join([self._get_cp1252_char(b) for b in chunk])
            result.append(f"{addr}   {bytes_str:<47} {ascii_str}")
        
        self.hex_text.insert(tk.END, "\n".join(result))
        if len(data) > limit:
            self.hex_text.insert(tk.END, f"\n\n--- PREVIEW LIMITED TO FIRST 64KB (TOTAL SIZE: {len(data)} BYTES) ---")
        self.hex_text.yview_moveto(0.0)

    def fill_dummy_hex(self):
        if hasattr(self.hex_text, 'vbar'):
            self.hex_text.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hex_text.delete(1.0, tk.END)
        header = "Offset (h) 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F Decoded text\n"
        dummy = header
        for i in range(20):
            addr = format(i * 16, '08X')
            bytes_str = " ".join(["FF"] * 16)
            dummy += f"{addr}   {bytes_str} ................\n"
        self.hex_text.insert(tk.END, dummy.rstrip("\n"))
        self.hex_text.yview_moveto(0.0)




    def show_config_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=self.clr_header, fg="white", 
                       activebackground=self.clr_neon_blue, activeforeground="black")
        menu.add_command(label="Auto Sequence Config", command=self.action_auto_config)
        menu.add_command(label="Clear / Reset Workspace", command=self.reset_workspace)
        menu.add_separator()
        menu.add_command(label="About", command=self.action_about)
        menu.add_command(label="Reset Layout to Default", command=self.reset_layout_action)
        
        try:
            x = self.config_btn.winfo_rootx()
            y = self.config_btn.winfo_rooty() + self.config_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def show_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("SYSTEM SETTINGS")
        dialog.geometry("380x520")
        dialog.configure(bg=self.clr_bg)
        dialog.transient(self.root)
        dialog.grab_set()
        
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 190
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 260
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="SYSTEM PREFERENCES", bg=self.clr_bg, fg=self.clr_neon_blue, 
                 font=("Orbitron", 14, "bold")).pack(pady=(15, 15))

        def on_hex_toggle():
            if self.config_hex_viewer.get():
                if hasattr(self, 'btn_tab_hex'):
                    self.btn_tab_hex.pack(side=tk.LEFT, padx=(0, 5))
            else:
                if hasattr(self, 'btn_tab_hex'):
                    self.btn_tab_hex.pack_forget()
                if hasattr(self, 'show_tab'):
                    self.show_tab("LOG")

        def on_sound_toggle():
            if hasattr(self, 'sound_manager'):
                self.sound_manager.enabled = self.config_pc_sound.get()
                self.sound_manager.hw_buzzer_enabled = self.config_hw_buzzer.get()

        chk_hex = tk.Checkbutton(dialog, text="Enable Memory Hex Viewer", variable=self.config_hex_viewer,
                                 bg=self.clr_bg, fg="white", selectcolor=self.clr_card,
                                 activebackground=self.clr_bg, activeforeground=self.clr_neon_blue,
                                 font=("Segoe UI", 10), command=on_hex_toggle)
        chk_hex.pack(anchor="w", padx=30, pady=5)

        chk_sound = tk.Checkbutton(dialog, text="Enable PC Speaker Sounds (TTS)", variable=self.config_pc_sound,
                                 bg=self.clr_bg, fg="white", selectcolor=self.clr_card,
                                 activebackground=self.clr_bg, activeforeground=self.clr_neon_blue,
                                 font=("Segoe UI", 10), command=on_sound_toggle)
        chk_sound.pack(anchor="w", padx=30, pady=5)

        chk_buzzer = tk.Checkbutton(dialog, text="Enable Hardware Buzzer (AD7 / GPIOL3)", variable=self.config_hw_buzzer,
                                 bg=self.clr_bg, fg="white", selectcolor=self.clr_card,
                                 activebackground=self.clr_bg, activeforeground=self.clr_neon_blue,
                                 font=("Segoe UI", 10), command=on_sound_toggle)
        # chk_buzzer.pack(anchor="w", padx=30, pady=5) # Temporarily disabled for this update

        # =========================================================
        # --- ADVANCED TOOLS (MOVED FROM NAVBAR) ---
        tools_frame = tk.LabelFrame(dialog, text="Advanced Tools & Plugins", bg=self.clr_bg, fg=self.clr_neon_blue, font=("Orbitron", 10))
        tools_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # New IC
        tk.Button(tools_frame, text="+ NEW IC", bg=self.clr_card, fg="#00ff00",
                  relief="flat", font=("Orbitron", 9, "bold"), cursor="hand2",
                  command=self.show_add_ic_dialog).pack(fill=tk.X, padx=15, pady=8)
        btn_frame = tk.Frame(dialog, bg=self.clr_bg)
        btn_frame.pack(pady=(15, 10))

        tk.Button(btn_frame, text="OK", bg=self.clr_card, fg=self.clr_neon_blue,
                  font=("Orbitron", 10, "bold"), relief="flat", padx=25, pady=5,
                  command=dialog.destroy).pack()

    def show_add_ic_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("ADD NEW IC")
        dialog.geometry("600x480")
        dialog.configure(bg=self.clr_bg)
        dialog.transient(self.root)
        dialog.grab_set()
        
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 300
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 240
        dialog.geometry(f"+{x}+{y}")
        
        frame_ai = tk.LabelFrame(dialog, text="1. AI Prompt Generator", bg=self.clr_bg, fg=self.clr_neon_blue, font=("Segoe UI", 10, "bold"))
        frame_ai.pack(fill=tk.X, padx=15, pady=10)
        
        lbl_ai = tk.Label(frame_ai, text="Click below to generate a prompt. Copy and paste it to ChatGPT/Gemini.", bg=self.clr_bg, fg="white", font=("Segoe UI", 9))
        lbl_ai.pack(anchor="w", padx=10, pady=5)
        
        txt_prompt = tk.Text(frame_ai, height=6, bg=self.clr_card, fg="#00ff00", font=("Consolas", 9), relief="flat")
        txt_prompt.pack(fill=tk.X, padx=10, pady=5)
        
        def generate_prompt():
            current_id = self.ic_address_var.get().replace("0x", "").upper()
            if not current_id or current_id in ["000000", "FFFFFF", "UNKNOWN_ID"]:
                current_id = "UNKNOWN_ID"
            
            prompt = (
                f"Hi! I need your help with identifying a flash memory IC chip.\n\n"
                f"I am using a BIOS programmer tool and I read the JEDEC ID from the chip socket. "
                f"The 3-byte JEDEC ID I got is: 0x{current_id}\n\n"
                f"Could you please look up this chip and find the following information for me?\n"
                f"  1. Manufacturer name\n"
                f"  2. Part / Model name (e.g. W25Q128JV, MX25L6406E, EN25Q64)\n"
                f"  3. Total flash size in BYTES (not KB or MB — the raw byte count, e.g. 8388608 for 8MB)\n"
                f"  4. Page size in bytes (usually 256)\n"
                f"  5. Operating voltage (e.g. 3.3V or 1.8V)\n\n"
                f"Once you have the data, please reply with ONLY a single XML line in EXACTLY this format "
                f"(no extra text, no markdown, no explanation — just the XML line):\n\n"
                f'<PART_NAME id="{current_id}" page="PAGE_SIZE" size="SIZE_IN_BYTES" manufacturer="MANUFACTURER"/>\n\n'
                f"For example, if the chip were a Winbond W25Q128JV (16MB, 3.3V), the correct output would be:\n"
                f'<W25Q128JV_3.3V id="EF4018" page="256" size="16777216" manufacturer="WINBOND"/>\n\n'
                f"Please include the voltage (3.3V or 1.8V) at the end of the part name with an underscore, like shown above.\n"
                f"Thank you!"
            )
            txt_prompt.delete(1.0, tk.END)
            txt_prompt.insert(tk.END, prompt)

            
        btn_frame_ai = tk.Frame(frame_ai, bg=self.clr_bg)
        btn_frame_ai.pack(pady=5)
        
        btn_gen = tk.Button(btn_frame_ai, text="GENERATE PROMPT", bg=self.clr_card, fg="#00ffff", font=("Orbitron", 9, "bold"), relief="flat", command=generate_prompt)
        btn_gen.pack(side=tk.LEFT, padx=5)
        
        def copy_prompt():
            self.root.clipboard_clear()
            self.root.clipboard_append(txt_prompt.get(1.0, tk.END).strip())
            self.root.update()
            self.notify_cyber("COPIED", "Prompt copied to clipboard!", "INFO")
            
        btn_copy = tk.Button(btn_frame_ai, text="COPY PROMPT", bg=self.clr_card, fg="#ffcc00", font=("Orbitron", 9, "bold"), relief="flat", command=copy_prompt)
        btn_copy.pack(side=tk.LEFT, padx=5)
        
        frame_xml = tk.LabelFrame(dialog, text="2. Paste AI Output (XML)", bg=self.clr_bg, fg=self.clr_neon_blue, font=("Segoe UI", 10, "bold"))
        frame_xml.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        txt_xml = tk.Text(frame_xml, height=6, bg=self.clr_card, fg="white", font=("Consolas", 10), relief="flat")
        txt_xml.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def add_ic_to_db():
            xml_data = txt_xml.get(1.0, tk.END).strip()
            if not xml_data:
                messagebox.showwarning("WARNING", "Please paste the XML data first.", parent=dialog)
                return
            
            # Smart Filter: Extract only the XML part (from first '<' to last '>')
            # This ignores AI chat text like "Here is your code: ```xml ... ```"
            start_idx = xml_data.find('<')
            end_idx = xml_data.rfind('>')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                xml_data = xml_data[start_idx:end_idx+1]
            else:
                messagebox.showerror("ERROR", "No valid XML tags found in the pasted text.", parent=dialog)
                return
            
            success, msg = self.db.add_chip_from_xml(xml_data)
            if success:
                self.log_write(f"DATABASE: {msg}")
                self.refresh_chip_list()
                dialog.destroy()
                self.notify_cyber("DATABASE SUCCESS", f"IC DATA ADDED TO DATABASE SUCCESSFULLY!\n\n{msg}", "INFO", duration=1000)
            else:
                messagebox.showerror("DATABASE ERROR", msg, parent=dialog)
                
        btn_frame_xml = tk.Frame(frame_xml, bg=self.clr_bg)
        btn_frame_xml.pack(pady=10)
        
        def paste_xml():
            try:
                clipboard_text = self.root.clipboard_get()
                txt_xml.delete(1.0, tk.END)
                txt_xml.insert(tk.END, clipboard_text)
            except tk.TclError:
                messagebox.showwarning("CLIPBOARD", "Clipboard is empty!", parent=dialog)
                
        btn_paste = tk.Button(btn_frame_xml, text="PASTE XML", bg=self.clr_card, fg="#ffcc00", font=("Orbitron", 10, "bold"), relief="flat", command=paste_xml)
        btn_paste.pack(side=tk.LEFT, padx=10)
        
        btn_add = tk.Button(btn_frame_xml, text="ADD TO DATABASE", bg=self.clr_neon_blue, fg="black", font=("Orbitron", 10, "bold"), relief="flat", command=add_ic_to_db)
        btn_add.pack(side=tk.LEFT, padx=10)

    # =========================================================================
    #  BIOS EDITOR LAUNCHER (LINKED TO R1 BIOS EDITOR)
    # =========================================================================
    def _find_bios_editor_exe(self):
        """
        Comprehensive search for installed R1 BIOS Editor executable on this system.
        Checks:
        1. System PATH
        2. Registry App Paths
        3. Registry Uninstall database (all subkeys in HKCU, HKLM, WOW6432Node)
        4. Standard and custom Program Files / Programs directories across all drives (C:, D:, E:, etc.)
        5. Windows Start Menu and Desktop shortcuts (.lnk targets)
        """
        import winreg
        import shutil

        target_exes = [
            "R1_BIOS_TOOL.exe", 
            "R1_BIOS_Editor.exe", 
            "R1_Editor.exe", 
            "R1_BIOS_Tool.exe"
        ]

        # 1. Check System PATH
        for exe_name in target_exes:
            found = shutil.which(exe_name)
            if found and os.path.exists(found):
                return found

        # 2. Check Windows Registry "App Paths"
        app_path_keys = [
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\R1_BIOS_TOOL.exe",
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\R1_BIOS_Editor.exe",
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\R1_Editor.exe",
        ]
        for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for sub in app_path_keys:
                try:
                    with winreg.OpenKey(hkey, sub) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val:
                            val = val.strip('"\',')
                            if os.path.exists(val):
                                return val
                except Exception:
                    pass

        # 3. Check Windows Registry Uninstall Database (Deep Scan)
        uninstall_roots = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root, path in uninstall_roots:
            try:
                with winreg.OpenKey(root, path) as k:
                    num_subkeys = winreg.QueryInfoKey(k)[0]
                    for i in range(num_subkeys):
                        sub = winreg.EnumKey(k, i)
                        try:
                            with winreg.OpenKey(k, sub) as sk:
                                display_name = ""
                                try:
                                    display_name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                except Exception:
                                    pass

                                sub_lower = sub.lower()
                                name_lower = display_name.lower()

                                # Match R1 Editor / R1 BIOS Tool / Inno GUID
                                is_target = False
                                if "65fd6276" in sub_lower:
                                    is_target = True
                                elif ("r1" in name_lower or "r1" in sub_lower) and ("editor" in name_lower or "edtor" in name_lower or "tool" in name_lower):
                                    if "programmer" not in name_lower: # avoid matching programmer itself
                                        is_target = True

                                if is_target:
                                    for val_name in ["DisplayIcon", "InstallLocation", "Inno Setup: App Path", "UninstallString"]:
                                        try:
                                            val, _ = winreg.QueryValueEx(sk, val_name)
                                            if val:
                                                clean_val = val.strip('"\',')
                                                # If it points directly to an exe
                                                if clean_val.lower().endswith(".exe") and os.path.exists(clean_val):
                                                    return clean_val
                                                # If it's a directory, check for executable inside
                                                if os.path.isdir(clean_val):
                                                    for cand in target_exes:
                                                        full = os.path.join(clean_val, cand)
                                                        if os.path.exists(full):
                                                            return full
                                        except Exception:
                                            pass
                        except Exception:
                            pass
            except Exception:
                pass

        # 4. Search across all system & drive directories (C:, D:, E:, etc.)
        base_folders = []
        for env_var in ["LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "APPDATA", "ProgramData"]:
            v = os.environ.get(env_var)
            if v and os.path.exists(v):
                base_folders.append(v)
                if env_var == "LOCALAPPDATA":
                    base_folders.append(os.path.join(v, "Programs"))

        # Check all available drives for Program Files & Programs
        drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        for d in drives:
            for p in ["Program Files", "Program Files (x86)", "Programs"]:
                full_p = os.path.join(d, p)
                if os.path.exists(full_p):
                    base_folders.append(full_p)

        sub_dirs = [
            "R1 BIOS Edtor", "R1 BIOS Editor", "R1_BIOS_TOOL", 
            "R1_BIOS_Editor", "R1 BIOS Tool", "R1 Editor", "R1_Editor", "R1Tool"
        ]

        for base in set(base_folders):
            for sub in sub_dirs:
                folder = os.path.join(base, sub)
                if os.path.isdir(folder):
                    for exe in target_exes:
                        candidate = os.path.join(folder, exe)
                        if os.path.exists(candidate):
                            return candidate

        # 5. Check Windows Start Menu and Desktop Shortcuts (.lnk)
        start_menu_dirs = [
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            r"C:\Users\Public\Desktop"
        ]
        for sm_dir in start_menu_dirs:
            if os.path.exists(sm_dir):
                for root, _, files in os.walk(sm_dir):
                    for f in files:
                        f_lower = f.lower()
                        if f_lower.endswith(".lnk") and "r1" in f_lower and ("editor" in f_lower or "edtor" in f_lower or "tool" in f_lower):
                            if "programmer" in f_lower:
                                continue
                            lnk_path = os.path.join(root, f)
                            try:
                                cmd = f'(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk_path}").TargetPath'
                                res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=2)
                                target = res.stdout.strip()
                                if target and os.path.exists(target) and target.lower().endswith(".exe"):
                                    return target
                            except Exception:
                                pass

        return None

    def launch_bios_editor(self):
        """
        Launches the external R1 BIOS Editor software ONLY if installed on this computer.
        If not installed, displays a popup notifying the user with a DOWNLOAD NOW button.
        """
        self.log_write("SYSTEM: CHECKING R1 BIOS EDITOR INSTALLATION...")
        exe_path = self._find_bios_editor_exe()

        if exe_path:
            self.log_write(f"SYSTEM: BIOS EDITOR FOUND AT '{exe_path}'. LAUNCHING...")
            try:
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                self.log_write("SYSTEM: BIOS EDITOR LAUNCHED SUCCESSFULLY.")
                self.notify_cyber("BIOS EDITOR", "R1 BIOS Editor launched successfully.", "INFO", duration=1500)
            except Exception as e:
                self.log_write(f"ERROR: COULD NOT LAUNCH BIOS EDITOR - {e}")
                self.notify_cyber("LAUNCH ERROR", str(e), "ERROR")
        else:
            self.log_write("SYSTEM: R1 BIOS EDITOR IS NOT INSTALLED ON THIS PC.")
            self._show_bios_editor_not_found_popup()

    def _show_bios_editor_not_found_popup(self):
        """
        Displays a styled popup when R1 BIOS Editor is not installed.
        Provides a 'DOWNLOAD NOW' button that opens the server link in the web browser.
        """
        import webbrowser

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-alpha", 0.97)
        popup.configure(bg=self.clr_card, highlightbackground="#ffcc00", highlightthickness=2)

        w, h = 480, 220
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.lift()
        popup.transient(self.root)

        # Header
        tk.Label(popup, text="  ⚠  BIOS EDITOR NOT INSTALLED", bg=self.clr_header, fg="#ffcc00",
                 font=("Orbitron", 10, "bold"), pady=10, anchor="w").pack(fill=tk.X)

        # Message
        msg_frame = tk.Frame(popup, bg=self.clr_card)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        msg_text = (
            "R1 BIOS Editor is not installed on this computer.\n\n"
            "This software is required to edit BIOS firmware files directly.\n"
            "Click 'DOWNLOAD NOW' to download the software from the server."
        )

        tk.Label(msg_frame, text=msg_text, bg=self.clr_card, fg=self.clr_text,
                 font=("Segoe UI", 9), wraplength=440, justify="left").pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(popup, bg=self.clr_card)
        btn_frame.pack(pady=(0, 15))

        # Server download link
        download_url = getattr(self, "bios_editor_download_url", "https://r1ailab.com/downloads/R1_BIOS_Editor_Setup.exe")

        def open_download_link():
            popup.destroy()
            self.log_write(f"SYSTEM: OPENING DOWNLOAD LINK: {download_url}")
            try:
                webbrowser.open(download_url)
                self.notify_cyber("DOWNLOAD", "Opening download link in your browser...", "INFO", duration=2500)
            except Exception as e:
                self.notify_cyber("ERROR", f"Could not open download link: {e}", "ERROR")

        tk.Button(btn_frame, text="DOWNLOAD NOW", bg=self.clr_neon_blue, fg="black",
                  font=("Orbitron", 8, "bold"), relief="flat", padx=16, pady=6,
                  command=open_download_link, cursor="hand2").pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="CLOSE", bg=self.clr_header, fg="white",
                  font=("Orbitron", 8, "bold"), relief="flat", padx=16, pady=6,
                  command=popup.destroy, cursor="hand2").pack(side=tk.LEFT, padx=10)

        popup.grab_set()

    def _get_tools_dir(self):
        """Returns the tools directory path relative to the app root."""
        if getattr(sys, 'frozen', False):
            root_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(base_dir)
        return os.path.join(root_dir, "tools")

    def _show_download_popup(self, app_name, app_not_found_msg, download_url, save_path, on_success=None):
        """
        Generic download popup dialog.
        Shows a small styled window with a message and DOWNLOAD button.
        After download completes, runs the downloaded .exe automatically.
        """
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-alpha", 0.97)
        popup.configure(bg=self.clr_card, highlightbackground="#ffcc00", highlightthickness=2)

        w, h = 420, 210
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.lift()
        popup.transient(self.root)

        # Header
        tk.Label(popup, text=f"  ⚠  {app_name} NOT FOUND", bg=self.clr_header, fg="#ffcc00",
                 font=("Orbitron", 10, "bold"), pady=10, anchor="w").pack(fill=tk.X)

        # Message
        msg_frame = tk.Frame(popup, bg=self.clr_card)
        msg_frame.pack(fill=tk.X, padx=20, pady=(12, 5))
        tk.Label(msg_frame, text=app_not_found_msg, bg=self.clr_card, fg=self.clr_text,
                 font=("Segoe UI", 9), wraplength=380, justify="left").pack(anchor="w")

        # Progress area (hidden initially)
        prog_frame = tk.Frame(popup, bg=self.clr_card)
        prog_frame.pack(fill=tk.X, padx=20)

        p_var = tk.DoubleVar()
        p_bar = ttk.Progressbar(prog_frame, variable=p_var, maximum=100, style="Cyber.Horizontal.TProgressbar")

        p_label = tk.Label(prog_frame, text="", bg=self.clr_card, fg=self.clr_neon_blue,
                           font=("Consolas", 8))

        # Buttons Row
        btn_row = tk.Frame(popup, bg=self.clr_card)
        btn_row.pack(pady=12)

        def start_download():
            btn_download.config(state="disabled", text="DOWNLOADING...")
            p_bar.pack(fill=tk.X, pady=(5, 2))
            p_label.pack(anchor="w")

            def worker():
                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    
                    urls = download_url if isinstance(download_url, list) else [download_url]
                    success = False
                    last_err = None
                    headers = {"User-Agent": "Mozilla/5.0"}
                    
                    for url in urls:
                        try:
                            self.log_write(f"DOWNLOAD: Fetching {app_name} from {url}")
                            self.root.after(0, lambda u=url: p_label.config(text=f"Connecting to mirror..."))
                            
                            response = requests.get(url, stream=True, timeout=30, headers=headers)
                            response.raise_for_status()

                            total = int(response.headers.get('content-length', 0))
                            downloaded = 0

                            with open(save_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=16384):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if total > 0:
                                            pct = (downloaded / total) * 100
                                            self.root.after(0, lambda p=pct: p_var.set(p))
                                            self.root.after(0, lambda p=pct, d=downloaded, t=total:
                                                p_label.config(text=f"Downloading... {int(p)}%  ({d//1024} KB / {t//1024} KB)"))
                            
                            success = True
                            break # Successful download, exit mirror loop
                            
                        except Exception as e:
                            last_err = str(e)
                            self.log_write(f"WARNING: Download mirror failed ({url}): {e}")
                            if os.path.exists(save_path):
                                try: os.remove(save_path)
                                except: pass

                    if not success:
                        raise Exception(f"All download mirrors failed. ({last_err})")

                    self.root.after(0, lambda: p_var.set(100))
                    self.root.after(0, lambda: p_label.config(text="✔ Download complete! Launching as Admin..."))
                    self.log_write(f"DOWNLOAD: {app_name} COMPLETE. RUNNING AS ADMINISTRATOR...")

                    # Close popup and run as Administrator using ShellExecuteW
                    def run_as_admin(path):
                        try:
                            import ctypes
                            ctypes.windll.shell32.ShellExecuteW(
                                None,       # hwnd
                                "runas",    # verb = run as administrator
                                path,       # file
                                None,       # parameters
                                None,       # directory
                                1           # SW_SHOWNORMAL
                            )
                            self.log_write(f"SYSTEM: {app_name} LAUNCHED AS ADMINISTRATOR.")
                        except Exception as ex:
                            self.log_write(f"ERROR: ADMIN LAUNCH FAILED - {ex}")
                            # Fallback: try normal launch
                            try:
                                subprocess.Popen([path])
                            except Exception as ex2:
                                self.log_write(f"ERROR: FALLBACK LAUNCH ALSO FAILED - {ex2}")

                    self.root.after(800, popup.destroy)
                    self.root.after(1000, lambda p=save_path: run_as_admin(p))
                    if on_success:
                        self.root.after(900, on_success)


                except Exception as e:
                    self.log_write(f"ERROR: {app_name} DOWNLOAD FAILED - {e}")
                    self.root.after(0, lambda: p_label.config(text=f"✘ Failed: {e}", fg=self.clr_neon_red))
                    self.root.after(0, lambda: btn_download.config(state="normal", text="RETRY"))
                    if os.path.exists(save_path):
                        try: os.remove(save_path)
                        except: pass

            threading.Thread(target=worker, daemon=True).start()

        btn_download = tk.Button(btn_row, text="⬇  DOWNLOAD", bg="#ffcc00", fg="black",
                                 font=("Orbitron", 9, "bold"), relief="flat", padx=20, pady=6,
                                 cursor="hand2", command=start_download)
        btn_download.pack(side=tk.LEFT, padx=10)

        tk.Button(btn_row, text="CANCEL", bg=self.clr_header, fg=self.clr_text,
                  font=("Orbitron", 8, "bold"), relief="flat", padx=15, pady=6,
                  cursor="hand2", command=popup.destroy).pack(side=tk.LEFT, padx=5)

    # =========================================================================
    #  LAYOUT MANAGER & INITIALIZATION ENGINE
    # ======================================================================================================================================

    def initialize_layout_manager(self):
        """
        Smart Layout Initialization:
        Waits for the window to be properly mapped and sized before applying 
        split ratios. Ensures sidebar width is reliably set to default (340px)
        and prevents any collapse bug.
        """
        self.root.bind("<Configure>", self.on_root_configure)
        self.root.after(200, lambda: self.apply_initial_layout())
        self.root.after(700, lambda: self.apply_initial_layout())

    def on_root_configure(self, event):
        """Detect when window is actually visible and sized."""
        if self.layout_initialized:
            return

        # Only initialize if we have a valid real window size
        if event.widget == self.root and event.width >= 800 and event.height >= 400:
            self.root.unbind("<Configure>")
            self.apply_initial_layout()

    def apply_initial_layout(self, force_default=False):
        """Applies layout with validation and prevents sidebar collapse."""
        self.root.update_idletasks()
        
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w < 600: w = 1200
        
        default_h_sash = 340
        t_sash_h = default_h_sash
        
        if not force_default and os.path.exists("layout.json"):
            try:
                with open("layout.json", "r") as f:
                    data = json.load(f)
                    
                saved_h = data.get("h_sash", -1)
                # Validation: sidebar must be between 280px and 500px
                max_allowed = max(340, int(w * 0.45))
                if 280 <= saved_h <= max_allowed:
                    t_sash_h = saved_h
            except Exception as e:
                print(f"[LAYOUT] Error reading layout config: {e}")

        # Always enforce a minimum sidebar width of 280px
        t_sash_h = max(280, t_sash_h)

        try:
            self.h_pane.sashpos(0, t_sash_h)
            self.layout_initialized = True
            self.panel_refresh()
        except Exception:
            pass

    def panel_refresh(self):
        """Force a refresh of internal panel geometry."""
        self.root.update_idletasks()

    def reset_layout_action(self):
        """Reset layout to factory defaults."""
        self.log_write("SYSTEM: RESETTING LAYOUT TO DEFAULTS...")
        if os.path.exists("layout.json"):
            try:
                os.remove("layout.json")
            except:
                pass
        
        self.layout_initialized = False
        self.apply_initial_layout(force_default=True)
        self.save_layout_config()
        self.notify_cyber("LAYOUT RESET", "UI Layout restored to factory default.")

    def save_layout_config(self):
        if not self.layout_initialized: return
        try:
            try:
                h_pos = self.h_pane.sashpos(0)
            except:
                return

            # Never save a collapsed or broken sash position
            if h_pos < 260:
                h_pos = 340

            data = {
                "h_sash": h_pos
            }
            with open("layout.json", "w") as f:
                json.dump(data, f)
            print(f"[LAYOUT] Saved: {data}")
        except Exception:
            pass

    def on_close(self):
        self.save_layout_config()
        self.root.destroy()


    # =========================================================================
    #  SOUND ENGINE HOOKS (NON-DESTRUCTIVE)
    # =========================================================================
    def initialize_sound_system(self):
        """
        Injects sound feedback without modifying code logic.
        Uses runtime hooks and event binding.
        """
        try:
            from sound_engine.sound_manager import SoundManager
            self.sound_manager = SoundManager()
            
            # Inject Hardware and Configs
            self.sound_manager.inject_hardware(self.hw)
            self.sound_manager.hw_buzzer_enabled = self.config_hw_buzzer.get()
            self.sound_manager.enabled = self.config_pc_sound.get()
            
            # Hook 1: Global Button Click
            # (REMOVED: User requested no click sound)
            # self.root.bind_class("Button", "<Button-1>", self.sound_manager.play_click, add="+")
            
            # Hook 2: Status Log Interception
            # We wrap the existing log_write method to listen for keywords
            self._original_log_write = self.log_write
            self.log_write = self._hooked_log_write
            
            print("SYSTEM: SOUND ENGINE ONLINE.")
        except Exception as e:
            print(f"Sound Init Failed: {e}")
            # If fail, we simply don't have sounds. No crash.

    def _hooked_log_write(self, msg):
        # 1. Execute original logic (Critical safety)
        self._original_log_write(msg)
        
        # 2. Additive Sound Logic
        try:
            if "ERROR" in msg or "FAILED" in msg:
                self.sound_manager.play_error()
        except:
            pass # Never let sound kill the app

    def action_about(self):
        self.notify_cyber(f"ABOUT R1 FLASH", f"Version: {self.app_version}\n\nHigh-Performance BIOS Programmer\nDeveloped by R1 Team", "INFO")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = CyberFlashUltra(root)
        root.mainloop()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        try:
            with open("crash_log.txt", "w") as f:
                f.write(err)
            messagebox.showerror("CRITICAL ERROR", f"Application Crashed:\n\n{e}\n\nLog saved to crash_log.txt")
        except:
             # Fallback if tk is dead or io fails
             print("CRITICAL CRASH:")
             print(err)
