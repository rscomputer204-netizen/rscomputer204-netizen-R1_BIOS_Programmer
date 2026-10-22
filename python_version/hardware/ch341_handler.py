import ctypes
import os

class CH341Driver:
    def __init__(self, dll_path):
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found: {dll_path}")
        
        self.dll = ctypes.windll.LoadLibrary(dll_path)
        self.handle = -1
        self.device_index = 0
        
        # Function Prototypes
        self.dll.CH341OpenDevice.argtypes = [ctypes.c_uint]
        self.dll.CH341OpenDevice.restype = ctypes.c_int
        
        self.dll.CH341CloseDevice.argtypes = [ctypes.c_uint]
        self.dll.CH341CloseDevice.restype = None
        
        self.dll.CH341SetStream.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self.dll.CH341SetStream.restype = ctypes.c_bool

        self.dll.CH341StreamSPI4.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
        self.dll.CH341StreamSPI4.restype = ctypes.c_bool

        self.dll.CH341GetStatus.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_ulong)]
        self.dll.CH341GetStatus.restype = ctypes.c_bool

        self.dll.CH341Set_D5_D0.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
        self.dll.CH341Set_D5_D0.restype = ctypes.c_bool

    def open(self):
        self.handle = self.dll.CH341OpenDevice(self.device_index)
        return self.handle != -1

    def close(self):
        if self.handle != -1:
            self.dll.CH341CloseDevice(self.device_index)
            self.handle = -1

    def set_spi_speed(self, speed_mode):
        """
        speed_mode: 0=20KHz, 01=100KHz, 10=400KHz, 11=750KHz
        bit 7: 0=LSB first, 1=MSB first
        """
        mode = (1 << 7) | (speed_mode & 0x03)
        return self.dll.CH341SetStream(self.device_index, mode)

    def spi_write_read(self, chip_select, data):
        """
        chip_select: 0x80 | 0x00 (D0)
        data: bytes to write
        returns: bytes read
        """
        buffer = (ctypes.c_ubyte * len(data))(*data)
        if self.dll.CH341StreamSPI4(self.device_index, chip_select, len(data), buffer):
            return bytes(buffer)
        return None

    def get_pins_status(self):
        status = ctypes.c_ulong()
        if self.dll.CH341GetStatus(self.device_index, ctypes.byref(status)):
            return status.value
        return None

if __name__ == "__main__":
    # Test script (requires connected hardware)
    dll_path = os.path.abspath("../../drivers/CH34X/CH341DLL.DLL")
    try:
        driver = CH341Driver(dll_path)
        if driver.open():
            print("Successfully opened CH341A device.")
            driver.set_spi_speed(1) # 100KHz
            # Attempt to read SPI ID (standard 9Fh command)
            response = driver.spi_write_read(0x80, [0x9F, 0x00, 0x00, 0x00])
            if response:
                print(f"SPI ID Response: {response.hex().upper()}")
            driver.close()
        else:
            print("CH341A device not found.")
    except Exception as e:
        print(f"Error: {e}")
