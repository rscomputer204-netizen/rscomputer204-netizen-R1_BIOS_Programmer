import sys
sys.path.insert(0, 'python_version')
import tkinter as tk
from ui.main_gui import CyberFlashUltra

try:
    root = tk.Tk()
    app = CyberFlashUltra(root)
    chip = {'name': 'W25Q64FW', 'manufacturer': 'WINBOND', 'size': 8388608, 'page': 256, 'spicmd': 'SPI'}
    app.select_chip(chip)
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
