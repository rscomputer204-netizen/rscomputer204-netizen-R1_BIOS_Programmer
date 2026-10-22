import sys
import os
import ctypes
import tkinter as tk

# Ensure we can find the modules whether frozen or not
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

if base_path not in sys.path:
    sys.path.append(base_path)

def main():
    # 1. Driver Check
    driver_ok = False
    try:
        # Try loading standard FTDI libraries
        ctypes.windll.LoadLibrary("ftd2xx.dll")
        driver_ok = True
    except:
        try:
            ctypes.windll.LoadLibrary("ftd2xx64.dll")
            driver_ok = True
        except:
            pass

    if not driver_ok:
        # Alert User
        MessageBox = ctypes.windll.user32.MessageBoxW
        MessageBox(None, "FT232H driver not found.\nPlease install from drivers folder.", "Driver Missing", 0x30) # 0x30 = Warning Icon

        # Open Drivers Folder
        drv_path = os.path.join(base_path, "drivers", "FTDI")
        if not os.path.exists(drv_path):
            try:
                os.makedirs(drv_path)
            except:
                pass
        
        try:
            os.startfile(drv_path)
        except Exception as e:
            print(f"Could not open drivers folder: {e}")

    # 2. Launch Main GUI
    try:
        # Import the main GUI module from the external source files
        from ui import main_gui
        
        root = tk.Tk()
        
        # Initialize the app
        # This will use the existing logic in main_gui to load the interface
        app = main_gui.CyberFlashUltra(root)
        
        # Start the event loop
        root.mainloop()

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        MessageBox = ctypes.windll.user32.MessageBoxW
        MessageBox(None, f"Launch Fatal Error:\n{str(e)}\n\n{err}", "Critical Error", 0x10)

if __name__ == "__main__":
    main()
