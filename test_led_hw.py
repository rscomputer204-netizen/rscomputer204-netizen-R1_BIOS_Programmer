import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver

def main():
    print("=== FT232H LED HARDWARE TEST ===")
    hw = FT232HDriver()
    if not hw.open():
        print("FAILED to open FT232H device!")
        return

    print("Device opened successfully.")
    print("Setting Voltage to 3.3V...")
    hw.set_voltage_pins("3.3V")
    time.sleep(0.5)

    print(f"Current ACBUS value: 0x{hw.current_acbus_val:02X}")

    print("\n--- TEST 1: set_led(True) for 3 seconds ---")
    print("Calling hw.set_led(True)...")
    hw.set_led(True)
    print(f"ACBUS value after set_led(True): 0x{hw.current_acbus_val:02X}")
    time.sleep(3.0)

    print("\n--- Turning LED OFF ---")
    print("Calling hw.set_led(False)...")
    hw.set_led(False)
    print(f"ACBUS value after set_led(False): 0x{hw.current_acbus_val:02X}")
    time.sleep(2.0)

    print("\n--- TEST 2: Rapid Blink (5 cycles) ---")
    for i in range(5):
        print(f"Blink cycle {i+1}: ON")
        hw.set_led(True)
        time.sleep(0.3)
        print(f"Blink cycle {i+1}: OFF")
        hw.set_led(False)
        time.sleep(0.3)

    print("\nClosing hardware...")
    hw.set_voltage_pins("OFF")
    hw.close()
    print("Test finished successfully.")

if __name__ == '__main__':
    main()
