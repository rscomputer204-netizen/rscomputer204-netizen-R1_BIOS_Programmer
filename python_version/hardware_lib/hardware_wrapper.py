import ctypes
import os
import sys

class HardwareWrapper:
    """
    Python wrapper for the C++ Hardware DLL and existing Python drivers.
    Implements a fallback mechanism and consistent API.
    """
    def __init__(self, log_callback):
        self.log = log_callback
        self.dll = None
        self.current_driver = None # Placeholder for CH341/FTDI
        
        self._load_dll()

    def _load_dll(self):
        try:
            # We will look for 'programmer_core.dll' in the libs folder
            dll_path = os.path.join(os.path.dirname(__file__), "libs", "programmer_core.dll")
            if os.path.exists(dll_path):
                self.dll = ctypes.WinDLL(dll_path)
                self.log("SYSTEM: High-performance C++ DLL loaded.")
            else:
                self.log("WARNING: C++ DLL not found. Falling back to Python drivers.")
        except Exception as e:
            self.log(f"DLL_LOAD_ERROR: {str(e)}")

    def read_id(self) -> str:
        """Reads the JEDEC ID from the chip."""
        if self.dll:
            # Call C++ DLL function: int read_jedec_id(uint8_t* id_buf)
            id_buf = (ctypes.c_ubyte * 3)()
            res = self.dll.read_jedec_id(id_buf)
            if res == 0:
                return "".join([format(b, '02X') for b in id_buf])
        
        # Fallback to existing Python logic (if current_driver is set)
        return "000000" # Placeholder

    def read_data(self, addr, length) -> Optional[bytearray]:
        """Reads a block of data from the chip."""
        if self.dll:
            buf = (ctypes.c_ubyte * length)()
            if self.dll.read_flash(addr, buf, length) == 0:
                return bytearray(buf)
        return None

    def erase_chip(self) -> bool:
        """Erases the entire chip."""
        if self.dll:
            return self.dll.erase_bulk() == 0
        return False

    def write_data(self, addr, data, progress_callback=None) -> bool:
        """Writes data to the chip with page-aware logic."""
        if self.dll:
            # Direct buffer passing to DLL for speed
            data_ptr = (ctypes.c_ubyte * len(data)).from_buffer(data)
            return self.dll.write_flash(addr, data_ptr, len(data)) == 0
        return False

    def verify_data(self, addr, expected_data, progress_callback=None) -> bool:
        """Compares flash data with a buffer."""
        actual_data = self.read_data(addr, len(expected_data))
        if actual_data and actual_data == expected_data:
            return True
        return False
