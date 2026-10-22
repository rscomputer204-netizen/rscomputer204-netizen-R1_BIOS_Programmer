import ctypes
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver

# FT_PROGRAM_DATA structure for FT232H
class FT_PROGRAM_DATA(ctypes.Structure):
    _fields_ = [
        ("Signature1", ctypes.c_uint32),
        ("Signature2", ctypes.c_uint32),
        ("Version", ctypes.c_uint32),
        ("VendorId", ctypes.c_uint16),
        ("ProductId", ctypes.c_uint16),
        ("Manufacturer", ctypes.c_char_p),
        ("ManufacturerId", ctypes.c_char_p),
        ("Description", ctypes.c_char_p),
        ("SerialNumber", ctypes.c_char_p),
        ("MaxPower", ctypes.c_uint16),
        ("PnP", ctypes.c_uint16),
        ("SelfPowered", ctypes.c_uint16),
        ("RemoteWakeup", ctypes.c_uint16),
        # FT232H specific fields...
    ]

def read_eeprom():
    hw = FT232HDriver()
    if not hw.open():
        print("Could not open FT232H")
        return
        
    print("[+] Device opened.")
    
    # Let's inspect raw EEPROM words (typically 64 or 128 words of 16-bit)
    print("Reading raw EEPROM words:")
    eeprom_data = []
    val = ctypes.c_uint16()
    for addr in range(64):
        res = hw.ft.FT_ReadEE(hw.handle, addr, ctypes.byref(val))
        if res == 0:
            eeprom_data.append(val.value)
        else:
            break
            
    if eeprom_data:
        print("EEPROM words (first 32):")
        for i in range(0, min(32, len(eeprom_data)), 8):
            print(f"  {i:02X}: " + " ".join(f"{w:04X}" for w in eeprom_data[i:i+8]))
    else:
        print("FT_ReadEE failed or not supported directly.")

    hw.close()

if __name__ == '__main__':
    read_eeprom()
