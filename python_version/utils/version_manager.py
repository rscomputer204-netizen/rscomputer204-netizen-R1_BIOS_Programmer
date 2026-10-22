import os

import sys

class VersionManager:
    @staticmethod
    def get_version(root_dir=None):
        """
        Reads the version from version.txt in the root directory.
        Returns 'Unknown Version' if file is missing or error occurs.
        """
        try:
            version_file = None
            
            # 1. Explicit Root Provided
            if root_dir:
                version_file = os.path.join(root_dir, "version.txt")
            
            # 2. Frozen (EXE) Mode
            elif getattr(sys, 'frozen', False):
                # In PyInstaller, sys.executable is the exe path
                base_dir = os.path.dirname(sys.executable)
                version_file = os.path.join(base_dir, "version.txt")
                
                # Fallback: Check _internal if not in root (sometimes bundled there)
                if not os.path.exists(version_file):
                     internal_dir = os.path.join(base_dir, "_internal")
                     if os.path.exists(os.path.join(internal_dir, "version.txt")):
                         version_file = os.path.join(internal_dir, "version.txt")

            # 3. Source Mode
            else:
                # Path: driver/python_version/utils/version_manager.py
                # Goal: driver/version.txt
                
                current_dir = os.path.dirname(os.path.abspath(__file__)) # utils
                python_version_dir = os.path.dirname(current_dir)       # python_version
                driver_dir = os.path.dirname(python_version_dir)        # driver (ROOT)
                
                version_file = os.path.join(driver_dir, "version.txt")
                
                # Fallback: Check python_version just in case
                if not os.path.exists(version_file):
                    if os.path.exists(os.path.join(python_version_dir, "version.txt")):
                        version_file = os.path.join(python_version_dir, "version.txt")
            
            if version_file and os.path.exists(version_file):
                with open(version_file, "r") as f:
                    version = f.read().strip()
                    if version:
                        return version
            
            return "Unknown Version"
            
        except Exception:
            return "Unknown Version"
