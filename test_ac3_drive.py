import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

def test_drive():
    hw = FT232HDriver()
    if not hw.open():
        print("Cannot open FT232H")
        return
        
    print("=" * 60)
    print("TESTING AC3 VOLTAGE & DRIVE STRENGTH")
    print("=" * 60)

    # 1. Standard Push-Pull LOW: All AC pins LOW, Direction all Outputs (0xFF)
    print("\n[Mode 1] Driving ALL ACBUS pins directly to 0x00 (GND, Direction=0xFF)...")
    print("--> AC3 should be driven to 0V (GND) by hardware push-pull driver.")
    hw.write_raw([0x82, 0x00, 0xFF, hw.SEND_IMMEDIATE])
    print("Holding for 5 seconds... Check AC3 with multimeter!")
    time.sleep(5)

    # 2. Standard Push-Pull HIGH: AC3=HIGH, others LOW
    print("\n[Mode 2] Driving AC3 HIGH (0x08, Direction=0xFF)...")
    hw.write_raw([0x82, 0x08, 0xFF, hw.SEND_IMMEDIATE])
    print("Holding for 5 seconds... Check AC3 with multimeter!")
    time.sleep(5)

    # 3. Open-Drain Mode (Drive-0 Only) using 0x9E command
    print("\n[Mode 3] Configuring Open-Drain (Drive-Zero Only) via 0x9E command...")
    # 0x9E <LowByteMask> <HighByteMask>: 0x08 enables Drive-0 for AC3
    hw.write_raw([0x9E, 0x00, 0x08, hw.SEND_IMMEDIATE])
    # Now set AC3=0 (Drive active low)
    hw.write_raw([0x82, 0x00, 0xFF, hw.SEND_IMMEDIATE])
    print("Holding Open-Drain LOW for 5 seconds... Check AC3 with multimeter!")
    time.sleep(5)

    # 4. Disable Drive-Zero (back to normal)
    hw.write_raw([0x9E, 0x00, 0x00, hw.SEND_IMMEDIATE])

    # 5. What about when 3.3V Relay (AC0) is ON?
    print("\n[Mode 4] Normal 3.3V Operation (AC0=1, AC3=0, AC6=1 -> 0x41)...")
    hw.write_raw([0x82, 0x41, 0xFF, hw.SEND_IMMEDIATE])
    print("Holding 0x41 for 5 seconds... Check AC3 with multimeter!")
    time.sleep(5)

    hw.set_voltage_pins("OFF")
    hw.close()
    print("\nTest completed.")

if __name__ == '__main__':
    test_drive()
