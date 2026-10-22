import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

def main():
    hw = FT232HDriver()
    if not hw.open():
        print("ERROR: Device could not be opened!")
        return

    print("=" * 65)
    print("      ALL-PINS GROUNDED TEST (ACTIVE FOR 3 MINUTES)")
    print("=" * 65)

    # AC0 = 1 (3.3V power switch enabled)
    # AC1-AC7 = 0 (ALL ACBUS PINS DRIVEN TO 0V / GND)
    # AD0-AD7 = 0 (ALL ADBUS PINS DRIVEN TO 0V / GND)
    print("\n[+] 3.3V is ON (AC0=1).")
    print("[+] ALL OTHER PINS on the entire board are now locked to GND (0V)!")
    print("\n" + "#" * 65)
    print(">>> EVERY PIN IS GROUND (0V) RIGHT NOW! <<<")
    print(">>> Touch your LED wire to C3, or D4, D5, D6, D7 <<<")
    print(">>> See which pin lights up your LED! <<<")
    print("#" * 65 + "\n")

    total_seconds = 180
    start = time.time()
    try:
        while time.time() - start < total_seconds:
            # Force all AC pins 0V (except AC0 3.3V switch)
            hw.write_raw([0x82, 0x01, 0xFF])
            # Force all AD pins 0V
            hw.write_raw([0x80, 0x00, 0xFF])
            
            rem = int(total_seconds - (time.time() - start))
            if rem % 10 == 0:
                print(f"[ACTIVE] All pins = 0V (GND) | Remaining: {rem}s")
            time.sleep(1.0)
    finally:
        hw.set_voltage_pins("OFF")
        hw.close()
        print("\nDevice closed safely.")

if __name__ == '__main__':
    main()
