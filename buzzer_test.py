import time
import sys
import os

# Add driver directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_version'))

from hardware.ft232h_handler import FT232HDriver

def test_buzzer():
    print("Testing Buzzer connection...")
    driver = FT232HDriver()
    if not driver.open():
        print("Could not open FT232H device! Make sure it is plugged in and drivers are installed.")
        return

    print("FT232H Device opened successfully.")
    
    # Default state (AC4 = 1, AC3 = 1) -> 0x18
    driver.write_raw([driver.SET_HIGH_BYTE, 0x18, 0xFF, driver.SEND_IMMEDIATE])
    time.sleep(1)

    print("\n--- Test 1: Active LOW ---")
    print("(Beeps if Buzzer+ is on VCC and Buzzer- is on AC4)")
    for _ in range(5):
        driver.write_raw([driver.SET_HIGH_BYTE, 0x08, 0xFF, driver.SEND_IMMEDIATE]) # AC4=0
        time.sleep(0.1)
        driver.write_raw([driver.SET_HIGH_BYTE, 0x18, 0xFF, driver.SEND_IMMEDIATE]) # AC4=1
        time.sleep(0.1)
    
    time.sleep(1)

    print("\n--- Test 2: Active HIGH ---")
    print("(Beeps if Buzzer+ is on AC4 and Buzzer- is on GND)")
    driver.write_raw([driver.SET_HIGH_BYTE, 0x08, 0xFF, driver.SEND_IMMEDIATE]) # Base state AC4=0
    time.sleep(0.1)
    for _ in range(5):
        driver.write_raw([driver.SET_HIGH_BYTE, 0x18, 0xFF, driver.SEND_IMMEDIATE]) # AC4=1
        time.sleep(0.1)
        driver.write_raw([driver.SET_HIGH_BYTE, 0x08, 0xFF, driver.SEND_IMMEDIATE]) # AC4=0
        time.sleep(0.1)
    
    driver.write_raw([driver.SET_HIGH_BYTE, 0x18, 0xFF, driver.SEND_IMMEDIATE]) # Back to normal
    time.sleep(1)

    print("\n--- Test 3: Passive Buzzer ---")
    print("(Makes a strange noise/buzz if you are using a passive speaker)")
    # Send a fast toggle sequence directly to FT232H to simulate PWM
    pwm_payload = []
    for _ in range(1500):
        pwm_payload.extend([0x82, 0x08, 0xFF])
        pwm_payload.extend([0x82, 0x18, 0xFF])
    pwm_payload.append(0x87) # SEND_IMMEDIATE
    
    for _ in range(10):
        driver.write_raw(pwm_payload)
        
    driver.write_raw([driver.SET_HIGH_BYTE, 0x18, 0xFF, driver.SEND_IMMEDIATE])
    
    print("\nTesting complete. Closing device...")
    driver.close()

if __name__ == '__main__':
    test_buzzer()
