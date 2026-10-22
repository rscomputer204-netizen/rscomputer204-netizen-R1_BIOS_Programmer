import xml.etree.ElementTree as ET
import os
import shutil

class ChipDatabase:
    def __init__(self, xml_path):
        self.base_xml_path = xml_path
        self.xml_path = self._resolve_db_path(xml_path)
        self.chips = []
        if os.path.exists(self.xml_path):
            self.load_chips()
        elif os.path.exists(self.base_xml_path):
            self.xml_path = self.base_xml_path
            self.load_chips()

    def _resolve_db_path(self, base_path):
        r"""
        Determines the correct writable path for chiplist.xml.
        If base_path is in a protected system directory (like C:\Program Files),
        or if user custom database already exists in %APPDATA%, use %APPDATA%\R1_BIOS_Programmer\chiplist.xml.
        """
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
        user_db_dir = os.path.join(appdata, 'R1_BIOS_Programmer')
        user_xml = os.path.join(user_db_dir, 'chiplist.xml')
        
        # 1. If user custom database already exists in AppData, use it
        if os.path.exists(user_xml):
            return user_xml
            
        # 2. Check if base_path is directly writable (dev mode / portable)
        try:
            if os.path.exists(base_path):
                # Try opening in append mode to verify write permission
                with open(base_path, 'a', encoding='utf-8') as f:
                    pass
                return base_path
            else:
                base_dir = os.path.dirname(base_path) or '.'
                test_file = os.path.join(base_dir, '.write_test.tmp')
                with open(test_file, 'w') as f:
                    f.write('1')
                os.remove(test_file)
                return base_path
        except (PermissionError, OSError):
            # 3. Base path is protected (e.g. C:\Program Files\R1_BIOS_Programmer)
            # Create user copy in AppData so user can add ICs freely without admin rights
            try:
                os.makedirs(user_db_dir, exist_ok=True)
                if os.path.exists(base_path):
                    shutil.copy2(base_path, user_xml)
                return user_xml
            except Exception:
                return base_path

    def load_chips(self):
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            # Iterate through protocols (SPI, I2C)
            for protocol in root:
                protocol_name = protocol.tag
                if protocol_name.upper() in ["MICROWIRE", "MW"]:
                    continue  # MicroWire completely removed
                for manufacturer in protocol:
                    manufacturer_name = manufacturer.tag
                    for chip in manufacturer:
                        chip_info = {
                            'protocol': protocol_name,
                            'manufacturer': manufacturer_name,
                            'name': chip.tag,
                            'id': chip.get('id', '0'),
                            'size': int(chip.get('size', '0')),
                            'page': chip.get('page', '256'),
                            'spicmd': chip.get('spicmd', '25'),
                            'addrtype': chip.get('addrtype', '0')
                        }
                        self.chips.append(chip_info)
            print(f"Successfully loaded {len(self.chips)} chips.")
        except Exception as e:
            print(f"Error loading XML: {e}")

    def search_chip(self, name):
        results = [c for c in self.chips if name.upper() in c['name'].upper()]
        return results

    def add_chip_from_xml(self, xml_string):
        """
        Parses an XML string and injects it into chiplist.xml
        """
        try:
            user_root = ET.fromstring(xml_string.strip())
            
            if len(user_root) == 0:
                manufacturer = user_root.get("manufacturer", "UNKNOWN_MANUFACTURER").upper().replace(" ", "_")
                if "manufacturer" in user_root.attrib:
                    del user_root.attrib["manufacturer"]
                chip_node = user_root
            else:
                manufacturer = user_root.tag.upper().replace(" ", "_")
                chip_node = user_root[0]
            
            chip_name = chip_node.tag
            chip_id = chip_node.get('id', '')
            
            # Check for duplicates by ID only (ignore if ID is empty or invalid)
            if chip_id and chip_id.upper() not in ["0", "000000", "FFFFFF"]:
                for existing_chip in self.chips:
                    if existing_chip['id'].upper() == chip_id.upper():
                        return False, f"ALREADY EXISTS: An IC with ID {chip_id} is already in the database ({existing_chip['name']})."
            
            # Convert to string but remove the auto-closing namespace if any
            chip_xml_str = ET.tostring(chip_node, encoding='unicode').strip()
            
            with open(self.xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            mfg_tag_open = f"<{manufacturer}>"
            
            if mfg_tag_open in content:
                insert_pos = content.find(mfg_tag_open) + len(mfg_tag_open)
                new_content = content[:insert_pos] + f"\n      {chip_xml_str}" + content[insert_pos:]
            else:
                spi_tag_open = "<SPI>"
                if spi_tag_open in content:
                    insert_pos = content.find(spi_tag_open) + len(spi_tag_open)
                    new_mfg_block = f"\n    <{manufacturer}>\n      {chip_xml_str}\n    </{manufacturer}>"
                    new_content = content[:insert_pos] + new_mfg_block + content[insert_pos:]
                else:
                    return False, "<SPI> tag not found in chiplist.xml"
            
            # Write updated XML to disk, with automatic fallback to AppData if permission denied
            try:
                with open(self.xml_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except (PermissionError, OSError):
                # Program Files or system folder is read-only; save to AppData
                appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
                user_db_dir = os.path.join(appdata, 'R1_BIOS_Programmer')
                os.makedirs(user_db_dir, exist_ok=True)
                user_xml = os.path.join(user_db_dir, 'chiplist.xml')
                with open(user_xml, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                self.xml_path = user_xml
                
            self.chips = []
            self.load_chips()
            return True, f"Successfully added {chip_name} under {manufacturer}!"
            
        except ET.ParseError:
            return False, "Invalid XML format. Please make sure the AI generated correct XML."
        except Exception as e:
            return False, f"Error: {str(e)}"

if __name__ == "__main__":
    db = ChipDatabase('chiplist.xml')
    search_query = 'W25Q'
    results = db.search_chip(search_query)
    print(f"\nSearching for '{search_query}':")
    for r in results[:5]:  # Show first 5 results
        print(f" - {r['manufacturer']} {r['name']} (ID: {r['id']}, Size: {r['size']} bytes)")
