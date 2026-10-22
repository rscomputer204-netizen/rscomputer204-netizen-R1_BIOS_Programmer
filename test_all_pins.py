import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

def test_all():
    hw = FT232HDriver()
    if not hw.open():
        print("ERROR: Device could not be opened!")
        return

    print("=" * 65)
    print("      TESTING ALL PINS ON FT232H (ADBUS + ACBUS)")
    print("=" * 65)

    try:
        # Phase 1: Drive EVERYTHING HIGH (Both ADBUS D0-D7 and ACBUS C0-C7 = 3.3V)
        print("\n>>> [PHASE 1] Driving ALL ADBUS and ALL ACBUS pins HIGH (3.3V) [7s]...")
        print("    If LED cathode is to GND, ANY pin connected will LIGHT UP NOW!")
        hw.write_raw([0x80, 0xFF, 0xFF]) # ADBUS all HIGH
        hw.write_raw([0x82, 0xFF, 0xFF]) # ACBUS all HIGH
        for s in range(7, 0, -1):
            print(f"    --> Phase 1 (All HIGH): {s}s remaining...")
            time.sleep(1)

        # Phase 2: Drive EVERYTHING LOW (Both ADBUS D0-D7 and ACBUS C0-C7 = 0V / GND)
        print("\n>>> [PHASE 2] Driving ALL ADBUS and ALL ACBUS pins LOW (0V / GND) [7s]...")
        print("    If LED anode is to 3.3V, ANY pin connected will LIGHT UP NOW!")
        hw.write_raw([0x80, 0x00, 0xFF]) # ADBUS all LOW (GND)
        hw.write_raw([0x82, 0x00, 0xFF]) # ACBUS all LOW (GND)
        for s in range(7, 0, -1):
            print(f"    --> Phase 2 (All LOW / GND): {s}s remaining...")
            time.sleep(1)

        # Phase 3: What if 3.3V comes from AC0 (Target Voltage Switch)?
        # AC0 = 3.3V (HIGH), and ALL other pins LOW (GND)
        print("\n>>> [PHASE 3] AC0 (3.3V Relay) = HIGH, ALL other ADBUS & ACBUS pins = 0V (GND) [7s]...")
        print("    (If LED gets 3.3V from the target VCC switch, it will light up NOW!)")
        hw.write_raw([0x80, 0x00, 0xFF]) # ADBUS all 0V
        hw.write_raw([0x82, 0x01, 0xFF]) # AC0=HIGH (3.3V), C1-C7 = 0V (GND)
        for s in range(7, 0, -1):
            print(f"    --> Phase 3: {s}s remaining...")
            time.sleep(1)

        # Phase 4: Test each pin individually (Pin Walking)
        # ADBUS free pins: AD4 (D4), AD5 (D5), AD6 (D6), AD7 (D7)
        print("\n>>> [PHASE 4] Testing ADBUS pins (D4, D5, D6, D7) one by one pulled LOW...")
        for pin_name, val in [("D4", 0xEF), ("D5", 0xDF), ("D6", 0xBF), ("D7", 0x7F)]:
            print(f"    Testing pin {pin_name} = LOW (0V) [2s]...")
            hw.write_raw([0x80, val, 0xFF])
            hw.write_raw([0x82, 0x01, 0xFF]) # AC0 3.3V enabled
            time.sleep(2)

    finally:
        print("\nSafely resetting device and closing...")
        hw.set_voltage_pins("OFF")
        hw.close()
        print("Test Complete.")

if __name__ == '__main__':
    test_all()
