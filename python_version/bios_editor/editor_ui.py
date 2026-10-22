import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import dialog_fixer

class BIOSEditorWindow:
    def __init__(self, parent_root):
        self.root = tk.Toplevel(parent_root)
        self.root.title("R1 BIOS EDITOR [BETA]")
        self.root.geometry("1000x700")
        self.root.configure(bg="#0d1117")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Internal Data Buffer (Separate from Main App)
        self.buffer = None
        self.current_file = None
        
        # Colors
        self.clr_bg = "#0d1117"
        self.clr_card = "#161b22"
        self.clr_accent = "#d2a8ff" # Purple for Editor (Distinct from Blue)
        self.clr_text = "#c9d1d9"
        
        self.setup_ui()
        self.apply_modal_behavior(parent_root)
        
    def apply_modal_behavior(self, parent_root):
        """Enforces professional modal behavior."""
        # 1. Transient: Tells OS this window belongs to parent
        self.root.transient(parent_root)
        
        # 2. Focus & Grab: Prevents interaction with main app
        self.root.grab_set()
        self.root.focus_set()
        
        # 3. Center Window relative to parent
        self.center_window(parent_root)

    def center_window(self, parent):
        self.root.update_idletasks()
        
        # Get parent geometry
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        
        # Get self geometry
        w = 1000
        h = 700
        
        # Calculate Center
        x = px + (pw // 2) - (w // 2)
        y = py + (ph // 2) - (h // 2)
        
        # Safety Check (Prevent off-screen)
        if x < 0: x = 0
        if y < 0: y = 0
        
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=self.clr_card, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="BIOS EDITOR", bg=self.clr_card, fg=self.clr_accent, 
                 font=("Orbitron", 16, "bold")).pack(side=tk.LEFT, padx=20)
        
        # Toolbar
        toolbar = tk.Frame(header, bg=self.clr_card)
        toolbar.pack(side=tk.RIGHT, padx=20)
        
        self.btn_load = self.create_btn(toolbar, "LOAD FILE", self.load_file)
        self.btn_save = self.create_btn(toolbar, "SAVE COPY", self.save_file)
        self.btn_close = self.create_btn(toolbar, "CLOSE", self.on_close, is_danger=True)
        
        # Main Content
        self.main_area = tk.Frame(self.root, bg=self.clr_bg)
        self.main_area.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Hex View
        tk.Label(self.main_area, text="HEX PREVIEW (READ ONLY)", bg=self.clr_bg, fg=self.clr_text).pack(anchor="w")
        self.hex_text = scrolledtext.ScrolledText(self.main_area, bg="#010409", fg=self.clr_accent,
                                                 font=("Consolas", 11), insertbackground="white")
        self.hex_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Status Bar
        self.status = tk.Label(self.root, text="READY. LOAD A FILE TO BEGIN.", bg=self.clr_card, fg="white", 
                              font=("Segoe UI", 9), pady=5)
        self.status.pack(fill=tk.X)

    def create_btn(self, parent, text, cmd, is_danger=False):
        fg = "#ff7b72" if is_danger else self.clr_accent
        btn = tk.Button(parent, text=text, command=cmd, bg=self.clr_card, fg=fg,
                        font=("Segoe UI", 9, "bold"), relief="flat", padx=15, pady=5,
                        activebackground=fg, activeforeground="black", cursor="hand2",
                        highlightthickness=1, highlightbackground=fg)
        btn.pack(side=tk.LEFT, padx=5)
        return btn

    def load_file(self):
        file_path = dialog_fixer.ask_open_filename_safe(self.root, filetypes=[("BIOS Files", "*.bin;*.rom;*.cap;*.fd"), ("All Files", "*.*")])
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    self.buffer = bytearray(f.read())
                self.current_file = file_path
                self.update_hex_view()
                self.status.config(text=f"LOADED: {os.path.basename(file_path)} ({len(self.buffer)} bytes)")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load file: {e}")

    def update_hex_view(self):
        self.hex_text.delete(1.0, tk.END)
        if not self.buffer: return
        
        # Show first 4KB for performance
        limit = min(len(self.buffer), 4096)
        output = []
        for i in range(0, limit, 16):
            chunk = self.buffer[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            output.append(f"{i:06X}: {hex_str:<47} | {ascii_str}")
        
        self.hex_text.insert(tk.END, "\n".join(output))
        if len(self.buffer) > limit:
            self.hex_text.insert(tk.END, f"\n... (Showing first {limit} bytes of {len(self.buffer)}) ...")

    def save_file(self):
        if not self.buffer: return
        file_path = dialog_fixer.ask_save_as_filename_safe(self.root, defaultextension=".bin")
        if file_path:
            try:
                with open(file_path, "wb") as f:
                    f.write(self.buffer)
                messagebox.showinfo("Success", "File saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def on_close(self):
        self.root.destroy()

def launch(parent):
    BIOSEditorWindow(parent)
