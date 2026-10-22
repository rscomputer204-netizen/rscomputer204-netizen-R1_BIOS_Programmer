import ctypes
import threading
import time
import tkinter as tk
from tkinter import filedialog
import os

# Windows API Constants
SW_NORMAL = 1
SW_RESTORE = 9
SW_SHOWNOACTIVATE = 4

class DialogFixer:
    """
    Background worker that watches for the next active GWL_STYLE dialog
    and forces it to be non-maximized and centered.
    """
    def __init__(self, root):
        self.root = root
        self.user32 = ctypes.windll.user32
        self.stop_event = threading.Event()

    def _get_window_rect(self, hwnd):
        rect = ctypes.wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def _center_logic(self, hwnd):
        # Get Screen Info
        screen_w = self.user32.GetSystemMetrics(0)
        screen_h = self.user32.GetSystemMetrics(1)
        
        # Target Size (50% of screen approx, or fixed compact)
        w = int(screen_w * 0.5)
        h = int(screen_h * 0.5)
        
        # Clamp min sizes
        w = max(w, 800)
        h = max(h, 600)
        
        # Calculate Center
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        
        # Force Restore (Un-maximize)
        self.user32.ShowWindow(hwnd, SW_NORMAL)
        
        # Move and Resize
        # SetWindowPos(hwnd, HWND_TOP, x, y, w, h, flags)
        # HWND_TOP = 0, SWP_SHOWWINDOW = 0x0040
        self.user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0040)
        
        # Force Focus
        self.user32.SetForegroundWindow(hwnd)

    def _watch_thread(self):
        # Watch for 3 seconds max (dialog usually appears instantly)
        start_time = time.time()
        while time.time() - start_time < 3.0:
            if self.stop_event.is_set():
                break
                
            # Get Foreground Window
            hwnd = self.user32.GetForegroundWindow()
            
            # Check if it's likely our dialog (Class #32770 is standard for file dialogs)
            length = self.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            
            # We assume if the foreground window changes to something that isn't our Main App, 
            # and it has standard dialog titles, it's the one.
            # Simplified: Just check if it's the file dialog class usually
            
            class_name = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW(hwnd, class_name, 256)
            
            if class_name.value == "#32770": # Standard Dialog Class
                # Found it!
                self._center_logic(hwnd)
                break
                
            time.sleep(0.05)

    def prepare_dialog(self):
        """Call this IMMEDIATELY before opening a dialog."""
        self.stop_event.clear()
        t = threading.Thread(target=self._watch_thread, daemon=True)
        t.start()

# Helper Wrapper Functions
def ask_open_filename_safe(parent, **options):
    fixer = DialogFixer(parent)
    fixer.prepare_dialog()
    # Enforce parent for modality
    options['parent'] = parent
    return filedialog.askopenfilename(**options)

def ask_save_as_filename_safe(parent, **options):
    fixer = DialogFixer(parent)
    fixer.prepare_dialog()
    options['parent'] = parent
    return filedialog.asksaveasfilename(**options)
