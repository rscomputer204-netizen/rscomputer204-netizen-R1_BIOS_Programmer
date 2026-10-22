import ctypes
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

class FT_EEPROM_FT232H(ctypes.Structure):
    _fields_ = [
        ("DeviceType", ctypes.c_uint32),
        ("VendorId", ctypes.c_uint16),
        ("ProductId", ctypes.c_uint16),
        ("Manufacturer", ctypes.c_char * 32),
        ("ManufacturerId", ctypes.c_char * 16),
        ("Description", ctypes.c_char * 64),
        ("SerialNumber", ctypes.c_char * 16),
        ("MaxPower", ctypes.c_uint16),
        ("PnP", ctypes.c_uint8),
        ("SelfPowered", ctypes.c_uint8),
        ("RemoteWakeup", ctypes.c_uint8),
        # FT232H specific:
        ("PullDownEnable", ctypes.c_uint8),
        ("SerNumEnable", ctypes.c_uint8),
        ("ACSlowSlew", ctypes.c_uint8),
        ("ACSchmittInput", ctypes.c_uint8),
        ("ACDriveCurrent", ctypes.c_uint8),
        ("ADSlowSlew", ctypes.c_uint8),
        ("ADSchmittInput", ctypes.c_uint8),
        ("ADDriveCurrent", ctypes.c_uint8),
        # ACBUS pins configuration:
        ("Cbus0", ctypes.c_uint8),
        ("Cbus1", ctypes.c_uint8),
        ("Cbus2", ctypes.c_uint8),
        ("Cbus3", ctypes.c_uint8),
        ("Cbus4", ctypes.c_uint8),
        ("Cbus5", ctypes.c_uint8),
        ("Cbus6", ctypes.c_uint8),
        ("Cbus7", ctypes.c_uint8),
        ("Cbus8", ctypes.c_uint8),
        ("Cbus9", ctypes.c_uint8),
        ("FT1248Cpol", ctypes.c_uint8),
        ("FT1248Lsb", ctypes.c_uint8),
        ("FT1248FlowControl", ctypes.c_uint8),
        ("IsVCP", ctypes.c_uint8),
        ("PowerSaveEnable", ctypes.c_uint8),
    ]

def check_eeprom_structure():
    hw = FT232HDriver()
    if not hw.open():
        print("Cannot open FT232H")
        return
        
    print("[+] Device opened.")
    
    # Check FT_EEPROM_Read
    if hasattr(hw.ft, 'FT_EEPROM_Read'):
        eeprom = FT_EEPROM_FT232H()
        eeprom.DeviceType = 0x08 # FT_DEVICE_232H
        mfg = (ctypes.c_char * 32)()
        mfg_id = (ctypes.c_char * 16)()
        desc = (ctypes.c_char * 64)()
        ser = (ctypes.c_char * 16)()
        
        res = hw.ft.FT_EEPROM_Read(
            hw.handle,
            ctypes.byref(eeprom),
            ctypes.sizeof(eeprom),
            mfg, mfg_id, desc, ser
        )
        print(f"FT_EEPROM_Read result: {res}")
        if res == 0:
            print(f"Manufacturer: {mfg.value.decode('latin1', 'ignore')}")
            print(f"Description: {desc.value.decode('latin1', 'ignore')}")
            print(f"Serial: {ser.value.decode('latin1', 'ignore')}")
            print(f"ACDriveCurrent: {eeprom.ACDriveCurrent}")
            print(f"Cbus0 (AC0): 0x{eeprom.Cbus0:02X}")
            print(f"Cbus1 (AC1): 0x{eeprom.Cbus1:02X}")
            print(f"Cbus2 (AC2): 0x{eeprom.Cbus2:02X}")
            print(f"Cbus3 (AC3): 0x{eeprom.Cbus3:02X}")
            print(f"Cbus4 (AC4): 0x{eeprom.Cbus4:02X}")
            print(f"Cbus5 (AC5): 0x{eeprom.Cbus5:02X}")
            print(f"Cbus6 (AC6): 0x{eeprom.Cbus6:02X}")
            print(f"Cbus7 (AC7): 0x{eeprom.Cbus7:02X}")
            print(f"Cbus8 (AC8): 0x{eeprom.Cbus8:02X}")
            print(f"Cbus9 (AC9): 0x{eeprom.Cbus9:02X}")
    else:
        print("FT_EEPROM_Read not found in DLL.")

    hw.close()

if __name__ == '__main__':
    check_eeprom_structure()
