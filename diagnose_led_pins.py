import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver

def test_pin_readback():
    hw = FT232HDriver()
    if not hw.open():
        print("Failed to open FT232H!")
        return

    print("FT232H opened.")
    hw.set_voltage_pins("3.3V")
    time.sleep(0.1)

    # Function to read ACBUS state using 0x83 command
    def read_acbus():
        hw.write_raw([0x83, 0x87]) # 0x83 = Read High Byte, 0x87 = Send Immediate
        res = hw.read_raw(1, timeout_ms=500)
        return res[0] if res else None

    print("\n--- Diagnostic: Reading ACBUS register ---")
    
    # State 1: LED OFF (AC3=1)
    hw.set_led(False)
    time.sleep(0.05)
    val_off = read_acbus()
    print(f"LED OFF: written 0x{hw.current_acbus_val:02X}, read back ACBUS = 0x{val_off:02X}" if val_off is not None else "Read failed")

    # State 2: LED ON (AC3=0)
    hw.set_led(True)
    time.sleep(0.05)
    val_on = read_acbus()
    print(f"LED ON : written 0x{hw.current_acbus_val:02X}, read back ACBUS = 0x{val_on:02X}" if val_on is not None else "Read failed")

    print("\n--- Testing all ACBUS pins toggling ---")
    # Let's toggle bit 3 (AC3) 10 times with 0.5s delay so user can observe
    print("Toggling AC3 (Active-LOW: 0=ON, 1=OFF) 5 times slowly...")
    for i in range(5):
        print(f"[{i+1}/5] AC3 -> LOW (0) [LED SHOULD BE ON NOW]")
        hw.write_raw([0x82, 0x41, 0xFF, 0x87]) # AC0=1 (3.3V), AC3=0, AC6=1
        time.sleep(0.7)
        
        print(f"[{i+1}/5] AC3 -> HIGH (1) [LED SHOULD BE OFF NOW]")
        hw.write_raw([0x82, 0x49, 0xFF, 0x87]) # AC0=1 (3.3V), AC3=1, AC6=1
        time.sleep(0.7)

    print("\nNow testing AC3 Active-HIGH (in case LED is wired to GND):")
    print("Driving AC3 HIGH (1) with AC0=0...")
    hw.write_raw([0x82, 0x08, 0xFF, 0x87]) # AC3=1, all other AC pins 0
    time.sleep(1.5)
    hw.write_raw([0x82, 0x00, 0xFF, 0x87]) # AC3=0
    time.sleep(0.5)

    print("Closing device...")
    hw.set_voltage_pins("OFF")
    hw.close()
    print("Diagnostic complete.")

if __name__ == '__main__':
    test_pin_readback()
