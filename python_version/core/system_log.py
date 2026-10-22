import os
import datetime
import threading

import re

class SystemLog:
    """
    System Log as Brain (The "Brain" of the operation).
    - Tracks ALL state changes.
    - Single source of truth.
    - Used for crash recovery and state restoration.
    """
    
    # Constants for Status
    STATUS_STARTED = "STARTED"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_ABORTED = "ABORTED"
    
    # Constants for Operations
    OP_READ = "READ"
    OP_WRITE = "WRITE"
    OP_ERASE = "ERASE"
    OP_VERIFY = "VERIFY"
    OP_IDENTIFY = "IDENTIFY"
    OP_AUTO = "AUTO"
    
    # File Paths
    LOG_DIR = "logs"
    LOG_FILE = os.path.join(LOG_DIR, "system.log")
    LOCK_FILE = os.path.join(LOG_DIR, "system.log.lock")
    
    def __init__(self, context_root):
        """
        Initialize the System Log Brain.
        :param context_root: The root directory where 'logs' folder should be created.
        """
        self.log_dir = os.path.join(context_root, self.LOG_DIR)
        self.log_file = os.path.join(self.log_dir, "system.log")
        self.lock_file = os.path.join(self.log_dir, "system.log.lock")
        
        self._ensure_log_dir()
        self._lock = threading.Lock()
        
    def _ensure_log_dir(self):
        try:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir, exist_ok=True)
            # Test write
            test_file = os.path.join(self.log_dir, '.write_test.tmp')
            with open(test_file, 'w') as f:
                f.write('1')
            os.remove(test_file)
        except (PermissionError, OSError):
            appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
            self.log_dir = os.path.join(appdata, 'R1_BIOS_Programmer', self.LOG_DIR)
            self.log_file = os.path.join(self.log_dir, "system.log")
            self.lock_file = os.path.join(self.log_dir, "system.log.lock")
            try:
                os.makedirs(self.log_dir, exist_ok=True)
            except Exception:
                pass
            
    def _write_line(self, line):
        """Thread-safe write to log file"""
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                
    def _create_lock(self):
        """Create lock file to indicate active operation (Crash detection)"""
        if not os.path.exists(self.lock_file):
            with open(self.lock_file, "w") as f:
                f.write(f"LOCKED_AT={datetime.datetime.now().isoformat()}")
                
    def _remove_lock(self):
        """Remove lock file when operation completes cleanly"""
        if os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except:
                pass

    def check_crash_state(self):
        """
        Check if the last session crashed (Lock file exists).
        :return: True if crashed, False otherwise.
        """
        return os.path.exists(self.lock_file)

    def log_operation(self, operation, status, **kwargs):
        """
        Log a major operation state change.
        Format: [TIMESTAMP] SESSION_ID=... KEY=VALUE ...
        """
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Session ID is typically YYYYMMDD_HHMMSS of the start of this specific op sequence
        # For simplicity, we can generate a session id if not provided, or just use current time
        session_id = kwargs.get("session_id", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        
        # Build the log line
        log_parts = [
            f"[{ts}]",
            f"SESSION_ID={session_id}",
            f"OPERATION={operation}",
            f"STATUS={status}"
        ]
        
        for k, v in kwargs.items():
            if k != "session_id":
                log_parts.append(f"{k.upper()}={v}")
                
        line = " ".join(log_parts)
        self._write_line(line)
        
        # Handle Locking Logic
        if status == self.STATUS_STARTED:
            self._create_lock()
        elif status in [self.STATUS_SUCCESS, self.STATUS_FAILED, self.STATUS_ABORTED]:
            self._remove_lock()
            
    def get_last_state(self):
        """
        Parse the log file to find the last recorded state.
        :return: Dict with last operation details or None.
        """
        if not os.path.exists(self.log_file):
            return None
            
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # Scan backwards for the last valid entry
            for line in reversed(lines):
                state = self.parse_log_line(line)
                if state:
                    return state
        except Exception as e:
            print(f"Log Parse Error: {e}")
            
        return None

    def parse_log_line(self, line):
        """
        Parse a single log line into a dictionary.
        Supports values with spaces (path, etc).
        Example: [2026-01-30 00:54:57] SESSION_ID=20260130_005457 OPERATION=SAVE STATUS=SUCCESS PATH=C:/My Path/file.bin
        """
        line = line.strip()
        if not line or not line.startswith("["):
            return None
            
        try:
            # Extract timestamp
            ts_match = re.search(r"\[(.*?)\]", line)
            if not ts_match: return None
            timestamp = ts_match.group(1)
            
            # The rest of the line
            content = line[ts_match.end():].strip()
            
            # Regex to find KEY=VALUE where VALUE can contain spaces but doesn't contain the next KEY= pattern
            # Uses positive lookahead to stop at the next KEY= or end of string
            pattern = r"([A-Z0-9_]+)=(.+?)(?=\s+[A-Z0-9_]+=|$)"
            matches = re.findall(pattern, content)
            
            state = {"TIMESTAMP": timestamp}
            for k, v in matches:
                state[k] = v
                
            return state
        except:
            return None

    def get_recovery_suggestion(self):
        """
        Analyze system.log to suggest recovery actions.
        """
        if not self.check_crash_state():
            return None # No crash detected
            
        last_state = self.get_last_state()
        if not last_state:
            return None
            
        op = last_state.get("OPERATION")
        status = last_state.get("STATUS")
        
        if status == self.STATUS_STARTED:
            # Operation started but never finished -> CRASH
            if op == self.OP_WRITE:
                return f"CRASH DETECTED DURING 'WRITE'. SUGGESTION: ERASE -> WRITE."
            elif op == self.OP_ERASE:
                return f"CRASH DETECTED DURING 'ERASE'. SUGGESTION: RETRY ERASE."
            elif op == self.OP_VERIFY:
                 return f"CRASH DETECTED DURING 'VERIFY'. SUGGESTION: RETRY VERIFY (OR RE-WRITE IF DATA CORRUPT)."
            else:
                 return f"CRASH DETECTED DURING '{op}'. SYSTEM STATE UNKNOWN."
                 
        return None
