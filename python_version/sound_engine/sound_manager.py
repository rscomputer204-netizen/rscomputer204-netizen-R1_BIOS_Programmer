import winsound
import os
import threading
import time

class SoundManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SoundManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized: return
        self.initialized = True
        
        # Mapping events to filenames
        self.sounds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
        self.events = {
            "CLICK": "click.wav",
            "SUCCESS": "read_done.wav", # Generic success
            "READ_COMPLETE": "read_done.wav",
            "WRITE_COMPLETE": "write_done.wav",
            "ERASE_COMPLETE": "erase_done.wav",
            "VERIFY_COMPLETE": "verify_done.wav",
            "IDENTIFY_COMPLETE": "identify_done.wav",
            "ERROR": "error.wav",
            "AUTO_COMPLETE": "auto_done.wav"
        }
        
        self.enabled = True
        self.hw_buzzer_enabled = False
        self.hw_driver = None
        self.volume = 0.5 
        
        # Pre-check file existence
        self.available_sounds = {}
        if os.path.exists(self.sounds_dir):
            for key, filename in self.events.items():
                path = os.path.join(self.sounds_dir, filename)
                if os.path.exists(path):
                    self.available_sounds[key] = path
                    
        print(f"[SOUND_ENGINE] Initialized. Available sounds: {list(self.available_sounds.keys())}")

    def inject_hardware(self, hw_driver):
        self.hw_driver = hw_driver

    def play_event(self, event_name):
        """Standard public API for triggering sound events"""
        self.play(event_name.upper())

    def play(self, event_name):
        def _play_thread():
            try:
                # 1. Hardware Buzzer (Independent of PC Sound)
                if self.hw_buzzer_enabled and self.hw_driver and hasattr(self.hw_driver, 'trigger_buzzer'):
                    if event_name == "CLICK":
                        self.hw_driver.trigger_buzzer([(30, 0)])
                    elif event_name == "ERROR":
                        self.hw_driver.trigger_buzzer([(100, 50), (100, 50), (100, 0)]) # Error sound
                    elif event_name == "IDENTIFY_COMPLETE":
                        self.hw_driver.trigger_buzzer([(150, 0)]) # One sound
                    elif event_name == "READ_COMPLETE":
                        self.hw_driver.trigger_buzzer([(150, 100), (150, 0)]) # Two sounds
                    elif event_name == "WRITE_COMPLETE":
                        self.hw_driver.trigger_buzzer([(150, 100), (150, 100), (150, 0)]) # Three sounds
                    elif event_name == "VERIFY_COMPLETE":
                        self.hw_driver.trigger_buzzer([(500, 0)]) # One long sound
                    elif "COMPLETE" in event_name or event_name == "SUCCESS":
                        self.hw_driver.trigger_buzzer([(300, 0)]) # Generic success

                # 2. PC Software Sound
                if not self.enabled: return
                
                # Priority 1: Play WAV file
                if event_name in self.available_sounds:
                    winsound.PlaySound(self.available_sounds[event_name], winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    # Priority 2: Fallback Beeps
                    if event_name == "CLICK":
                        pass 
                    elif "COMPLETE" in event_name or event_name == "SUCCESS":
                        winsound.Beep(1000, 100)
                        time.sleep(0.05)
                        winsound.Beep(1500, 100)
                    elif event_name == "ERROR":
                        winsound.Beep(500, 300)
            except Exception as e:
                print(f"[SOUND_ENGINE] Error playing {event_name}: {e}")

        # Threading checks
        threading.Thread(target=_play_thread, daemon=True).start()

    def play_click(self, event=None):
        self.play("CLICK")

    def play_success(self):
        self.play_event("SUCCESS")
        
    def play_error(self):
        self.play_event("ERROR")

