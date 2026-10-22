import os
import subprocess
import json
import logging
import sys

class FirmwareTools:
    """
    Wrapper for external open-source BIOS/ME tools.
    Expects tools to be in a 'tools' directory at the root.
    """
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.tools_dir = os.path.join(self.root_dir, "tools")
        
        # Define tool paths
        self.uefi_tool = os.path.join(self.tools_dir, "UEFITool.exe")
        self.me_analyzer = os.path.join(self.tools_dir, "MEA.exe")
        self.me_cleaner = os.path.join(self.tools_dir, "me_cleaner.py")
        self.fit_tool = os.path.join(self.tools_dir, "fit.exe") # Example path
        
    def _run_cmd(self, cmd, timeout=60):
        """Run a shell command and return stdout, stderr, and exit code."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return result.stdout, result.stderr, result.returncode
        except Exception as e:
            return "", str(e), -1

    def get_me_info(self, bios_path):
        """
        Use ME Analyzer to detect ME version and status.
        Returns a dictionary with version info.
        """
        if not os.path.exists(self.me_analyzer):
            return {"error": "ME Analyzer not found"}
            
        # Command: MEA.exe bios.bin
        stdout, stderr, code = self._run_cmd([self.me_analyzer, bios_path])
        
        if code != 0:
            return {"error": "MEA failed", "details": stderr}
            
        # Basic parsing (in a real scenario, MEA might output JSON or structured text)
        # Here we look for keywords in stdout
        # Parse all fields from the output (Key : Value format)
        info = {}
        for line in stdout.splitlines():
            # Skip empty lines or divider lines (like "-------")
            if ":" not in line or "---" in line:
                continue
                
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                # Clean up keys (remove extra spaces or artifacts)
                if key:
                    info[key] = val
                    
        return info

    def analyze_bios(self, bios_path):
        """Use UEFITool to extract basic info (Vendor, etc)"""
        # Note: UEFITool often needs a script or specific CLI flags for extraction.
        # This is a placeholder for basic validation.
        if not os.path.exists(self.uefi_tool):
            return {"error": "UEFITool not found"}
            
        # Example call for info only
        stdout, stderr, code = self._run_cmd([self.uefi_tool, bios_path, "-i"])
        return {"raw_info": stdout}

    def clean_me(self, input_path, output_path):
        """
        Use me_cleaner.py to clean the ME region.
        me_cleaner.py -O output_path input_path
        """
        if not os.path.exists(self.me_cleaner):
            return False, "me_cleaner.py not found"
            
        # Use current python executable to run the script
        cmd = [sys.executable, self.me_cleaner, "-O", output_path, input_path]
        stdout, stderr, code = self._run_cmd(cmd)
        
        if code == 0:
            return True, stdout
        else:
            return False, stderr

    def extract_rebuild_fit(self, input_path, me_region_path, mode="EXTRACT"):
        """
        Placeholder for FIT tool integration.
        FIT tool usage varies significantly by ME version.
        """
        if not os.path.exists(self.fit_tool):
            return False, "FIT Tool not found"
        return False, "FIT Integration not fully implemented"
