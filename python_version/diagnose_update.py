import requests
import zipfile
import io
import sys

url = "https://raw.githubusercontent.com/RSCompu/version.json/main/update.zip"
print(f"Downloading from: {url}")

try:
    r = requests.get(url)
    print(f"Status Code: {r.status_code}")
    
    if r.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            print("\nZip Contents:")
            for name in z.namelist():
                print(f" - {name}")
                
            # Try to find version.txt
            v_files = [f for f in z.namelist() if "version.txt" in f]
            if v_files:
                for vf in v_files:
                    print(f"\nReading {vf}:")
                    print("-" * 20)
                    print(z.read(vf).decode('utf-8', errors='ignore'))
                    print("-" * 20)
            else:
                print("\nWARNING: No version.txt found in zip!")
    else:
        print("Failed to download file.")

except Exception as e:
    print(f"Error: {e}")
