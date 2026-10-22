import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver
from core.spi25_handler import SPI25Handler

def test_program_led():
    print("=" * 60)
    print("      R1 BIOS PROGRAMMER - LED & HARDWARE TEST")
    print("=" * 60)
    
    hw = FT232HDriver()
    if not hw.open():
        print("[-] ERROR: FT232H device could not be opened!")
        return False
        
    print("[+] FT232H Hardware Connected Successfully.")
    
    try:
        # Step 1: Set 3.3V
        print("\n[Step 1] Setting Voltage to 3.3V (AC0 = HIGH)...")
        hw.set_voltage_pins("3.3V")
        time.sleep(0.1)
        print(f"    Current ACBUS Register: 0x{hw.current_acbus_val:02X}")
        
        # Step 2: Try Chip Detect
        spi = SPI25Handler(hw)
        jedec = spi.read_id()
        print(f"[Step 2] Reading Chip JEDEC ID: {jedec if jedec else 'No response'}")

        # Step 3: Test A - Active-LOW LED ON (AC3 = 0, AC0 = 1)
        print("\n[Step 3] TEST A: Turning Program LED ON (Active-LOW: AC3=0) for 4 seconds...")
        hw.set_led(True)
        print(f"    --> ACBUS value set to: 0x{hw.current_acbus_val:02X} (AC3 is LOW)")
        print("    [!] Check your programmer board NOW: Is the Program LED ON?")
        for s in range(4, 0, -1):
            print(f"        Remaining: {s}s...")
            time.sleep(1.0)
            
        # Step 4: Turning LED OFF
        print("\n[Step 4] Turning Program LED OFF (AC3=1) for 2 seconds...")
        hw.set_led(False)
        print(f"    --> ACBUS value set to: 0x{hw.current_acbus_val:02X} (AC3 is HIGH)")
        time.sleep(2.0)

        # Step 5: Test B - Rapid Blink
        print("\n[Step 5] TEST B: Blinking Program LED 6 times (0.4s intervals)...")
        for i in range(1, 7):
            hw.set_led(True)
            print(f"    [{i}/6] LED ON  (AC3=0)")
            time.sleep(0.4)
            hw.set_led(False)
            print(f"    [{i}/6] LED OFF (AC3=1)")
            time.sleep(0.4)

        # Step 6: Test C - Active-HIGH test (if LED cathode is GND and anode is AC3)
        print("\n[Step 6] TEST C: Testing Active-HIGH (AC3=1, AC0=0) for 3 seconds...")
        print("    (In case LED is wired with Cathode to GND instead of 3.3V)")
        hw.write_raw([hw.SET_HIGH_BYTE, 0x08, 0xFF, hw.SEND_IMMEDIATE]) # AC3=1, others 0
        time.sleep(3.0)
        hw.write_raw([hw.SET_HIGH_BYTE, 0x00, 0xFF, hw.SEND_IMMEDIATE])
        
        # Step 7: Simulated Read with LED ON
        print("\n[Step 7] TEST D: Simulating Read Operation with LED ON...")
        hw.set_voltage_pins("3.3V")
        hw.set_led(True)
        print(f"    LED is ON. Simulating 3-second data read...")
        time.sleep(3.0)
        hw.set_led(False)
        print("    Read simulation finished, LED turned OFF.")
        
    finally:
        print("\n[Final] Safely resetting pins and closing device...")
        hw.set_voltage_pins("OFF")
        hw.close()
        print("[+] Test Completed.\n")

if __name__ == '__main__':
    test_program_led()
