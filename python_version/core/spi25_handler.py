import time

class SPI25Handler:
    def __init__(self, hw_driver):
        self.hw = hw_driver
        self.address_bytes = 3

    def wait_busy(self, tick_callback=None, poll_delay=0):
        """Wait until chip is not busy (Status Register Bit 0 == 0)"""
        while True:
            # Send 05h (Read Status) and read 1 byte back
            res = self.hw.spi_write_read([0x05], 1)
            if res and not (res[0] & 0x01):
                break
            
            # Optimization: Only sleep if requested (e.g. for long erase)
            if poll_delay > 0:
                time.sleep(poll_delay)
            
            # Allow UI updates during long erase
            if tick_callback:
                tick_callback()

    def _build_address_bytes(self, address):
        if self.address_bytes == 4:
            return [
                (address >> 24) & 0xFF,
                (address >> 16) & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF
            ]
        return [
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF
        ]

    def write_enable(self):
        """Send Write Enable command (06h)"""
        self.hw.spi_write_read([0x06])

    def read_data(self, address, length, opcode=None):
        """Read data starting from address"""
        if opcode is None:
            opcode = 0x13 if self.address_bytes == 4 else 0x03
            
        cmd = [opcode] + self._build_address_bytes(address)
        # For reading, we send the command and then read 'length' bytes
        return self.hw.spi_write_read(cmd, length)

    def page_program(self, address, data, opcode=None):
        """Write a page (up to 256 bytes) to the chip"""
        if len(data) > 256:
            raise ValueError("Page size exceeded (max 256 bytes)")

        if opcode is None:
            opcode = 0x12 if self.address_bytes == 4 else 0x02

        # Optimization: Batch Write Enable + Page Program in one USB transaction
        wren_cmd = [0x06]
        pp_cmd = [opcode] + self._build_address_bytes(address) + list(data)
        
        # Check if driver supports batching (it should, we just added it)
        if hasattr(self.hw, 'spi_exec_sequence'):
            self.hw.spi_exec_sequence([wren_cmd, pp_cmd])
        else:
            # Fallback for CH341 or older drivers
            self.write_enable()
            self.hw.spi_write_read(pp_cmd)
            
        self.wait_busy()


    def chip_erase(self, tick_callback=None):
        """Send Chip Erase command (C7h) with optimization"""
        # Batch Write Enable + Chip Erase
        wren_cmd = [0x06]
        erase_cmd = [0xC7]
        
        if hasattr(self.hw, 'spi_exec_sequence'):
             self.hw.spi_exec_sequence([wren_cmd, erase_cmd])
        else:
            self.write_enable()
            self.hw.spi_write_read(erase_cmd)
            
        self.wait_busy(tick_callback, poll_delay=0.05)

    def read_id(self):
        """Read standard JEDEC ID using multiple opcodes (9Fh, 90h, ABh, 15h)"""
        # 1. Standard JEDEC ID (9Fh) - 3 bytes
        res = self.hw.spi_write_read([0x9F], 3)
        if res and len(res) >= 3 and any(b != 0x00 for b in res) and any(b != 0xFF for b in res):
            return "".join([format(b, '02X') for b in res])
            
        # 2. Manufacturer/Device ID (90h) - needs 3 dummy bytes, returns 2 bytes
        res = self.hw.spi_write_read([0x90, 0x00, 0x00, 0x00], 2)
        if res and len(res) >= 2 and any(b != 0x00 for b in res) and any(b != 0xFF for b in res):
            return "".join([format(b, '02X') for b in res])

        # 3. Release from Deep Power-down / Device ID (ABh) - 3 dummy bytes, returns 1 byte
        res = self.hw.spi_write_read([0xAB, 0x00, 0x00, 0x00], 1)
        if res and len(res) >= 1 and res[0] != 0x00 and res[0] != 0xFF:
            return "".join([format(b, '02X') for b in res])
            
        # 4. Old ID (15h)
        res = self.hw.spi_write_read([0x15], 3)
        if res and len(res) >= 3 and any(b != 0x00 for b in res) and any(b != 0xFF for b in res):
            return "".join([format(b, '02X') for b in res])

        # Fallback to 9Fh even if 000000/FFFFFF to show results to user if all failed
        res = self.hw.spi_write_read([0x9F], 3)
        if res and len(res) >= 3:
            return "".join([format(b, '02X') for b in res])
            
        return None
