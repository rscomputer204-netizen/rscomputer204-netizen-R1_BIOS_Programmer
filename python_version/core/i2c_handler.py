import time

class I2CHandler:
    """
    Robust I2C Handler for 24-Series EEPROMs (24C01 through 24C1024).
    Calculates correct slave device address (dev_addr) and word address bytes
    based on standard EEPROM addrtype/capacity specifications.
    """
    def __init__(self, hw):
        self.hw = hw

    def _get_device_and_addr_bytes(self, chip_info, address):
        """
        Determines device address (0x50 base) and 1 or 2 word address bytes.
        
        addrtype mapping:
          0: 24C01 (Atmel legacy)
          1: 24C01 / 24C02 (up to 256 bytes, 1 byte address) -> dev=0x50, [addr & 0xFF]
          2: 24C04 (512 bytes, bit A8 in dev_addr)           -> dev=0x50 | ((addr>>8)&1), [addr & 0xFF]
          3: 24C08 (1024 bytes, bits A9..A8 in dev_addr)     -> dev=0x50 | ((addr>>8)&3), [addr & 0xFF]
          4: 24C16 (2048 bytes, bits A10..A8 in dev_addr)    -> dev=0x50 | ((addr>>8)&7), [addr & 0xFF]
          5: 24C32 - 24C512 (16-bit address, 2 bytes)        -> dev=0x50, [(addr>>8)&0xFF, addr & 0xFF]
          6: 24C1024 (17-bit address, bit A16 in dev_addr)   -> dev=0x50 | ((addr>>16)&1), [(addr>>8)&0xFF, addr & 0xFF]
        """
        size = int(chip_info.get('size', 256)) if chip_info else 256
        addrtype = chip_info.get('addrtype', None) if chip_info else None

        atype = -1
        if addrtype is not None:
            try:
                atype = int(addrtype)
            except Exception:
                atype = -1

        if atype == 1 or (atype == -1 and size <= 256):
            dev = 0x50
            addr_bytes = [address & 0xFF]
        elif atype == 2 or (atype == -1 and size == 512):
            dev = 0x50 | ((address >> 8) & 0x01)
            addr_bytes = [address & 0xFF]
        elif atype == 3 or (atype == -1 and size == 1024):
            dev = 0x50 | ((address >> 8) & 0x03)
            addr_bytes = [address & 0xFF]
        elif atype == 4 or (atype == -1 and size == 2048):
            dev = 0x50 | ((address >> 8) & 0x07)
            addr_bytes = [address & 0xFF]
        elif atype == 6 or (atype == -1 and size >= 131072):
            dev = 0x50 | ((address >> 16) & 0x01)
            addr_bytes = [(address >> 8) & 0xFF, address & 0xFF]
        else:
            # 24C32 - 24C512 (default for >= 4096 bytes)
            dev = 0x50
            addr_bytes = [(address >> 8) & 0xFF, address & 0xFF]

        return dev, addr_bytes

    def read_data(self, address, length, chip_info=None):
        """Reads 'length' bytes from I2C EEPROM starting at 'address'."""
        if not self.hw:
            return []

        dev_addr, addr_bytes = self._get_device_and_addr_bytes(chip_info, address)
        
        self.hw.i2c_start()
        # 1. Send Device Address in WRITE mode to set word address pointer
        if not self.hw.i2c_write_byte(dev_addr << 1):
            self.hw.i2c_stop()
            return []
            
        # 2. Send word address bytes
        for ab in addr_bytes:
            self.hw.i2c_write_byte(ab)
            
        # 3. Repeated Start to switch to READ mode
        self.hw.i2c_start()
        if not self.hw.i2c_write_byte((dev_addr << 1) | 0x01):
            self.hw.i2c_stop()
            return []
            
        # 4. Stream data bytes (ACK every byte except the last which gets NACK)
        data = bytearray()
        for i in range(length):
            b = self.hw.i2c_read_byte(ack=(i < length - 1))
            data.append(b)
            
        self.hw.i2c_stop()
        return data

    def write_page(self, address, data, chip_info=None):
        """Writes up to one page of data to I2C EEPROM starting at 'address'."""
        if not self.hw:
            return False

        dev_addr, addr_bytes = self._get_device_and_addr_bytes(chip_info, address)
        
        self.hw.i2c_start()
        # 1. Send Device Address in WRITE mode
        if not self.hw.i2c_write_byte(dev_addr << 1):
            self.hw.i2c_stop()
            return False
            
        # 2. Send word address bytes
        for ab in addr_bytes:
            self.hw.i2c_write_byte(ab)
            
        # 3. Send payload bytes
        for b in data:
            self.hw.i2c_write_byte(b)
            
        self.hw.i2c_stop()
        
        # EEPROM write cycle delay (tWR = 5ms to 10ms)
        time.sleep(0.010)
        return True
