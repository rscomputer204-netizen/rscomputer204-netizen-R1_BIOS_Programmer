import os
import win32com.client

def generate_sounds():
    out_dir = r"c:\Users\R1 LAB\Desktop\Desktop-bk\driver\python_version\sound_engine\sounds"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    sounds = {
        "read_done.wav": "Read complete.",
        "write_done.wav": "Write complete.",
        "verify_done.wav": "Verify complete.",
        "error.wav": "System Error.",
        "click.wav": "Click"
    }

    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        
        for filename, text in sounds.items():
            path = os.path.join(out_dir, filename)
            
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(path, 3) # SSFMCreateForWrite
            
            speaker.AudioOutputStream = stream
            speaker.Speak(text)
            stream.Close()
            
            print(f"Generated {filename}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    generate_sounds()
