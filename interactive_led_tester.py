import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

def run_test():
    hw = FT232HDriver()
    if not hw.open():
        print("ERROR: Device could not be opened!")
        return

    print("=" * 65)
    print("       LIVE HARDWARE LED DIAGNOSTIC (WATCH THE BOARD)")
    print("=" * 65)

    try:
        # TEST 1: Active-LOW with 3.3V (AC0=1, AC3=0, AC6=1 -> 0x41)
        print("\n>>> [TEST 1] Active-LOW: 3.3V ON, AC3 = 0V (GND) [8 SECONDS]")
        print("    Logic: 3.3V -> LED Anode -> LED Cathode -> AC3 (LOW)")
        print("    Sending MPSSE [0x82, 0x41, 0xFF] (NO 0x87 extra byte)...")
        hw.write_raw([0x82, 0x41, 0xFF])
        for s in range(8, 0, -1):
            print(f"    --> Holding TEST 1... {s}s remaining")
            time.sleep(1)

        # TEST 2: Active-HIGH with 3.3V (AC0=1, AC3=1, AC6=1 -> 0x49)
        print("\n>>> [TEST 2] Active-HIGH: 3.3V ON, AC3 = 3.3V (HIGH) [8 SECONDS]")
        print("    Logic: If LED is connected to GND, it will light up NOW!")
        print("    Sending MPSSE [0x82, 0x49, 0xFF]...")
        hw.write_raw([0x82, 0x49, 0xFF])
        for s in range(8, 0, -1):
            print(f"    --> Holding TEST 2... {s}s remaining")
            time.sleep(1)

        # TEST 3: AC3 PURE SINK (All AC pins 0x00 except AC0=1 -> 0x01)
        print("\n>>> [TEST 3] Pure Sink Mode: AC0=3.3V (1), ALL OTHER PINS 0V (0x01) [8 SECONDS]")
        print("    Sending MPSSE [0x82, 0x01, 0xFF]...")
        hw.write_raw([0x82, 0x01, 0xFF])
        for s in range(8, 0, -1):
            print(f"    --> Holding TEST 3... {s}s remaining")
            time.sleep(1)

        # TEST 4: ALL ACBUS PINS DRIVEN HIGH (0xFF) [6 SECONDS]
        print("\n>>> [TEST 4] ALL ACBUS pins HIGH (0xFF): AC0-AC7 = 3.3V [6 SECONDS]")
        print("    (If LED is on any AC pin to GND, it MUST turn ON now)")
        hw.write_raw([0x82, 0xFF, 0xFF])
        for s in range(6, 0, -1):
            print(f"    --> Holding TEST 4... {s}s remaining")
            time.sleep(1)

        # TEST 5: ALL ACBUS PINS DRIVEN LOW (0x00) with 3.3V VCC [6 SECONDS]
        print("\n>>> [TEST 5] ALL ACBUS pins LOW (0x00): AC0-AC7 = 0V [6 SECONDS]")
        print("    (If LED is from fixed 3.3V to any AC pin, it MUST turn ON now)")
        hw.write_raw([0x82, 0x00, 0xFF])
        for s in range(6, 0, -1):
            print(f"    --> Holding TEST 5... {s}s remaining")
            time.sleep(1)

        # TEST 6: Slow alternating blink on AC3 (1 second ON, 1 second OFF, 5 times)
        print("\n>>> [TEST 6] Slow Blink on AC3 (Active-LOW: 0x41 vs 0x49) [10 SECONDS]")
        for i in range(1, 6):
            print(f"    Blink {i}/5: AC3 = LOW (0V) -> [LED SHOULD BE ON]")
            hw.write_raw([0x82, 0x41, 0xFF])
            time.sleep(1.0)
            print(f"    Blink {i}/5: AC3 = HIGH (3.3V) -> [LED SHOULD BE OFF]")
            hw.write_raw([0x82, 0x49, 0xFF])
            time.sleep(1.0)

    finally:
        print("\n>>> Safely resetting device and closing...")
        hw.set_voltage_pins("OFF")
        hw.close()
        print("Diagnostic test finished.")

if __name__ == '__main__':
    run_test()
