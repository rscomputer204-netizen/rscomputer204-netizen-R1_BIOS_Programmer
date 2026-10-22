import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QPushButton, QListWidget, QLabel, QTextEdit, 
                             QProgressBar, QLineEdit, QFrame, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

# Import logic components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.chip_db import ChipDatabase
from core.logic_manager import LogicManager
from hardware_lib.hardware_wrapper import HardwareWrapper

class WorkerThread(QThread):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(bool, str)
    log_msg = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result, "Operation completed.")
        except Exception as e:
            self.finished.emit(False, str(e))

class CyberFlashPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CYBERFLASH PRO - Hybrid BIOS Programmer")
        self.resize(1200, 800)
        
        # Initialize Core
        self.db = ChipDatabase(os.path.join(os.path.dirname(os.path.dirname(__file__)), "chiplist.xml"))
        self.hw = HardwareWrapper(self.add_log)
        self.logic = LogicManager(self.db, self.hw, self.add_log)
        
        self.init_ui()
        self.apply_theme()

    def apply_theme(self):
        # Dark Stealth Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; }
            QWidget { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #30363d; border-radius: 5px; margin-top: 10px; font-weight: bold; color: #58a6ff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QPushButton { background-color: #21262d; border: 1px solid #30363d; padding: 8px; border-radius: 4px; min-width: 80px; }
            QPushButton:hover { background-color: #30363d; border-color: #8b949e; }
            QPushButton#actionBtn { background-color: #238636; color: white; font-weight: bold; }
            QPushButton#actionBtn:hover { background-color: #2ea043; }
            QPushButton#dangerBtn { background-color: #da3633; color: white; }
            QPushButton#autoBtn { background-color: #1f6feb; color: white; font-size: 14px; padding: 12px; }
            QListWidget { background-color: #010409; border: 1px solid #30363d; border-radius: 4px; outline: none; }
            QListWidget::item:selected { background-color: #1f6feb; }
            QTextEdit { background-color: #010409; border: 1px solid #30363d; font-family: 'Consolas'; color: #7ee787; }
            QLineEdit { background-color: #010409; border: 1px solid #30363d; padding: 5px; border-radius: 4px; }
            QProgressBar { border: 1px solid #30363d; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #1f6feb; }
        """)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel (Chip Selection)
        left_panel = QVBoxLayout()
        
        search_group = QGroupBox("CHIP SELECTION")
        search_layout = QVBoxLayout(search_group)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Brand or Model...")
        self.search_input.textChanged.connect(self.filter_chips)
        search_layout.addWidget(self.search_input)
        
        self.chip_list = QListWidget()
        self.chip_list.itemClicked.connect(self.on_chip_selected)
        search_layout.addWidget(self.chip_list)
        
        left_panel.addWidget(search_group)
        
        # IC Info Group
        info_group = QGroupBox("IC PROPERTIES")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("Select a chip to view details")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        left_panel.addWidget(info_group)

        main_layout.addLayout(left_panel, 1)

        # Right Panel (Operations & Log)
        right_panel = QVBoxLayout()
        
        # Operation Buttons
        btn_layout = QHBoxLayout()
        self.read_btn = QPushButton("READ")
        self.read_btn.clicked.connect(self.start_read)
        self.erase_btn = QPushButton("ERASE")
        self.erase_btn.setObjectName("dangerBtn")
        self.write_btn = QPushButton("WRITE")
        self.verify_btn = QPushButton("VERIFY")
        self.auto_btn = QPushButton("AUTO (SMART SEQUENCE)")
        self.auto_btn.setObjectName("autoBtn")
        self.auto_btn.clicked.connect(self.start_auto)
        
        for b in [self.read_btn, self.erase_btn, self.write_btn, self.verify_btn]:
            btn_layout.addWidget(b)
        
        right_panel.addLayout(btn_layout)
        right_panel.addWidget(self.auto_btn)
        
        # Progress
        self.progress_bar = QProgressBar()
        right_panel.addWidget(self.progress_bar)
        
        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        right_panel.addWidget(QLabel("SYSTEM LOG"))
        right_panel.addWidget(self.log_output)
        
        main_layout.addLayout(right_panel, 2)
        
        # Initial Filter
        self.filter_chips()

    def add_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def filter_chips(self):
        query = self.search_input.text().upper()
        self.chip_list.clear()
        count = 0
        for chip in self.db.chips:
            if query in chip['name'].upper() or query in chip['manufacturer'].upper():
                self.chip_list.addItem(f"{chip['manufacturer']} - {chip['name']}")
                count += 1
                if count > 100: break # Performance limit

    def on_chip_selected(self, item):
        text = item.text()
        manufacturer, name = text.split(" - ")
        for chip in self.db.chips:
            if chip['name'] == name and chip['manufacturer'] == manufacturer:
                self.logic.set_chip(chip)
                details = (f"<b>Manufacturer:</b> {chip['manufacturer']}<br>"
                           f"<b>Model:</b> {chip['name']}<br>"
                           f"<b>ID:</b> {chip['id']}<br>"
                           f"<b>Size:</b> {chip['size']} Bytes<br>"
                           f"<b>Page:</b> {chip['page']}")
                self.info_label.setText(details)
                break

    def start_read(self):
        self.progress_bar.setValue(0)
        self.worker = WorkerThread(self.logic.read_chip, progress_callback=self.progress_bar.setValue)
        self.worker.finished.connect(self.on_op_finished)
        self.worker.start()

    def start_auto(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Select BIOS File", "", "Binary Files (*.bin *.rom)")
        if file_path:
            self.progress_bar.setValue(0)
            self.worker = WorkerThread(self.logic.auto_sequence, file_path, 
                                        progress_callback=lambda p, s: (self.progress_bar.setValue(int(p)), self.add_log(f"Auto: {s}...")))
            self.worker.finished.connect(self.on_op_finished)
            self.worker.start()

    def on_op_finished(self, success, message):
        if success:
            self.add_log("SUCCESS: Operation finished.")
        else:
            self.add_log(f"ERROR: {message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CyberFlashPro()
    window.show()
    sys.exit(app.exec())
