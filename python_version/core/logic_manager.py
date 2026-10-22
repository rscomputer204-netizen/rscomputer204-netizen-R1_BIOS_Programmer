import time
import os
import threading
from typing import Callable, Optional

class LogicManager:
    """
    Centralized controller for BIOS programmer operations.
    Acts as a bridge between the Frontend (PyQt) and the Hardware (DLL/Drivers).
    """
    def __init__(self, chip_db, hardware_wrapper, log_callback: Callable[[str], None]):
        self.db = chip_db
        self.hw = hardware_wrapper
        self.log = log_callback
        
        self.current_chip = None
        self.buffer = bytearray()
        self.is_busy = False
        
        self._stop_event = threading.Event()


    def set_chip(self, chip_info):
        self.current_chip = chip_info
        self.log(f"CHIP_SELECTED: {chip_info['manufacturer']} {chip_info['name']}")

    @staticmethod
    def validate_safe_write(chip_size_bytes, file_size_bytes):
        """
        Validates if the file size is safe to write to the chip.
        Normalization: Ensure inputs are integers (bytes).
        Rule: file_size > chip_size => UNSAFE (Critical Block)
        Returns: (bool, str) -> (is_safe, error_message)
        """
        try:
            c_size = int(chip_size_bytes)
            f_size = int(file_size_bytes)
        except (ValueError, TypeError):
             # If sizes cannot be cast to int, assume invalid/unsafe to be cautious
             return False, "Validation Error: Invalid size data structure."

        if f_size > c_size:
            msg = (f"Selected BIOS file ({f_size} bytes) is LARGER than\n"
                   f"detected chip capacity ({c_size} bytes).\n\n"
                   f"Writing is strictly blocked to prevent chip damage.\n"
                   f"Please select a correct BIOS file or target chip.")
            return False, msg
            
        return True, ""

    def read_chip(self, progress_callback: Optional[Callable[[float], None]] = None):
        if not self.current_chip:
            self.log("ERROR: No chip selected.")
            return False
            
        self.is_busy = True
        self.log(f"READ_START: {self.current_chip['name']}")
        
        try:
            # Placeholder for actual hardware call
            # In a real hybrid app, this would call self.hw.read_flash(...)
            size = self.current_chip['size']
            self.buffer = bytearray()
            
            chunk_size = 4096
            for addr in range(0, size, chunk_size):
                if self._stop_event.is_set():
                    self.log("READ_ABORTED by user.")
                    return False
                
                length = min(chunk_size, size - addr)
                data = self.hw.read_data(addr, length)
                if data is None:
                    self.log(f"READ_ERROR at address 0x{addr:X}")
                    return False
                
                self.buffer.extend(data)
                if progress_callback:
                    progress_callback((addr + length) / size * 100)
            
            self.log("READ_COMPLETE.")
            return True
        finally:
            self.is_busy = False

    def auto_sequence(self, file_path: str, progress_callback: Callable[[float, str], None]):
        """
        Executes the AUTO sequence: ID Check -> Erase -> Write -> Verify
        """
        if not self.current_chip:
            self.log("ERROR: No chip selected.")
            return False

        self.is_busy = True
        self.log("AUTO_SEQUENCE_INIT...")
        
        try:
            # 1. ID Check
            self.log("AUTO_STEP [1/4]: Checking JEDEC ID...")
            detected_id = self.hw.read_id()
            if detected_id.upper() != self.current_chip['id'].upper():
                self.log(f"ERROR: ID Mismatch! Expected: {self.current_chip['id']}, Detected: {detected_id}")
                return False
            self.log("ID Match Verified.")

            # 2. Erase
            self.log("AUTO_STEP [2/4]: Erasing Flash...")
            if not self.hw.erase_chip():
                self.log("ERROR: Erase failed.")
                return False
            self.log("Erase Successful.")

            # 3. Write
            self.log("AUTO_STEP [3/4]: Writing Data...")
            # Load file if provided
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    self.buffer = bytearray(f.read())
            
            if len(self.buffer) == 0:
                self.log("ERROR: Buffer empty, nothing to write.")
                return False
                
            if not self.hw.write_data(0, self.buffer, progress_callback=lambda p: progress_callback(p, "Writing")):
                self.log("ERROR: Write failed.")
                return False

            # 4. Verify
            self.log("AUTO_STEP [4/4]: Verifying...")
            if not self.hw.verify_data(0, self.buffer, progress_callback=lambda p: progress_callback(p, "Verifying")):
                self.log("ERROR: Verification failed.")
                return False
            
            self.log("AUTO_SEQUENCE_SUCCESSFUL.")
            return True
        except Exception as e:
            self.log(f"AUTO_FATAL_ERROR: {str(e)}")
            return False
        finally:
            self.is_busy = False

    def abort(self):
        self._stop_event.set()
        self.log("ABORT_SIGNAL_SENT.")
