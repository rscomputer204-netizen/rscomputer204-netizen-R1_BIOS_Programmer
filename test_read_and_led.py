import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver
from core.spi25_handler import SPI25Handler

def main():
    print("=== TESTING HARDWARE CONNECTION & CHIP ===")
    hw = FT232HDriver()
    if not hw.open():
        print("ERROR: Device could not be opened!")
        return

    print("FT232H opened successfully.")
    
    # Test voltages and read chip ID
    for volt in ["3.3V", "1.8V"]:
        print(f"\n--- Testing with Voltage: {volt} ---")
        hw.set_voltage_pins(volt)
        time.sleep(0.050)
        
        # Test LED ON
        print("Turning LED ON (set_led(True))...")
        hw.set_led(True)
        print(f"ACBUS register value: 0x{hw.current_acbus_val:02X}")
        
        spi = SPI25Handler(hw)
        jedec = spi.read_id()
        print(f"JEDEC ID detected: {jedec}")
        
        if jedec and jedec not in ["000000", "FFFFFF"]:
            print(f"--> Chip successfully identified at {volt}: {jedec}")
            
            # Read first 64 bytes
            data = spi.read_data(0, 64)
            print(f"Sample data (first 16 bytes): {data[:16].hex() if data else 'None'}")
            
            print("Keeping LED ON for 2 seconds...")
            time.sleep(2)
            break
        else:
            print("No valid chip detected with this voltage.")
            hw.set_led(False)

    print("\nTurning LED OFF (set_led(False))...")
    hw.set_led(False)
    print(f"ACBUS register value: 0x{hw.current_acbus_val:02X}")
    time.sleep(1)

    print("\nTesting LED Polarity on AC3:")
    print("State A: AC3 = LOW (0), AC0 (3.3V) = HIGH (1)")
    hw.set_voltage_pins("3.3V")
    hw.write_raw([hw.SET_HIGH_BYTE, 0x41, 0xFF, hw.SEND_IMMEDIATE]) # AC0=1, AC3=0
    print("Holding State A (AC3 LOW) for 2 seconds...")
    time.sleep(2)

    print("State B: AC3 = HIGH (1), AC0 (3.3V) = HIGH (1)")
    hw.write_raw([hw.SET_HIGH_BYTE, 0x49, 0xFF, hw.SEND_IMMEDIATE]) # AC0=1, AC3=1
    print("Holding State B (AC3 HIGH) for 2 seconds...")
    time.sleep(2)

    print("\nClosing hardware...")
    hw.set_voltage_pins("OFF")
    hw.close()
    print("Test Complete.")

if __name__ == '__main__':
    main()
