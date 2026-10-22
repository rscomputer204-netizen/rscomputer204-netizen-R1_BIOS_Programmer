import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))
from hardware.ft232h_handler import FT232HDriver

def hold_low():
    hw = FT232HDriver()
    if not hw.open():
        print("[-] ERROR: Could not open FT232H device!")
        return

    print("=" * 65)
    print("      CONTINUOUS LED LOW TEST (HOLDING FOR 3 MINUTES)")
    print("=" * 65)
    print("\n[+] Device Connected.")
    print("[+] Step 1: Enabling 3.3V Power (AC0 = HIGH)...")
    hw.set_voltage_pins("3.3V")
    time.sleep(0.1)

    print("[+] Step 2: Forcing AC3 strictly LOW (0V / GND)...")
    print("    Command: [0x82, 0x41, 0xFF] (AC0=1, AC3=0, AC6=1, Dir=0xFF)")
    
    # We will continuously send the command every 500ms to guarantee it stays LOW
    # and print countdown for 180 seconds (3 full minutes!)
    total_seconds = 180
    start_time = time.time()
    
    print("\n" + "#" * 65)
    print(">>> AC3 IS NOW LOCKED TO LOW (0V / GND)! <<<")
    print(">>> Check your LED and Multimeter right now! <<<")
    print("#" * 65 + "\n")

    try:
        while time.time() - start_time < total_seconds:
            # Actively reinforce AC3 = LOW
            hw.write_raw([0x82, 0x41, 0xFF])
            # Also keep ADBUS in idle SPI state
            hw.write_raw([0x80, 0x08, 0x0B])
            
            elapsed = int(time.time() - start_time)
            remaining = total_seconds - elapsed
            if remaining % 5 == 0:
                print(f"[STATUS] AC3 is strictly LOW (0V) | Remaining: {remaining}s | Multimeter Probe AC3 now!")
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nUser stopped test.")

    finally:
        print("\nSafely resetting device and closing...")
        hw.set_voltage_pins("OFF")
        hw.close()
        print("Device closed.")

if __name__ == '__main__':
    hold_low()
