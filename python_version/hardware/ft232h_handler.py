import ctypes
import time
import os
import threading

class FT232HDriver:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        # Try to load the FTDI DLL
        try:
            if hasattr(os, 'add_dll_directory'):
                # Common path for FTDI drivers
                try:
                    os.add_dll_directory(r"C:\Windows\System32")
                except:
                    pass
            
            self.ft = ctypes.windll.LoadLibrary("ftd2xx.dll")
        except Exception as e:
            try:
                self.ft = ctypes.windll.LoadLibrary("ftd2xx64.dll")
            except:
                self.ft = None
                print("FTD2XX DLL not found. Running in Offline Mode.")

        if self.ft:
            self.handle = ctypes.c_void_p()
            self.is_open = False

        self._lock = threading.RLock()  # Re-entrant lock: protects FT_Write/FT_Read from concurrent threads

        # Define argtypes for robustness (Prevents OverflowError on 64-bit)
        if self.ft:
            try:
                self.ft.FT_Open.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
                self.ft.FT_Close.argtypes = [ctypes.c_void_p]
                self.ft.FT_Write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
                self.ft.FT_Read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
                self.ft.FT_SetBitMode.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_ubyte]
                self.ft.FT_Purge.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                self.ft.FT_SetLatencyTimer.argtypes = [ctypes.c_void_p, ctypes.c_ubyte]
                self.ft.FT_SetTimeouts.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
                self.ft.FT_GetQueueStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
                self.ft.FT_CreateDeviceInfoList.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
                self.ft.FT_SetUSBParameters.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
                self.ft.FT_SetChars.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte]
                if hasattr(self.ft, 'FT_ResetDevice'):
                    self.ft.FT_ResetDevice.argtypes = [ctypes.c_void_p]
                if hasattr(self.ft, 'FT_Rescan'):
                    self.ft.FT_Rescan.argtypes = []
                if hasattr(self.ft, 'FT_Reload'):
                    self.ft.FT_Reload.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
            except Exception as e:
                self.log(f"WARNING: Could not set argtypes: {e}")

        # MPSSE Commands
        self.SET_LOW_BYTE = 0x80
        self.GET_LOW_BYTE = 0x81
        self.SET_HIGH_BYTE = 0x82
        self.GET_HIGH_BYTE = 0x83
        self.MSB_RISING_EDGE_OUT_BYTES = 0x10
        self.MSB_FALLING_EDGE_OUT_BYTES = 0x11
        self.MSB_RISING_EDGE_IN_BYTES = 0x20
        self.MSB_FALLING_EDGE_IN_BYTES = 0x24
        self.SEND_IMMEDIATE = 0x87

    def log(self, msg):
        print(f"DRIVER: {msg}")
        if self.log_callback and any(k in msg for k in ["ERROR", "FAILED", "CRITICAL"]):
            self.log_callback(f"DRIVER: {msg}")

    def force_cleanup(self):
        """Immediately closes handle and clears state without attempting I/O."""
        with self._lock:
            if self.handle and self.handle.value:
                try:
                    self.ft.FT_SetBitMode(self.handle, 0x00, 0x00)
                    self.ft.FT_Purge(self.handle, 3)
                    if hasattr(self.ft, 'FT_ResetDevice'):
                        self.ft.FT_ResetDevice(self.handle)
                except Exception:
                    pass
                try:
                    self.ft.FT_Close(self.handle)
                except Exception:
                    pass
            self.handle = ctypes.c_void_p()
            self.is_open = False

    def open(self, device_index=0):
        # Result status codes
        self.last_res = 3 # Default to DEVICE_NOT_OPENED
        
        if not self.ft:
            self.log("ERROR: Drivers not loaded. Cannot open device.")
            return False
        
        with self._lock:
            # Ensure any previous handle is closed and cleared before opening
            self.force_cleanup()
            
            # Retry loop for robust connection (OS driver handover can be slow after reconnect)
            for attempt in range(5):
                self.handle = ctypes.c_void_p()
                self.last_res = self.ft.FT_Open(device_index, ctypes.byref(self.handle))
                if self.last_res == 0:
                    self.is_open = True
                    if self.init_mpsse():
                        return True
                    else:
                        self.log("MPSSE INIT FAILED, CLOSING HANDLE.")
                        self.close()
                        return False
                time.sleep(0.3)
                
            # If open failed with 3, try Rescan before giving up
            if self.last_res == 3:
                try:
                    if hasattr(self.ft, 'FT_Rescan'):
                        self.ft.FT_Rescan()
                        time.sleep(0.5)
                        self.handle = ctypes.c_void_p()
                        self.last_res = self.ft.FT_Open(device_index, ctypes.byref(self.handle))
                        if self.last_res == 0:
                            self.is_open = True
                            if self.init_mpsse():
                                return True
                            else:
                                self.close()
                                return False
                except Exception:
                    pass

            self.log(f"FT_Open FAILED WITH STATUS {self.last_res}")
            return False

    def get_last_error(self):
        status_map = {
            1: "INVALID_HANDLE", 2: "DEVICE_NOT_FOUND", 3: "DEVICE_NOT_OPENED",
            4: "IO_ERROR", 5: "INSUFFICIENT_RESOURCES", 6: "INVALID_PARAMETER",
            7: "INVALID_BAUD_RATE", 8: "DEVICE_NOT_OPENED_FOR_ERASE",
            9: "DEVICE_NOT_OPENED_FOR_WRITE", 10: "FAILED_TO_WRITE_DEVICE",
            11: "EEPROM_READ_FAILED", 12: "EEPROM_WRITE_FAILED",
            13: "EEPROM_ERASE_FAILED", 14: "EEPROM_NOT_PRESENT",
            15: "EEPROM_NOT_PROGRAMMED", 16: "INVALID_ARGS", 17: "NOT_SUPPORTED"
        }
        return status_map.get(self.last_res, f"UNKNOWN_ERROR_{self.last_res}")

    def close(self):
        with self._lock:
            if self.is_open and self.handle and self.handle.value:
                try:
                    # Auto-force all pins LOW before closing for absolute safety
                    self.set_voltage_pins("OFF")
                except Exception:
                    pass
                try:
                    self.ft.FT_SetBitMode(self.handle, 0x00, 0x00)
                    self.ft.FT_Purge(self.handle, 3)
                    if hasattr(self.ft, 'FT_ResetDevice'):
                        self.ft.FT_ResetDevice(self.handle)
                except Exception:
                    pass
                try:
                    self.ft.FT_Close(self.handle)
                except Exception:
                    pass
            self.handle = ctypes.c_void_p()
            self.is_open = False

    def write_raw(self, data):
        if not self.is_open or not self.handle or not self.handle.value: return
        length = len(data)
        if hasattr(data, 'tobytes'):
            data_buf = (ctypes.c_ubyte * length).from_buffer_copy(data)
        elif isinstance(data, (list, tuple)):
            data_buf = (ctypes.c_ubyte * length)(*data)
        else:
            data_buf = (ctypes.c_ubyte * length).from_buffer_copy(data)
            
        written = ctypes.c_uint()
        with self._lock:
            self.ft.FT_Write(self.handle, data_buf, length, ctypes.byref(written))

    def read_raw(self, length, timeout_ms=3000):
        if not self.is_open or not self.handle or not self.handle.value: return bytearray()
        
        data = bytearray()
        timeout_sec = max(1.0, timeout_ms / 1000.0)
        t_last = time.time()
        
        with self._lock:
            while len(data) < length:
                rem = length - len(data)
                data_buf = (ctypes.c_ubyte * rem)()
                read_now = ctypes.c_uint32()
                res = self.ft.FT_Read(self.handle, data_buf, rem, ctypes.byref(read_now))
                if res != 0:
                    self.log(f"FT_Read FAILED WITH STATUS {res}")
                    break
                if read_now.value > 0:
                    data.extend(data_buf[:read_now.value])
                    t_last = time.time()  # Reset timer while actively receiving bytes
                else:
                    if (time.time() - t_last) > timeout_sec:
                        self.log(f"FT_Read TIMEOUT: received {len(data)}/{length} bytes")
                        break
                    time.sleep(0.0005)
                    
        return data

    def set_pins(self, value, direction):
        # 0x80: Set Low Byte, value, direction
        self.write_raw([0x80, value, direction])

    def set_voltage_pins(self, voltage_str):
        # AC0=3.3V (bit 0), AC1=1.8V (bit 1), AC2=1.2V (bit 2), AC3=LED (bit 3), AC6=Buzzer (bit 6)
        # LED is active LOW: AC3=0 -> LED ON (sinks to GND), AC3=1 -> LED OFF (3.3V).
        # Buzzer is active LOW: AC6=0 -> BUZZER ON, AC6=1 -> BUZZER OFF.
        # AC3=1 (LED OFF) and AC6=1 (BUZZER OFF) by default.
        
        # Determine target state (LED OFF by default: bit 3 = 1, Buzzer OFF: bit 6 = 1)
        if voltage_str == "3.3V":
            val = 0x49 # 0100 1001 (AC0 High, AC3 High=LED OFF, AC6 High=BUZZER OFF)
        elif voltage_str == "1.8V":
            val = 0x4A # 0100 1010 (AC1 High, AC3 High=LED OFF, AC6 High=BUZZER OFF)
        elif voltage_str == "1.2V":
            val = 0x4C # 0100 1100 (AC2 High, AC3 High=LED OFF, AC6 High=BUZZER OFF)
        else: # OFF or default
            val = 0x48 # 0100 1000 (AC3 High=LED OFF, AC6 High=BUZZER OFF, others Low)
            
        self.current_acbus_val = val
            
        # 1. Force ACBUS (AC0-AC7) to safe state. Direction 0xFF (all outputs).
        self.write_raw([self.SET_HIGH_BYTE, val, 0xFF, self.SEND_IMMEDIATE])
        # 2. Force ADBUS (AD0-AD7) completely LOW to prevent backpowering or floating pins.
        # This guarantees NO data pin is high when voltage is off.
        self.write_raw([0x80, 0x00, 0xFF, self.SEND_IMMEDIATE])
        
        # If we are actually turning ON a voltage, wait 50ms for discharge before enabling
        if voltage_str in ["3.3V", "1.8V", "1.2V"]:
            time.sleep(0.050) # 50ms Dead-Time Delay
            # Set the voltage pin HIGH, keep AC3 HIGH (LED OFF), AC6 HIGH (Buzzer OFF)
            self.write_raw([self.SET_HIGH_BYTE, val, 0xFF, self.SEND_IMMEDIATE])
            # Restore ADBUS to SPI idle state (CS High, DO Low, SK Low, all others Low)
            # 0x08 = CS High. Direction = 0x0B (CS, DO, SK are outputs)
            self.write_raw([0x80, 0x08, 0x0B, self.SEND_IMMEDIATE])
            
        self.log(f"VOLTAGE SET TO {voltage_str} (ACBUS VAL: 0x{val:02X})")

    def set_led(self, state: bool):
        """ 
        Turns the status LED on (True) or off (False).
        Hardware: LED Anode (+) -> 3.3V, LED Cathode (-) -> AC3 pin.
        Active LOW: AC3 = 0 -> LED ON, AC3 = 1 -> LED OFF.
        """
        if not self.is_open or not self.handle or not self.handle.value: return
        base_val = getattr(self, 'current_acbus_val', 0x48)
        if state:
            # LED ON -> AC3 Low (0)
            new_val = base_val & ~0x08
        else:
            # LED OFF -> AC3 High (1)
            new_val = base_val | 0x08
            
        self.current_acbus_val = new_val
        self.write_raw([self.SET_HIGH_BYTE, new_val, 0xFF, self.SEND_IMMEDIATE])

    def trigger_buzzer(self, pattern):
        """
        Plays a beep pattern on the hardware buzzer connected to AD7 (GPIOL3).
        AD7 is active LOW: AD7=0 -> BUZZER ON, AD7=1 -> BUZZER OFF.
        pattern: list of tuples (beep_duration_ms, silence_duration_ms)
        Uses RLock to safely wait for the SPI/I2C bus to be free.
        """
        if not self.is_open: return
        
        # Wait up to 3 seconds for the SPI bus to be free
        acquired = self._lock.acquire(timeout=3.0)
        if not acquired:
            self.log("BUZZER: Bus busy after 3s, skipping beep.")
            return

        try:
            # Use AD7 (GPIOL3) as buzzer pin
            # SPI dir with AD7 as output: 0x8B
            # CS must stay HIGH (AD3=1) while buzzer is active
            spi_dir  = getattr(self, '_adbus_spi_dir',  0x8B)
            idle_val = getattr(self, '_adbus_idle_val', 0x88)  # CS=1, AD7=1 (silent)
            buzz_val = idle_val & ~self._adbus_buzzer_bit       # CS=1, AD7=0 (buzzing)
            
            for beep_ms, silence_ms in pattern:
                # Turn Buzzer ON: AD7 = 0
                self.write_raw([0x80, buzz_val, spi_dir, self.SEND_IMMEDIATE])
                time.sleep(beep_ms / 1000.0)
                
                # Turn Buzzer OFF: AD7 = 1
                self.write_raw([0x80, idle_val, spi_dir, self.SEND_IMMEDIATE])
                if silence_ms > 0:
                    time.sleep(silence_ms / 1000.0)
        finally:
            self._lock.release()

    def sync_mpsse(self):
        # Flush any stalled buffers
        self.ft.FT_Purge(self.handle, 3) 
        
        for attempt in range(5):
            self.log(f"SYNC: SENDING 0xAA ECHO (Attempt {attempt+1})...")
            self.write_raw([0xAA, self.SEND_IMMEDIATE])
            res = self.read_raw(2, timeout_ms=1000)
            if res and list(res) == [0xFA, 0xAA]:
                self.log("SYNC: 0xAA ECHO OK. SENDING 0xAB ECHO...")
                self.write_raw([0xAB, self.SEND_IMMEDIATE])
                res = self.read_raw(2, timeout_ms=1000)
                if res and list(res) == [0xFA, 0xAB]:
                    self.log("SYNC: HANDSHAKE SUCCESS.")
                    return True
            time.sleep(0.1)
            self.ft.FT_Purge(self.handle, 1) # Clear RX
            
        self.log(f"SYNC: HANDSHAKE FAILED. LAST_RESPONSE: {res}")
        return False

    def list_devices(self):
        try:
            num = ctypes.c_uint()
            self.ft.FT_CreateDeviceInfoList(ctypes.byref(num))
            return num.value
        except:
            return 0

    def init_mpsse(self):
        # 1. Reset device
        self.log("INIT: RESETTING DEVICE MODE...")
        self.ft.FT_SetBitMode(self.handle, 0x00, 0x00) 
        time.sleep(0.05)
        
        # 2. Enable MPSSE with correct Pin Mask (0x0B = D0,D1,D3 outputs)
        self.log("INIT: ENABLING MPSSE MODE...")
        self.ft.FT_SetBitMode(self.handle, 0x0B, 0x02)
        time.sleep(0.05)
        
        # 3. Purge & Setup
        self.log("INIT: PURGING BUFFERS & SETTING TIMEOUTS...")
        self.ft.FT_Purge(self.handle, 3) 
        self.ft.FT_SetUSBParameters(self.handle, 65536, 65536)
        self.ft.FT_SetChars(self.handle, 0, 0, 0, 0) # Disable event/error characters
        self.ft.FT_SetLatencyTimer(self.handle, 1) # Set to 1ms for best performance
        self.ft.FT_SetTimeouts(self.handle, 1000, 1000)
        
        # --- EARLY ACBUS SAFE STATE ---
        # Force ACBUS to safe state IMMEDIATELY after MPSSE is enabled.
        # AC3=1 (LED OFF), AC6=1 (BUZZER OFF), all others LOW
        # 0x48 = 0100 1000
        self.log("INIT: FORCING ACBUS PINS TO SAFE LOW STATE...")
        self.write_raw([self.SET_HIGH_BYTE, 0x48, 0xFF, self.SEND_IMMEDIATE])
        self.current_acbus_val = 0x48
        # Also force ADBUS LOW to prevent any backpowering
        self.write_raw([0x80, 0x00, 0xFF, self.SEND_IMMEDIATE])
        time.sleep(0.02) # Short settle time
        # ------------------------------
        
        # 4. Sync
        sync_ok = self.sync_mpsse()
        
        # 5. Config SPI
        self.log("INIT: CONFIGURING SPI PARAMETERS...")
        self.write_raw([0x8A]) # Disable clock divide by 5 (ensure 60MHz master)
        self.write_raw([0x8D]) # Disable adaptive clocking
        self.set_spi_speed(2) # Use 15MHz (Fast & 100% Signal Integrity) by default
        self.set_pins(0x08, 0x0B) 
        
        # Final: Initialize ACBUS pins for Voltage Control (OFF = all pins low/safe)
        self.set_voltage_pins("OFF")
        self.log("INIT: ACBUS PINS CONFIRMED SAFE (ALL VOLTAGE OUTPUTS LOW).")
        
        # --- ADBUS BUZZER INIT (AD7 = GPIOL3 = bit 7) ---
        # AD7 is a free GPIO on all FT232H boards. Not EEPROM-locked.
        # Buzzer is active LOW: AD7=1 -> silent, AD7=0 -> buzzer ON.
        # SPI direction: 0x0B = AD0,AD1,AD3 out. We extend to 0x8B to add AD7 as output.
        # SPI idle value: 0x08 (CS=HIGH). With AD7=1 buzzer-off: 0x88.
        self._adbus_buzzer_bit = 0x80  # AD7 = bit 7
        self._adbus_spi_dir   = 0x8B  # 1000 1011 (AD0,AD1,AD3,AD7 as outputs)
        self._adbus_idle_val  = 0x88  # 1000 1000 (CS=1 at AD3, AD7=1=buzzer OFF)
        self.write_raw([0x80, self._adbus_idle_val, self._adbus_spi_dir, self.SEND_IMMEDIATE])
        self.log("INIT: AD7 BUZZER PIN INITIALIZED (HIGH = SILENT).")
        # ---------------------------------------------------
        
        return sync_ok

    def set_spi_speed(self, speed):
        # 0x86 = Set Clock Divisor
        # Divisor = (60MHz / (2 * Frequency)) - 1
        # Div 1 = 15MHz, Div 2 = 10MHz, Div 4 = 6MHz
        if speed >= 3: div = 1 # 15MHz
        elif speed == 2: div = 2 # 10MHz (Optimal, Rock-Solid Stable)
        elif speed == 1: div = 4 # 6MHz (Safe)
        else: div = 9 # 3MHz (Slow)
        self.write_raw([0x86, div, 0x00])

    # --- I2C MPSSE IMPLEMENTATION ---
    def i2c_init(self):
        self.write_raw([0x86, 0x95, 0x00]) # 200KHz
        self.write_raw([0x97]) # Disable adaptive clocking
        self.write_raw([0x8C]) # Enable 3-phase clocking
        self.write_raw([0x9E, 0x07, 0x00]) # Tristate on 1 for SCL/SDA
        self.set_pins(0x03, 0x03) # SCL, SDA High

    def i2c_start(self):
        # Start Condition: SDA goes Low while SCL is High
        for _ in range(4): self.set_pins(0x03, 0x03) # SCL Hi, SDA Hi
        for _ in range(4): self.set_pins(0x01, 0x03) # SCL Hi, SDA Lo
        self.set_pins(0x00, 0x03) # SCL Lo, SDA Lo

    def i2c_stop(self):
        # Stop Condition: SDA goes High while SCL is High
        for _ in range(4): self.set_pins(0x00, 0x03) # SCL Lo, SDA Lo
        for _ in range(4): self.set_pins(0x01, 0x03) # SCL Hi, SDA Lo
        for _ in range(4): self.set_pins(0x03, 0x03) # SCL Hi, SDA Hi

    def i2c_write_byte(self, byte):
        # Send byte (MSB first, rising edge)
        # Command 0x11: MSB out on -ve edge (will be ready on +ve edge)
        self.write_raw([0x11, 0x00, 0x00, byte])
        # Force SCL Low, SDA In
        self.set_pins(0x00, 0x01)
        # Read ACK (1 bit)
        self.write_raw([0x22, 0x00, 0x87])
        ack = self.read_raw(1)
        # Reset pins to SDA High
        self.set_pins(0x02, 0x03)
        return ack and not (ack[0] & 0x01)

    def i2c_read_byte(self, ack=True):
        # Force SDA In, SCL Lo
        self.set_pins(0x00, 0x01)
        # Read byte (8 bits)
        self.write_raw([0x20, 0x00, 0x00])
        data = self.read_raw(1)
        # Send ACK/NACK bit
        ack_bit = 0x00 if ack else 0xFF
        self.write_raw([0x13, 0x00, ack_bit, 0x87])
        return data[0] if data else 0x00

    def spi_write_read(self, data, read_len=0):
        if not self.is_open or not self.handle or not self.handle.value:
            return bytearray() if read_len > 0 else None
            
        with self._lock:
            spi_dir = getattr(self, '_adbus_spi_dir', 0x8B if hasattr(self, '_adbus_buzzer_bit') else 0x0B)
            idle_val = getattr(self, '_adbus_idle_val', 0x88 if hasattr(self, '_adbus_buzzer_bit') else 0x08)
            cs_low_val = idle_val & ~0x08  # CS Low, Buzzer High
            
            cmd = bytearray()
            
            # Select chip (CS Low)
            cmd.extend([0x80, cs_low_val, spi_dir])
            
            # Write bytes command if there is data to send
            if data:
                d_len = len(data)
                cmd.extend([0x11, (d_len-1) & 0xFF, (d_len-1) >> 8])
                cmd.extend(data)
                
            # Read bytes command if reading is requested
            if read_len > 0:
                cmd.extend([0x20, (read_len-1) & 0xFF, (read_len-1) >> 8])
                # Deselect Chip (CS High) in hardware IMMEDIATELY when read clocking completes!
                cmd.extend([0x80, idle_val, spi_dir])
                cmd.extend([0x87]) # Flush to PC
                self.write_raw(cmd)
                return self.read_raw(read_len)
            else:
                # CS High
                cmd.extend([0x80, idle_val, spi_dir])
                cmd.extend([0x87]) # Flush to PC
                self.write_raw(cmd)
                return bytearray()

    def spi_exec_sequence(self, commands):
        """
        Execute multiple SPI transactions in one USB packet.
        commands: list of bytearrays/lists to write. Each item is a separate transaction (CS toggle).
        """
        if not self.is_open or not self.handle or not self.handle.value:
            return
            
        spi_dir = getattr(self, '_adbus_spi_dir', 0x8B if hasattr(self, '_adbus_buzzer_bit') else 0x0B)
        idle_val = getattr(self, '_adbus_idle_val', 0x88 if hasattr(self, '_adbus_buzzer_bit') else 0x08)
        cs_low_val = idle_val & ~0x08
        
        full_cmd = bytearray()
        
        for data in commands:
            if not data: continue
            
            # CS Low
            full_cmd.extend([0x80, cs_low_val, spi_dir])
            
            # Write Data
            d_len = len(data)
            full_cmd.extend([0x11, (d_len-1) & 0xFF, (d_len-1) >> 8])
            full_cmd.extend(data)
            
            # CS High
            full_cmd.extend([0x80, idle_val, spi_dir])
            
        # Send Immediate at the very end to flush
        full_cmd.extend([0x87])
        
        self.write_raw(full_cmd)

