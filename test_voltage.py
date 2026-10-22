import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from python_version.hardware.ft232h_handler import FT232HDriver

def test():
    print("Testing FT232H Voltage Control...")
    hw = FT232HDriver()
    if hw.open():
        print("Hardware Opened Successfully!")
        
        print("\n--- TURNING ALL OFF ---")
        hw.set_voltage_pins("OFF")
        time.sleep(2)
        
        print("\n--- TURNING ON 3.3V (AC0 HIGH) ---")
        print("Please check AC0 with your multimeter NOW. You have 15 seconds...")
        hw.set_voltage_pins("3.3V")
        
        for i in range(15):
            print(f"Time remaining: {15-i} seconds...")
            time.sleep(1)
            
        print("\n--- TURNING ALL OFF AGAIN ---")
        hw.set_voltage_pins("OFF")
        time.sleep(1)
        
        hw.close()
        print("Test Complete. Hardware Closed.")
    else:
        print("Failed to open FT232H!")

if __name__ == "__main__":
    test()
